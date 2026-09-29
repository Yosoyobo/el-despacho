"""VersionImprenta — una foto de TODOS los ajustes de los documentos.

Se toma al guardar cualquier sección, con el resumen de lo que cambió en
palabras («Letra del documento: Arial → Lato»). Restaurar es copiar la foto de
vuelta y tomar una versión nueva que lo diga: el historial nunca se reescribe,
así que siempre se puede volver también de una restauración.
"""

from __future__ import annotations

from django.db import models


class VersionImprenta(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        "cuentas.Usuario", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    #: {"hoja": {...ConfiguracionDocumento...}, "ambitos": {ambito: valores}}
    foto = models.JSONField(default=dict)
    #: Los cambios respecto a la versión anterior, en palabras.
    resumen = models.JSONField(default=list, blank=True)
    #: Qué se guardó: «Marca», «Cotización», «Estado inicial», «Restaurada…».
    motivo = models.CharField(max_length=160, blank=True, default="")
    restaurada_de = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        db_table = "imprenta_version"
        ordering = ["-creado_en", "-pk"]
        verbose_name = "versión de los documentos"
        verbose_name_plural = "versiones de los documentos"

    def __str__(self) -> str:
        return f"Versión {self.pk} · {self.motivo}"
