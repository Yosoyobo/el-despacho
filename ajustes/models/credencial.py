"""Modelo Credencial — KV de secretos cifrados con La Bóveda.

Cada slot es un string (URL, token, JSON). El valor en DB siempre está cifrado;
solo se descifra al leerlo vía `Credencial.obtener()`. La UI nunca expone el
valor crudo; muestra "•••• guardado" o similar.
"""

from __future__ import annotations

from django.db import models

from lib.boveda import cifrar, descifrar

# Catálogo de slots conocidos. Agregar slots nuevos AQUÍ para que aparezcan en
# la UI de Los Ajustes. Slots no listados se aceptan también (extensible).
GRUPOS_CREDENCIAL: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    ("Los Chalanes (IA)",
     "Las llaves de cada Chalán. Sin llave, ese Chalán no participa y la cadena salta al siguiente.",
     [
        ("chalan_anthropic_api_key", "Chalán Claudio — API Key (sk-ant-…)", "API key del Chalán Claudio (Anthropic)."),
        ("chalan_openai_api_key", "Chalán GPT — API Key (sk-…)", "API key del Chalán GPT (OpenAI)."),
        ("chalan_deepseek_api_key", "Chalán Chino — API Key", "API key del Chalán Chino (Deepseek). NO soporta visión."),
        ("chalan_gemini_api_key", "Chalán Gemini — API Key (reservado)", "Reservado; el adapter se activa en un sprint posterior."),
        ("chalan_mimo_api_key", "Chalán MiMo — API Key", "API key del Chalán MiMo (Xiaomi). Soporta visión. Header `api-key`, no Bearer."),
        ("chalan_grok_api_key", "Chalán Grok — API Key (xai-…)", "API key del Chalán Grok (xAI). Soporta visión. Endpoint compatible con OpenAI."),
        ("anthropic_api_key", "Legacy: Anthropic — API Key", "Slot legacy. Usa chalan_anthropic_api_key."),
        ("openai_api_key", "Legacy: OpenAI — API Key", "Slot legacy. Usa chalan_openai_api_key."),
     ]),
    ("Google",
     "Para entrar con Google y para guardar archivos en Drive.",
     [
        ("google_oauth_client_id", "Google OAuth — Client ID", "Cliente OAuth de Google Cloud Console."),
        ("google_oauth_client_secret", "Google OAuth — Client Secret", "Secret del cliente OAuth."),
        ("google_oauth_project_id", "Google OAuth — Project ID", "Solo para logs / debug (ej. `el-despacho-496414`). Opcional."),
     ]),
    ("Herramientas del servidor",
     "Las piezas que corren junto a El Despacho en el NUC.",
     [
        ("n8n_api_key", "Automatizaciones (n8n) — llave de la API", "Se genera dentro de n8n, en Configuración → API. Sin ella El Chalán no puede ni ver qué automatizaciones hay: las capacidades desaparecen de su catálogo en vez de fallar cuando las use."),
        ("n8n_webhook_url", "n8n — Webhook URL", "Endpoint del Portavoz (vía Tailscale)."),
        ("n8n_webhook_secret", "n8n — Webhook Secret", "Para firmar HMAC saliente."),
        ("n8n_health_url", "n8n — Health URL (vía Tailscale)", "Ej. http://hal.tailedd04d.ts.net:5678/healthz. El Site lo pinguea."),
        ("paperless_token", "Papeleo (Paperless) — llave de la API", "Se puede pegar a mano (Paperless → Mi perfil → token) o dejar que la pantalla de Gerencia → Papeleo la canjee por ti con tu usuario y contraseña. Sin ella no se puede buscar papeleo desde El Despacho: la búsqueda lo dice, en vez de fallar."),
     ]),
    ("Papeleo y fiscal",
     "Lo que necesita la contabilidad y los comprobantes.",
     [
        ("rfc_empresa", "Contaduría — RFC de la empresa", "RFC de Learning Center. Se usa en el export fiscal XML (Anexo 24). Ej. XAXX010101000."),
        ("cfdi_ingesta_token", "CFDI por correo — token de entrada", "Contraseña con la que n8n empuja a El Despacho los CFDI que llegan al buzón de facturas. Invéntala larga y pégala igual en n8n. Sin ella la puerta no deja pasar a nadie: se cierra, no se abre."),
        ("papeleo_entrada_token", "Papeleo por correo — token de entrada", "Contraseña con la que n8n empuja a El Despacho el papeleo que llega al buzón (contratos, remisiones). Invéntala larga y pégala igual en n8n. Sin ella la puerta no deja pasar a nadie: se cierra, no se abre."),
     ]),
    ("Avisos y monitoreo",
     "Notificaciones al equipo y el monitor del taller.",
     [
        ("vapid_public_key", "Web Push — VAPID Public", "Notificaciones del Interfono. Generar con `interfono_generar_vapid`."),
        ("vapid_private_key", "Web Push — VAPID Private", "Notificaciones del Interfono. Generar con `interfono_generar_vapid`."),
        ("vapid_email", "Web Push — VAPID contact", "Correo de contacto del header VAPID (ej. mailto:soporte@learningcenter.mx)."),
        ("celador_token", "El Celador — token del monitor", "Token que manda el monitor del taller en la cabecera `x-celador` para leer el desglose de `/salud` (gasto de IA y uso). Lo entrega el taller. Sin token, `/salud` solo contesta la cara pública."),
        ("do_api_token", "DigitalOcean — API Token (dop_v1_...)", "Token para que El Site lea specs y bandwidth del Droplet."),
     ]),
    ("Cobros en línea",
     "Todavía sin usar: La Caja no existe, así que llenarlos no habilita nada.",
     [
        ("stripe_secret_key", "Stripe — Secret Key (sk_...)", "Llave secreta del modo correspondiente."),
        ("stripe_webhook_secret", "Stripe — Webhook Secret (whsec_...)", "Validación de webhooks entrantes."),
        ("mercadopago_access_token", "MercadoPago — Access Token", "Token de la cuenta vendedor."),
        ("mercadopago_webhook_secret", "MercadoPago — Webhook Secret", "Validación de notificaciones."),
     ]),
]

#: La lista plana de siempre, derivada de los grupos. Lo que ya consumía
#: `SLOTS_CREDENCIAL` sigue funcionando igual: agrupar es cosa de la pantalla,
#: no del catálogo.
SLOTS_CREDENCIAL: list[tuple[str, str, str]] = [
    s for _titulo, _ayuda, _slots in GRUPOS_CREDENCIAL for s in _slots
]


class Credencial(models.Model):
    clave = models.SlugField(max_length=80, unique=True)
    valor_cifrado = models.TextField()  # base64 URL-safe
    actualizada_en = models.DateTimeField(auto_now=True)
    actualizada_por = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Resultado del último "Probar conexión" — sólo aplica a slots de IA por
    # ahora pero el campo vive aquí para no proliferar tablas. NULL = nunca
    # probada.
    ultimo_test_en = models.DateTimeField(null=True, blank=True)
    ultimo_test_ok = models.BooleanField(null=True, blank=True)
    ultimo_test_mensaje = models.CharField(max_length=240, blank=True, default="")

    class Meta:
        db_table = "ajustes_credencial"
        ordering = ["clave"]

    def __str__(self):
        return self.clave

    # ── API alta-nivel ───────────────────────────────────────────────────────

    @classmethod
    def obtener(cls, clave: str) -> str | None:
        """Devuelve el valor descifrado o None si no existe."""
        row = cls.objects.filter(clave=clave).first()
        if not row:
            return None
        try:
            return descifrar(row.valor_cifrado)
        except Exception:
            return None

    @classmethod
    def guardar(cls, clave: str, valor: str, *, usuario=None) -> Credencial:
        """Cifra y persiste. Si valor es vacío, elimina la entrada."""
        if not valor:
            cls.objects.filter(clave=clave).delete()
            return cls(clave=clave)
        row, _ = cls.objects.update_or_create(
            clave=clave,
            defaults={
                "valor_cifrado": cifrar(valor),
                "actualizada_por": usuario,
            },
        )
        return row

    @classmethod
    def esta_configurado(cls, clave: str) -> bool:
        return cls.objects.filter(clave=clave).exists()
