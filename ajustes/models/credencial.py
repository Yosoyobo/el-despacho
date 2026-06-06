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
SLOTS_CREDENCIAL: list[tuple[str, str, str]] = [
    # (clave, etiqueta_humana, descripción)
    ("google_oauth_client_id", "Google OAuth — Client ID", "Cliente OAuth de Google Cloud Console."),
    ("google_oauth_client_secret", "Google OAuth — Client Secret", "Secret del cliente OAuth."),
    ("google_oauth_project_id", "Google OAuth — Project ID", "Solo para logs / debug (ej. `el-despacho-496414`). Opcional."),
    ("stripe_secret_key", "Stripe — Secret Key (sk_...)", "Llave secreta del modo correspondiente."),
    ("stripe_webhook_secret", "Stripe — Webhook Secret (whsec_...)", "Validación de webhooks entrantes."),
    ("mercadopago_access_token", "MercadoPago — Access Token", "Token de la cuenta vendedor."),
    ("mercadopago_webhook_secret", "MercadoPago — Webhook Secret", "Validación de notificaciones."),
    ("chalan_anthropic_api_key", "Chalán Claudio — API Key (sk-ant-…)", "API key del Chalán Claudio (Anthropic)."),
    ("chalan_openai_api_key", "Chalán GPT — API Key (sk-…)", "API key del Chalán GPT (OpenAI)."),
    ("chalan_deepseek_api_key", "Chalán Chino — API Key", "API key del Chalán Chino (Deepseek). NO soporta visión."),
    ("chalan_gemini_api_key", "Chalán Gemini — API Key (reservado)", "Reservado; el adapter se activa en un sprint posterior."),
    ("chalan_mimo_api_key", "Chalán MiMo — API Key", "API key del Chalán MiMo (Xiaomi). Soporta visión. Header `api-key`, no Bearer."),
    # Legacy — reemplazados por chalan_* arriba (pre-S2b.1). El super_admin
    # los puede borrar manualmente desde la UI tras validar la migración.
    ("anthropic_api_key", "Legacy: Anthropic — API Key", "Slot legacy. Usa chalan_anthropic_api_key."),
    ("openai_api_key", "Legacy: OpenAI — API Key", "Slot legacy. Usa chalan_openai_api_key."),
    ("n8n_webhook_url", "n8n — Webhook URL", "Endpoint del Portavoz (vía Tailscale)."),
    ("n8n_webhook_secret", "n8n — Webhook Secret", "Para firmar HMAC saliente."),
    ("vapid_public_key", "Web Push — VAPID Public", "Notificaciones del Interfono. Generar con `interfono_generar_vapid`."),
    ("vapid_private_key", "Web Push — VAPID Private", "Notificaciones del Interfono. Generar con `interfono_generar_vapid`."),
    ("vapid_email", "Web Push — VAPID contact", "Correo de contacto del header VAPID (ej. mailto:soporte@bautista.mx)."),
    ("do_api_token", "DigitalOcean — API Token (dop_v1_...)", "Token para que El Site lea specs y bandwidth del Droplet."),
    ("n8n_health_url", "n8n — Health URL (vía Tailscale)", "Ej. http://hal.tailedd04d.ts.net:5678/healthz. El Site lo pinguea."),
    # Google Drive. Configúralo con el asistente guiado en /ajustes/google-drive/
    # (no pegues estos valores a mano aquí — el asistente valida la conexión).
    ("google_drive_service_account_json", "Google Drive — Cuenta de servicio (JSON)", "Configúralo desde el asistente: Ajustes → Conectar Google Drive."),
    ("google_drive_carpeta_raiz_id", "Google Drive — Carpeta raíz (ID)", "Configúralo desde el asistente: Ajustes → Conectar Google Drive."),
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
