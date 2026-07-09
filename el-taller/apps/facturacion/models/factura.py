"""Modelos de La Facturación V1 (S2b.facturacion-v1).

Factura comercial no fiscal. NO emite CFDI ni se conecta a PAC (regla §16
de CLAUDE.md). El contador externo timbra aparte y reconcilia su libro
fiscal con exports del libro interno.

Patrón espejo de `cotizaciones.Cotizacion` — código correlativo
`FAC-YYYY-NNNN` bajo `select_for_update`, manager `vigentes`, transiciones
de estado en `services.py`, totales calculados sobre items.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

from lib.fiscal import REGIMENES_FISCALES, desglose_honorarios, q2

ESTADOS_FACTURA = (
    ("borrador", "Borrador"),
    ("emitida", "Emitida"),
    ("cobrada_parcial", "Cobrada parcial"),
    ("cobrada_total", "Cobrada total"),
    ("cancelada", "Cancelada"),
)

CERO = Decimal("0.00")


def _generar_codigo(anio: int) -> str:
    """FAC-YYYY-NNNN tomando el max correlativo del año. Usar dentro de atomic."""
    prefijo = f"FAC-{anio}-"
    ultimo = (
        Factura.objects.select_for_update()
        .filter(codigo__startswith=prefijo)
        .order_by("-codigo")
        .first()
    )
    if ultimo:
        try:
            n = int(ultimo.codigo.rsplit("-", 1)[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"{prefijo}{n:04d}"


def _siguiente_folio_numero() -> int:
    """Máximo folio existente + 1 (arranca en 101 si no hay). Usar dentro de atomic.

    El folio «F###» es la foliación oficial de Learning Center (visible en
    tabla/detalle/PDF). Editable en el form; esto solo sugiere el siguiente.
    """
    ultimo = (
        Factura.objects.select_for_update()
        .exclude(folio_numero__isnull=True)
        .order_by("-folio_numero")
        .first()
    )
    if ultimo and ultimo.folio_numero:
        return ultimo.folio_numero + 1
    return 101


def sugerir_folio_numero() -> int:
    """Siguiente folio sugerido para el formulario (sin lock — solo lectura)."""
    ultimo = (
        Factura.objects.exclude(folio_numero__isnull=True)
        .order_by("-folio_numero")
        .first()
    )
    if ultimo and ultimo.folio_numero:
        return ultimo.folio_numero + 1
    return 101


def _vencimiento_default() -> date:
    return date.today() + timedelta(days=30)


class FacturaVigentesManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(estado="cancelada")


class Factura(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True)

    # Folio oficial visible de Learning Center: «F###». Editable, autollena
    # máx+1. Nullable para facturas viejas/importadas sin folio (se muestran
    # como "Sin información"). La secuencia con huecos se delata en la tabla.
    folio_numero = models.PositiveIntegerField(
        null=True, blank=True, unique=True, db_index=True
    )

    cliente = models.ForeignKey(
        "cartera.Cliente",
        on_delete=models.PROTECT,
        related_name="facturas",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="facturas",
    )
    cotizacion_origen = models.ForeignKey(
        "cotizaciones.Cotizacion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="facturas",
    )

    # El título se retiró del formulario (LC 2026-07): se autollena con el
    # Concepto. Se conserva el campo para no romper datos/PDF existentes.
    titulo = models.CharField(max_length=200, blank=True, default="")
    # Concepto corto que identifica la factura en listas y PDF. Obligatorio en
    # el form, pre-rellenado según los productos (LC 2026-07).
    concepto = models.CharField(max_length=200, blank=True, default="")
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_FACTURA,
        default="borrador",
        db_index=True,
    )

    fecha_emision = models.DateField(default=date.today)
    fecha_vencimiento = models.DateField(default=_vencimiento_default)

    moneda = models.CharField(max_length=3, default="MXN")
    # Régimen fiscal del documento (LC 2026-07). Hereda del proyecto al crear.
    # 'iva' = solo IVA vía tasas (M2M); 'honorarios' = IVA + retenciones RESICO;
    # 'exento' = sin impuestos.
    regimen_fiscal = models.CharField(
        max_length=12, choices=REGIMENES_FISCALES, default="iva", db_index=True
    )
    descuento_global_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    # Parcialidad a facturar (LC 2026-07): 100 = total; 50 = medio anticipo.
    # Escala el monto SIN tocar las líneas (pill 100%/50% del formulario).
    porcentaje_a_facturar = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("100.00")
    )

    notas = models.TextField(blank=True, default="")
    terminos = models.TextField(blank=True, default="")

    # PDF generado vía Google Docs (regla §8). Se regenera al pedirlo y se
    # guarda en Drive (subcarpeta "Facturas"). Vacío = aún no se generó.
    pdf_file_id = models.CharField(max_length=100, blank=True, default="")
    pdf_url = models.URLField(max_length=500, blank=True, default="")
    pdf_generado_en = models.DateTimeField(null=True, blank=True)

    # Denormalizado — se recalcula desde Ingresos vinculados.
    monto_cobrado = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )

    # Emisión
    emitida_en = models.DateTimeField(null=True, blank=True)
    emitida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="facturas_emitidas",
    )

    # Marca cuando el cron emitió el evento `factura.vencida` para evitar
    # duplicados. Si se registra un cobro y la factura sale de mora, limpiar.
    vencida_notificada_en = models.DateTimeField(null=True, blank=True)

    # Cancelación
    cancelada_en = models.DateTimeField(null=True, blank=True)
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="facturas_canceladas",
    )
    motivo_cancelacion = models.CharField(max_length=300, blank=True, default="")

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="facturas_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    vigentes = FacturaVigentesManager()

    class Meta:
        db_table = "facturacion_factura"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["cliente", "-creado_en"]),
            models.Index(fields=["proyecto", "-creado_en"]),
            models.Index(fields=["estado", "-fecha_emision"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.titulo}"

    def save(self, *args, **kwargs):
        # Título se retiró del form: si viene vacío, hereda el Concepto.
        if not (self.titulo or "").strip():
            self.titulo = (self.concepto or "").strip()[:200] or "Factura"
        necesita_codigo = not self.codigo
        necesita_folio = self.folio_numero is None and "update_fields" not in kwargs
        if necesita_codigo or necesita_folio:
            with transaction.atomic():
                if necesita_codigo:
                    anio = (self.fecha_emision or date.today()).year
                    self.codigo = _generar_codigo(anio)
                if necesita_folio:
                    self.folio_numero = _siguiente_folio_numero()
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    # --- propiedades derivadas -------------------------------------------

    @property
    def folio(self) -> str:
        """Folio oficial visible, ej. «F101». Vacío si aún no tiene."""
        return f"F{self.folio_numero}" if self.folio_numero else ""

    @property
    def folio_display(self) -> str:
        return self.folio or "Sin información"

    @property
    def es_editable(self) -> bool:
        return self.estado == "borrador"

    @property
    def esta_vencida(self) -> bool:
        return (
            self.estado in {"emitida", "cobrada_parcial"}
            and self.fecha_vencimiento < date.today()
        )

    @property
    def estado_visible(self) -> str:
        if self.esta_vencida:
            return "vencida"
        return self.estado

    @property
    def saldo_pendiente(self) -> Decimal:
        total = self.calcular_totales()["total"]
        return (total - (self.monto_cobrado or CERO)).quantize(Decimal("0.01"))

    # --- totales (copia exacta de Cotizacion.calcular_totales) -----------

    def calcular_totales(self) -> dict:
        items = list(self.items.all())
        subtotal_items = sum((it.subtotal for it in items), CERO)

        desc_pct = self.descuento_global_porcentaje or CERO
        descuento_global = q2(subtotal_items * desc_pct / Decimal("100"))
        # Parcialidad (pill 100%/50%): escala la base sin tocar las líneas.
        factor = (self.porcentaje_a_facturar or Decimal("100")) / Decimal("100")
        base_bruta = (subtotal_items - descuento_global)
        base_impuestos = q2(base_bruta * factor)
        parcialidad_descuento = q2(base_bruta - base_impuestos)

        trasladados = CERO
        retenciones = CERO
        impuestos_detalle: list = []

        if self.regimen_fiscal == "honorarios":
            # RESICO / honorarios: cálculo dedicado (IVA + ret ISR + ret IVA ⅔).
            d = desglose_honorarios(base_impuestos)
            trasladados = d["trasladados"]
            retenciones = d["retenciones"]
            impuestos_detalle = d["impuestos_detalle"]
            total = d["total"]
        elif self.regimen_fiscal == "exento":
            total = base_impuestos
        else:
            # 'iva' — mecanismo genérico vía tasas de la M2M (HALF_UP).
            for fi in self.impuestos.select_related("tasa").all():
                tasa = fi.tasa
                monto = q2(base_impuestos * tasa.porcentaje / Decimal("100"))
                if tasa.tipo == "retencion":
                    retenciones += monto
                else:
                    trasladados += monto
                impuestos_detalle.append({
                    "id": fi.id,
                    "tasa_id": tasa.id,
                    "nombre": tasa.nombre,
                    "tipo": tasa.tipo,
                    "porcentaje": tasa.porcentaje,
                    "monto": monto,
                })
            total = q2(base_impuestos + trasladados - retenciones)

        return {
            "subtotal_items": q2(subtotal_items),
            "descuento_global": descuento_global,
            "porcentaje_a_facturar": (self.porcentaje_a_facturar or Decimal("100")),
            "parcialidad_descuento": parcialidad_descuento,
            "base_impuestos": base_impuestos,
            "trasladados": q2(trasladados),
            "retenciones": q2(retenciones),
            "total": total,
            "impuestos_detalle": impuestos_detalle,
        }


class FacturaItem(models.Model):
    factura = models.ForeignKey(
        Factura, on_delete=models.CASCADE, related_name="items"
    )
    orden = models.PositiveIntegerField(default=0, db_index=True)

    servicio = models.ForeignKey(
        "el_catalogo.Servicio",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="lineas_factura",
    )
    descripcion = models.TextField()

    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    unidad = models.CharField(max_length=30, default="pieza")
    unidad_fk = models.ForeignKey(
        "el_catalogo.Unidad",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="lineas_factura",
        help_text="Catálogo. Si está vacío, se usa la cadena en 'unidad' (legacy).",
    )
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    descuento_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        db_table = "facturacion_item"
        ordering = ["factura", "orden", "pk"]

    def __str__(self) -> str:
        return f"{self.factura.codigo} · {self.descripcion[:40]}"

    @property
    def unidad_label(self) -> str:
        if self.unidad_fk_id:
            return self.unidad_fk.nombre
        return self.unidad or ""

    @property
    def subtotal(self) -> Decimal:
        bruto = (self.cantidad or CERO) * (self.precio_unitario or CERO)
        desc = (self.descuento_porcentaje or CERO) / Decimal("100")
        return (bruto * (Decimal("1") - desc)).quantize(Decimal("0.01"))


class FacturaImpuesto(models.Model):
    factura = models.ForeignKey(
        Factura, on_delete=models.CASCADE, related_name="impuestos"
    )
    tasa = models.ForeignKey(
        "ajustes.TasaImpositiva", on_delete=models.PROTECT, related_name="facturas"
    )
    aplicado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "facturacion_impuesto"
        unique_together = (("factura", "tasa"),)
        ordering = ["tasa__orden", "tasa__nombre"]

    def __str__(self) -> str:
        return f"{self.factura.codigo} · {self.tasa.nombre}"
