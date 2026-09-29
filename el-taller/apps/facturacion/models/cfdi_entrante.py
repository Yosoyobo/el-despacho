"""Los CFDI que llegan por correo y todavía no tienen dueño.

El problema que resuelve, medido el 2026-08-24: **de 36 facturas, sólo 1 tenía
su CFDI archivado**. No porque falte dónde guardarlo —eso existe desde julio—
sino porque bajarlo del PAC y subirlo uno por uno nadie lo hace.

La receta es que entren solos: n8n vigila el buzón, saca el XML y lo manda
aquí. Pero **ligar a ciegas sería peor que no ligar**: si dos facturas del mes
son del mismo cliente por el mismo monto, adivinar deja la contabilidad
apoyada en una suposición que nadie revisó.

Por eso esta tabla. Cuando la coincidencia es inequívoca, el CFDI se liga solo
y aquí queda el registro de que pasó. Cuando hay dudas —ninguna candidata, o
varias— queda `pendiente` y una persona decide. Es la misma regla de siempre
en este repo: el sistema propone, el humano confirma.
"""

from __future__ import annotations

from django.db import models

ESTADO_PENDIENTE = "pendiente"
ESTADO_LIGADO = "ligado"
ESTADO_IGNORADO = "ignorado"

ESTADOS = [
    (ESTADO_PENDIENTE, "Pendiente de asignar"),
    # «Ligado» y no «Ligado a su factura»: desde S-Pendientes-Sep28 un CFDI de
    # proveedor también se liga, a su egreso.
    (ESTADO_LIGADO, "Ligado"),
    (ESTADO_IGNORADO, "Ignorado"),
]

ORIGEN_CORREO = "correo"
ORIGEN_MANUAL = "manual"


class CfdiEntrante(models.Model):
    """Un comprobante que llegó y espera dueño."""

    #: El folio fiscal es único en todo México: es lo que evita archivar dos
    #: veces el mismo correo reenviado. `unique` lo garantiza en la base y no
    #: en la confianza de que el flujo no se repita.
    uuid = models.CharField(
        max_length=64, unique=True,
        help_text="Folio fiscal del SAT. Único: evita archivar dos veces el mismo correo.",
    )

    estado = models.CharField(max_length=16, choices=ESTADOS, default=ESTADO_PENDIENTE,
                              db_index=True)
    origen = models.CharField(max_length=16, default=ORIGEN_CORREO)

    # Lo que dice el comprobante, congelado. Se guarda aunque se ligue, para
    # poder revisar después sin volver a abrir el XML.
    emisor_rfc = models.CharField(max_length=20, blank=True, default="")
    emisor_nombre = models.CharField(max_length=200, blank=True, default="")
    receptor_rfc = models.CharField(max_length=20, blank=True, default="")
    receptor_nombre = models.CharField(max_length=200, blank=True, default="")
    total = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # El desglose, para proponer el egreso sin volver a abrir el XML
    # (S-Pendientes-Sep28). Null = el comprobante no lo trae o llegó antes de
    # que se guardara; en ese caso se relee del archivo.
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    descuento = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    iva = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                              help_text="IVA trasladado a nivel comprobante.")
    retenciones = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                      help_text="Total de impuestos retenidos.")
    concepto = models.CharField(max_length=300, blank=True, default="",
                                help_text="Los conceptos del comprobante, en una línea.")
    moneda = models.CharField(max_length=8, blank=True, default="")
    fecha_cfdi = models.CharField(max_length=40, blank=True, default="")
    referencia = models.CharField(max_length=60, blank=True, default="",
                                  help_text="Serie y folio como los escribe quien lo emitió.")

    #: A dónde se ligó, si se ligó.
    factura = models.ForeignKey(
        "facturacion.Factura", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cfdis_entrantes",
    )

    #: Quién lo emitió, si es la factura de un proveedor. Se llena solo cuando
    #: el RFC del emisor casa con UN proveedor del catálogo, o a mano.
    proveedor = models.ForeignKey(
        "el_catalogo.Proveedor", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cfdis_recibidos",
    )

    #: El egreso que registra el gasto. Uno a uno a propósito: la base
    #: garantiza que un egreso no quede respaldado por dos comprobantes, y que
    #: el mismo comprobante no respalde dos egresos (el gasto contado doble).
    egreso = models.OneToOneField(
        "tesoreria.Egreso", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cfdi_entrante",
    )

    #: Por qué quedó pendiente, en español: es lo que lee quien va a resolverlo.
    motivo = models.CharField(max_length=300, blank=True, default="")

    archivo_id = models.CharField(max_length=255, blank=True, default="",
                                  help_text="Dónde quedó guardado el XML.")
    pdf_id = models.CharField(max_length=255, blank=True, default="",
                              help_text="La representación impresa, si llegó con el correo.")

    recibido_en = models.DateTimeField(auto_now_add=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)
    resuelto_por = models.ForeignKey(
        "cuentas.Usuario", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "facturacion_cfdi_entrante"
        ordering = ["-recibido_en"]
        verbose_name = "CFDI entrante"
        verbose_name_plural = "CFDI entrantes"

    def __str__(self) -> str:
        quien = self.emisor_nombre or self.emisor_rfc or "?"
        return f"{self.referencia or self.uuid[:8]} · {quien} · {self.total or '?'}"

    @property
    def base(self):
        """Lo que vale antes de impuestos: SubTotal − Descuento."""
        if self.subtotal is None:
            return None
        return self.subtotal - (self.descuento or 0)

    @property
    def fecha(self):
        """La fecha del comprobante como `date`, o None si no se entiende."""
        from datetime import date

        try:
            return date.fromisoformat((self.fecha_cfdi or "")[:10])
        except ValueError:
            return None

    @property
    def comprobante_id(self) -> str:
        """El archivo que respalda el gasto: el PDF si llegó, si no el XML."""
        return self.pdf_id or self.archivo_id

    @property
    def es_nuestra_emision(self) -> bool:
        """¿Lo emitimos nosotros? Entonces va contra una Factura del sistema.

        Si somos el receptor, es la factura de un proveedor: un gasto, que se
        registra por otro camino.
        """
        return bool(self.factura_id) or self.estado == ESTADO_LIGADO
