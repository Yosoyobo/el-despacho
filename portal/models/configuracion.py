"""ConfiguracionPortal — lo que decide un humano sobre La Recepción.

Singleton (id=1) que se edita en La Gerencia → Los Ajustes → Portal de clientes.
Se crea al leer (`obtener`), no con una migración de datos (§14 Bug I).
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def _requeridos_default() -> list[str]:
    # La CSF es lo que el contador siempre pide para facturar (CFDI 4.0).
    return ["csf"]


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
    # Documentos (2026-09-29): el cliente sube su papelería desde el portal.
    documentos_activo = models.BooleanField(
        default=True,
        help_text="Enseñar la sección «Documentos» en el portal para que el cliente suba su papelería.",
    )
    # Lo que se le pide a TODO cliente: el portal y la ficha dicen qué falta.
    documentos_requeridos = models.JSONField(default=_requeridos_default, blank=True)
    # Qué tan reciente tiene que ser la Constancia de Situación Fiscal. El Chalán
    # lee su fecha de emisión y avisa si es más vieja.
    csf_vigencia_dias = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(730)],
        help_text="Días máximos de antigüedad de la Constancia de Situación Fiscal.",
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
