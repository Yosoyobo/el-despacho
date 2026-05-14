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
    ("google_oauth_client_id", "Google OAuth — Client ID", "Cliente OAuth del Workspace."),
    ("google_oauth_client_secret", "Google OAuth — Client Secret", "Secret del cliente OAuth."),
    ("google_oauth_redirect_uri", "Google OAuth — Redirect URI", "Ej. https://taller.ninomeando.com/auth/google/callback"),
    ("google_workspace_dominio", "Google Workspace — Dominio", "Dominio @ que se aceptará (vacío = cualquiera)."),
    ("stripe_secret_key", "Stripe — Secret Key (sk_...)", "Llave secreta del modo correspondiente."),
    ("stripe_webhook_secret", "Stripe — Webhook Secret (whsec_...)", "Validación de webhooks entrantes."),
    ("mercadopago_access_token", "MercadoPago — Access Token", "Token de la cuenta vendedor."),
    ("mercadopago_webhook_secret", "MercadoPago — Webhook Secret", "Validación de notificaciones."),
    ("anthropic_api_key", "Anthropic — API Key (sk-ant-...)", "Provider primario de Los Analistas."),
    ("openai_api_key", "OpenAI — API Key (sk-...)", "Fallback de El Reemplazo."),
    ("n8n_webhook_url", "n8n — Webhook URL", "Endpoint del Portavoz (vía Tailscale)."),
    ("n8n_webhook_secret", "n8n — Webhook Secret", "Para firmar HMAC saliente."),
    ("vapid_public_key", "Web Push — VAPID Public", "Notificaciones PWA (opcional, S3+)."),
    ("vapid_private_key", "Web Push — VAPID Private", "Notificaciones PWA (opcional, S3+)."),
]


class Credencial(models.Model):
    clave = models.SlugField(max_length=80, unique=True)
    valor_cifrado = models.TextField()  # base64 URL-safe
    actualizada_en = models.DateTimeField(auto_now=True)
    actualizada_por = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.SET_NULL, null=True, blank=True
    )

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
    def guardar(cls, clave: str, valor: str, *, usuario=None) -> "Credencial":
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
