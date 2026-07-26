from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

from lib.fiscal import REGIMENES_FISCALES, desglose_honorarios, q2

ESTADOS_COTIZACION = (
    ("borrador", "Borrador"),
    ("generada", "Generada"),
    ("enviada", "Enviada"),
    ("aprobada", "Aprobada"),
    ("pagada", "Pagada"),
    ("rechazada", "Rechazada"),
    ("anulada", "Anulada"),
)

ESTADOS_TERMINAL = {"aprobada", "rechazada", "anulada"}

# El flujo de las cotizaciones de proyecto (generada → enviada → aprobada →
# pagada) es CONFIGURABLE desde La Gerencia (modelo EstadoCotizacion). El
# label/color de cada estado se lee del catálogo vía `mapa_estados_cot()`.

CERO = Decimal("0.00")


def _generar_codigo(anio: int) -> str:
    """COT-YYYY-NNNN tomando el max correlativo del año. Usar dentro de atomic."""
    prefijo = f"COT-{anio}-"
    ultimo = (
        Cotizacion.objects.select_for_update()
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


def _validez_default() -> date:
    return date.today() + timedelta(days=30)


class CotizacionVigentesManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(estado="anulada")


class Cotizacion(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True)

    cliente = models.ForeignKey(
        "cartera.Cliente",
        on_delete=models.PROTECT,
        related_name="cotizaciones",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cotizaciones",
    )

    titulo = models.CharField(max_length=200)
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_COTIZACION,
        default="borrador",
        db_index=True,
    )

    # Versión dentro de un proyecto (v1, v2, v3…). 0 = cotización standalone
    # (creada a mano desde el módulo Cotizaciones, no generada desde proyecto).
    # Las generadas desde la página del proyecto llevan version ≥ 1.
    version = models.PositiveIntegerField(default=0, db_index=True)

    fecha_emision = models.DateField(default=date.today)
    fecha_validez = models.DateField(default=_validez_default)

    moneda = models.CharField(max_length=3, default="MXN")
    # Régimen fiscal (LC 2026-07). Hereda del proyecto al generar la cotización.
    regimen_fiscal = models.CharField(
        max_length=12, choices=REGIMENES_FISCALES, default="iva", db_index=True
    )
    descuento_global_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )

    # Anticipo (S-Finanzas-V2 #E). Cuando la cotización está aprobada y
    # `anticipo_porcentaje > 0`, el monto se cuenta como "por cobrar"
    # hasta que se genere la factura del anticipo (vía service).
    # `anticipo_monto_override` permite fijar un monto absoluto distinto
    # al calculado del porcentaje (caso uso: redondeo a $5,000 exactos).
    anticipo_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="% del total que se cobra como anticipo. 0 = sin anticipo.",
    )
    anticipo_monto_override = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Monto absoluto del anticipo. Si se deja vacío, se calcula del porcentaje.",
    )
    anticipo_facturado_en = models.DateTimeField(
        null=True, blank=True,
        help_text="Cuando se generó la factura del anticipo desde esta cotización.",
    )

    notas = models.TextField(blank=True, default="")
    terminos = models.TextField(blank=True, default="")

    # LC 2026-07 (Oscar) — dos interruptores del documento que se le manda al
    # cliente. Se prenden desde la página de la cotización y cada versión
    # guarda los suyos (la siguiente versión los hereda).
    #
    # `incluir_desglose`: apagado, el PDF lleva la tablita de montos de cada
    # producto y nada más. Prendido, agrega al final el «Desglose de Elementos»
    # (todos los conceptos juntos) y el cálculo de impuestos con el total.
    incluir_desglose = models.BooleanField(
        default=False,
        help_text="Incluir al final del PDF el desglose de conceptos y el cálculo de impuestos.",
    )
    # `forma_pago`: elige el texto de la última nota del PDF.
    FORMA_ANTICIPO = "anticipo"
    FORMA_CONTADO = "contado"
    FORMAS_PAGO = (
        (FORMA_ANTICIPO, "Anticipo"),
        (FORMA_CONTADO, "Un solo pago"),
    )
    forma_pago = models.CharField(
        max_length=12, choices=FORMAS_PAGO, default=FORMA_ANTICIPO,
        help_text="Define la nota de forma de pago del PDF.",
    )

    # PDF generado vía Google Docs (regla §8). Se regenera al pedirlo y se
    # guarda en Drive (subcarpeta "Cotizaciones"). Vacío = aún no se generó.
    pdf_file_id = models.CharField(max_length=100, blank=True, default="")
    pdf_url = models.URLField(max_length=500, blank=True, default="")
    pdf_generado_en = models.DateTimeField(null=True, blank=True)

    # Envío
    enviada_en = models.DateTimeField(null=True, blank=True)
    enviada_a_email = models.CharField(max_length=200, blank=True, default="")

    # Pagada (flujo de proyecto: generada → enviada → aprobada → pagada).
    pagada_en = models.DateTimeField(null=True, blank=True)

    # Aprobación / rechazo (lado cliente — texto libre)
    aprobada_en = models.DateTimeField(null=True, blank=True)
    aprobada_por_nombre = models.CharField(max_length=200, blank=True, default="")
    aprobada_por_email = models.CharField(max_length=200, blank=True, default="")
    referencia_aprobacion = models.CharField(max_length=200, blank=True, default="")

    rechazada_en = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True, default="")

    # Anulación interna
    # Marca cuando el cron emitió el evento `cotizacion.vencida` para
    # evitar duplicados. Si la cotización se reactiva (raro), limpiar a None.
    vencida_notificada_en = models.DateTimeField(null=True, blank=True)

    anulada_en = models.DateTimeField(null=True, blank=True)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cotizaciones_anuladas",
    )
    motivo_anulacion = models.CharField(max_length=300, blank=True, default="")

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cotizaciones_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    vigentes = CotizacionVigentesManager()

    class Meta:
        db_table = "cotizaciones_cotizacion"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["cliente", "-creado_en"]),
            models.Index(fields=["proyecto", "-creado_en"]),
            models.Index(fields=["estado", "-fecha_emision"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.titulo}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            anio = (self.fecha_emision or date.today()).year
            with transaction.atomic():
                self.codigo = _generar_codigo(anio)
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    # --- estado / propiedades derivadas ----------------------------------

    @property
    def es_editable(self) -> bool:
        return self.estado == "borrador"

    @property
    def es_terminal(self) -> bool:
        return self.estado in ESTADOS_TERMINAL

    @property
    def permite_editar_texto(self) -> bool:
        """Si se puede corregir el TEXTO del documento (concepto y
        especificaciones) desde la página de la cotización.

        Es más permisivo que `es_editable` —que solo abarca borrador— porque
        redactar no cambia dinero: mientras la cotización esté viva se puede
        pulir la descripción. Una vez aprobada, pagada, rechazada o anulada
        queda como testimonio de lo que se le mandó al cliente.
        """
        return self.estado in ("borrador", "generada", "enviada")

    @property
    def esta_vencida(self) -> bool:
        """Vencida = enviada sin respuesta y fecha_validez < hoy."""
        return self.estado == "enviada" and self.fecha_validez < date.today()

    @property
    def estado_visible(self) -> str:
        """Estado para UI: convierte 'enviada' en 'vencida' si aplica."""
        if self.esta_vencida:
            return "vencida"
        return self.estado

    @property
    def version_label(self) -> str:
        """'v1', 'v2'… para el recuadro de Cotizaciones del proyecto."""
        return f"v{self.version}" if self.version else "—"

    def get_estado_display(self) -> str:
        """Override: el label sale del catálogo configurable (EstadoCotizacion)
        si el slug está ahí; si no, cae a los choices legacy del módulo
        standalone (borrador/rechazada/anulada) y por último al slug crudo."""
        from .estado_cotizacion import mapa_estados_cot
        m = mapa_estados_cot()
        if self.estado in m:
            return m[self.estado]["label"]
        return dict(ESTADOS_COTIZACION).get(self.estado, self.estado)

    @property
    def titulo_documento(self) -> str:
        """Título centrado del PDF, en el formato fijo de LC (Oscar 2026-07-25):
        «Producción de elementos para proyecto 'Ted Lasso'».

        Se deriva SIEMPRE del proyecto para que ninguna versión salga con otro
        encabezado; sin proyecto (cotización standalone) cae al título capturado.
        """
        if self.proyecto_id:
            nombre = (self.proyecto.nombre or self.proyecto.codigo or "").strip()
            if nombre:
                return f"Producción de elementos para proyecto '{nombre}'"
        return (self.titulo or self.codigo or "").strip()

    @property
    def estado_color(self) -> str:
        """Color HEX del estado actual (del catálogo; fallback gris)."""
        from .estado_cotizacion import mapa_estados_cot
        return (mapa_estados_cot().get(self.estado) or {}).get("color", "#667085")

    @property
    def nombre_pdf(self) -> str:
        """Nombre del archivo PDF. Para cotizaciones de proyecto (version ≥ 1)
        usa «NombreDelProyecto_Vn» (decisión Oscar); para las standalone usa el
        código COT-YYYY-NNNN."""
        import re
        if self.version and self.proyecto_id:
            base = (self.proyecto.nombre or self.proyecto.codigo or self.codigo).strip()
            base = re.sub(r'[\\/:"*?<>|\n\r]+', " ", base).strip()
            return f"{base}_V{self.version}"
        return self.codigo

    # --- Anticipo (S-Finanzas-V2 #E) -------------------------------------

    @property
    def anticipo_monto(self) -> Decimal:
        """Monto del anticipo. Usa override si está, si no calcula del %."""
        if self.anticipo_monto_override is not None and self.anticipo_monto_override > 0:
            return Decimal(self.anticipo_monto_override).quantize(Decimal("0.01"))
        pct = self.anticipo_porcentaje or Decimal("0")
        if pct <= 0:
            return Decimal("0.00")
        total = self.calcular_totales()["total"]
        return (Decimal(total) * pct / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def nota_forma_pago(self) -> str:
        """Última nota del PDF, según el interruptor Anticipo / Un solo pago.

        En modo anticipo respeta el porcentaje capturado en la cotización (por
        si un cliente va al 40%); si no hay ninguno, el default de LC es 50%.
        """
        if self.forma_pago == self.FORMA_CONTADO:
            return "Forma de pago: Un sólo pago."
        pct = self.anticipo_porcentaje or Decimal("0")
        if pct <= 0:
            pct = Decimal("50")
        # 50.00 → «50»; 33.50 → «33.5» (sin ceros de relleno).
        texto = f"{pct.normalize():f}" if isinstance(pct, Decimal) else str(pct)
        return f"Forma de pago: Anticipo {texto}%."

    @property
    def anticipo_pendiente(self) -> bool:
        """True si el anticipo está configurado, cotización aprobada y
        aún no se ha generado la factura del anticipo."""
        return (
            self.estado == "aprobada"
            and self.anticipo_monto > 0
            and self.anticipo_facturado_en is None
        )

    # --- totales (calculados sobre items) --------------------------------

    def calcular_totales(self) -> dict:

        items = list(self.items.all())
        subtotal_items = sum((it.subtotal for it in items), CERO)

        desc_pct = self.descuento_global_porcentaje or CERO
        descuento_global = q2(subtotal_items * desc_pct / Decimal("100"))
        base_impuestos = q2(subtotal_items - descuento_global)

        trasladados = CERO
        retenciones = CERO
        impuestos_detalle: list = []

        if self.regimen_fiscal == "honorarios":
            d = desglose_honorarios(base_impuestos)
            trasladados = d["trasladados"]
            retenciones = d["retenciones"]
            impuestos_detalle = d["impuestos_detalle"]
            total = d["total"]
        elif self.regimen_fiscal == "exento":
            total = base_impuestos
        else:
            for ci in self.impuestos.select_related("tasa").all():
                tasa = ci.tasa
                monto = q2(base_impuestos * tasa.porcentaje / Decimal("100"))
                if tasa.tipo == "retencion":
                    retenciones += monto
                else:
                    trasladados += monto
                impuestos_detalle.append({
                    "id": ci.id,
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
            "base_impuestos": base_impuestos,
            "trasladados": q2(trasladados),
            "retenciones": q2(retenciones),
            "total": total,
            "impuestos_detalle": impuestos_detalle,
        }


class CotizacionItem(models.Model):
    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.CASCADE, related_name="items"
    )
    orden = models.PositiveIntegerField(default=0, db_index=True)

    servicio = models.ForeignKey(
        "el_catalogo.Servicio",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="lineas_cotizacion",
    )
    variacion = models.ForeignKey(
        "el_catalogo.Variacion",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="lineas_cotizacion",
    )
    # LC 2026-07: el NOMBRE del concepto tal como se congeló al generar la
    # versión (el alias del proyecto si lo hubo). Es el título numerado del PDF
    # y la columna «Concepto» del desglose. Vacío en las líneas viejas, que
    # guardaban el nombre dentro de `descripcion` — ver `concepto_visible`.
    concepto = models.CharField(max_length=150, blank=True, default="")
    # Bloque multilínea con las especificaciones que lee el cliente (piezas,
    # material, color, detalles de branding). Se genera al crear la versión y
    # se edita a mano en la página de la cotización.
    descripcion = models.TextField(blank=True, default="")

    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    # #12: unidad consolidada a 'pz' (sin selector). Columnas conservadas por back-compat.
    unidad = models.CharField(max_length=30, default="pz")
    unidad_fk = models.ForeignKey(
        "el_catalogo.Unidad",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="lineas_cotizacion",
        help_text="Catálogo. Si está vacío, se usa la cadena en 'unidad' (legacy).",
    )
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    descuento_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        db_table = "cotizaciones_item"
        ordering = ["cotizacion", "orden", "pk"]

    def __str__(self) -> str:
        return f"{self.cotizacion.codigo} · {self.concepto_visible[:40]}"

    @property
    def concepto_visible(self) -> str:
        """Nombre del concepto — el título numerado y subrayado del PDF.

        Orden (Oscar 2026-07-25: «que se jale del NOMBRE, no de la primera línea
        de las especificaciones»): el `concepto` congelado → el nombre del
        producto del catálogo (+ variación) → y solo si no hay ninguno, el primer
        renglón de `descripcion` (formato viejo, donde el nombre vivía ahí).
        """
        propio = (self.concepto or "").strip()
        if propio:
            return propio
        if self.variacion_id and (vnom := (self.variacion.nombre or "").strip()):
            base = (self.servicio.nombre or "").strip() if self.servicio_id else ""
            if not base or vnom.lower() in base.lower():
                return base or vnom
            return vnom if base.lower() in vnom.lower() else f"{base} · {vnom}"
        if self.servicio_id and (nom := (self.servicio.nombre or "").strip()):
            return nom
        return ((self.descripcion or "").strip().splitlines() or [""])[0].strip()

    @property
    def detalle_lineas(self) -> list[str]:
        """Renglones de especificaciones que van bajo el título en el PDF.

        En el formato viejo (sin `concepto`) el primer renglón de `descripcion`
        ERA el nombre: se quita solo si efectivamente coincide con el título que
        se está imprimiendo, para no comerse una especificación real ahora que
        el título puede venir del producto del catálogo.
        """
        crudo = (self.descripcion or "").strip()
        if not crudo:
            return []
        renglones = crudo.splitlines()
        if (not (self.concepto or "").strip() and renglones
                and renglones[0].strip().lower() == self.concepto_visible.strip().lower()):
            renglones = renglones[1:]
        return [r.strip() for r in renglones if r.strip()]

    @property
    def filas_textarea(self) -> int:
        """Alto del cuadro de especificaciones en la página de la cotización:
        que quepa lo escrito más un renglón libre, sin desbordar la tabla."""
        n = len((self.descripcion or "").splitlines())
        return max(3, min(n + 1, 12))

    @property
    def unidad_label(self) -> str:
        """Etiqueta a mostrar: prefiere la FK del catálogo si está enlazada."""
        if self.unidad_fk_id:
            return self.unidad_fk.nombre
        return self.unidad or ""

    @property
    def subtotal(self) -> Decimal:
        bruto = (self.cantidad or CERO) * (self.precio_unitario or CERO)
        desc = (self.descuento_porcentaje or CERO) / Decimal("100")
        return (bruto * (Decimal("1") - desc)).quantize(Decimal("0.01"))


class CotizacionImpuesto(models.Model):
    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.CASCADE, related_name="impuestos"
    )
    tasa = models.ForeignKey(
        "ajustes.TasaImpositiva", on_delete=models.PROTECT, related_name="cotizaciones"
    )
    aplicado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cotizaciones_impuesto"
        unique_together = (("cotizacion", "tasa"),)
        ordering = ["tasa__orden", "tasa__nombre"]

    def __str__(self) -> str:
        return f"{self.cotizacion.codigo} · {self.tasa.nombre}"
