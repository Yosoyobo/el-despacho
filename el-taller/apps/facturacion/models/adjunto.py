"""Los archivos de una factura más allá de su CFDI (S-Tickets-Oct14).

La factura guarda **un** PDF y **un** XML timbrados (`pdf_file_id`/`xml_file_id`:
son «el CFDI»). Pero en el día a día se suben más: el complemento de pago, la
constancia de retención, la orden de compra del cliente, un segundo PDF. Antes
el segundo archivo del mismo tipo se descartaba en silencio. Esta tabla guarda
los que no caben en el CFDI: tantos como haga falta, cada uno con su nombre.

Sólo se guarda la referencia a El Almacén (`archivo_id` = la huella del
contenido); el contenido se sirve por el proxy autenticado de la factura.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class FacturaAdjunto(models.Model):
    factura = models.ForeignKey(
        "facturacion.Factura", on_delete=models.CASCADE, related_name="adjuntos",
    )
    archivo_id = models.CharField(max_length=255)
    nombre = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120, blank=True, default="")
    tamano_bytes = models.PositiveBigIntegerField(default=0)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="factura_adjuntos",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "facturacion_adjunto"
        ordering = ["creado_en", "pk"]

    def __str__(self) -> str:
        return f"adjunto#{self.pk} {self.nombre}"

    @property
    def es_imagen(self) -> bool:
        return (self.mime_type or "").startswith("image/")

    @property
    def es_pdf(self) -> bool:
        return (self.mime_type or "") == "application/pdf"
