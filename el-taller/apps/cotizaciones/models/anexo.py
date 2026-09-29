"""Los anexos de una cotización: fichas técnicas que viajan pegadas al PDF.

Oscar, Sep28: «anexos de la cotización (se unen al final del PDF)». La ficha
técnica del termo, la tabla de tallas, la garantía del proveedor — papeles que
el cliente necesita junto con la propuesta y que hoy se mandaban aparte, como un
segundo adjunto que nadie abre.

**Dónde viven.** En El Almacén (`lib/almacen`), no en Drive: se leen cada vez
que se arma el PDF, y leer de Drive en caliente es justo lo que El Almacén vino
a quitar. La llave es el sha256 del contenido, así que la misma ficha anexada a
diez cotizaciones ocupa UN archivo en disco.

**Por eso quitar un anexo no borra el archivo.** Se hereda a la versión
siguiente (misma llave) y puede estar pegado a una cotización ya enviada: borrar
el archivo dejaría un hueco en un documento que el cliente ya tiene.

**Word y Excel se guardan ya convertidos a PDF.** Sólo un PDF se puede unir al
final de otro. Si el convertidor no contestaba al subir, se guarda el original
(`es_pdf=False`) y se intenta de nuevo al armar el documento — la ficha no se
pierde por un servicio caído.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class CotizacionAnexo(models.Model):
    cotizacion = models.ForeignKey(
        "cotizaciones.Cotizacion", on_delete=models.CASCADE, related_name="anexos",
    )
    #: Posición al final del documento (0 = el primero después de la cotización).
    orden = models.PositiveIntegerField(default=0)

    #: Cómo se llama en la pantalla: el nombre del archivo, ya en PDF si se
    #: convirtió («Ficha termo.docx» → «Ficha termo.pdf»).
    nombre = models.CharField(max_length=200)
    #: El nombre con el que se subió, por si se convirtió.
    nombre_original = models.CharField(max_length=200, blank=True, default="")

    #: La llave en El Almacén (sha256 del contenido).
    archivo_clave = models.CharField(max_length=100)
    #: False = es un Word/Excel que todavía no se pudo pasar a PDF; se reintenta
    #: al armar el documento.
    es_pdf = models.BooleanField(default=True)
    tamano = models.PositiveIntegerField(default=0, help_text="Bytes.")

    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="anexos_cotizacion",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cotizaciones_anexo"
        ordering = ["cotizacion", "orden", "pk"]
        verbose_name = "anexo de cotización"
        verbose_name_plural = "anexos de cotización"

    def __str__(self) -> str:
        return f"{self.cotizacion_id} · {self.nombre}"
