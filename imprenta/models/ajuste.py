"""AjusteImprenta — los valores de una parte de los documentos.

Una fila por ÁMBITO: los globales (`marca`, `tablas`, `despacho`, `firma`) y uno
por tipo de documento (`cotizacion`, `factura`…). Los valores son un diccionario
que valida `imprenta.esquema`; lo que no está guardado toma su default, que es
el documento de siempre.

La hoja general (motor, tamaño, márgenes, pie) sigue en
`ajustes.ConfiguracionDocumento`, que ya existía y de la que depende el
generador; La Imprenta la lee y la escribe, y la incluye en cada versión.
"""

from __future__ import annotations

from django.db import models


class AjusteImprenta(models.Model):
    ambito = models.CharField(max_length=40, unique=True)
    valores = models.JSONField(default=dict, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        "cuentas.Usuario", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "imprenta_ajuste"
        verbose_name = "ajuste de documentos"
        verbose_name_plural = "ajustes de documentos"

    def __str__(self) -> str:
        return f"La Imprenta · {self.ambito}"
