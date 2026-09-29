"""ConfiguracionPortal — lo que decide un humano sobre La Recepción.

Singleton (id=1) que se edita en La Gerencia → Los Ajustes → Portal de clientes.
Se crea al leer (`obtener`), no con una migración de datos (§14 Bug I).
"""

from __future__ import annotations

from django.db import models


class ConfiguracionPortal(models.Model):
    # Decisión de Oscar (2026-09-29): el portal entra SÓLO con el enlace por
    # correo. «Entrar con Google» se enciende aquí, y antes hay que registrar la
    # dirección de regreso del portal en Google Cloud Console: sin ella Google
    # contesta `redirect_uri_mismatch` y el botón no sirve.
    google_activo = models.BooleanField(
        default=False,
        help_text=(
            "Enseñar «Entrar con Google» en el portal. Antes, registra "
            "https://recepcion.learningcenter.mx/auth/google/callback en Google "
            "Cloud Console. Sólo entra quien ya tiene acceso: Google nunca da "
            "de alta a nadie."
        ),
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_configuracion"
        verbose_name = "configuración del portal"
        verbose_name_plural = "configuración del portal"

    def __str__(self) -> str:
        return f"Portal · Google {'encendido' if self.google_activo else 'apagado'}"

    @classmethod
    def obtener(cls) -> ConfiguracionPortal:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
