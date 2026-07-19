from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

from lib.fiscal import REGIMENES_FISCALES, desglose_honorarios, q2

# Enum reflejando el ciclo real del despacho (LC, 2026-05-22).
ESTADOS_PROYECTO = (
    ("por_cotizar", "Por cotizar"),
    ("esperando_respuesta", "Esperando respuesta"),
    ("en_proceso_diseno", "En proceso de diseño"),
    ("en_proceso_produccion", "En proceso de producción"),
    ("entregado", "Entregado"),
    ("cerrado", "Cerrado"),
    ("en_pausa", "En pausa"),
    ("cancelado", "Cancelado"),
)

# 'cerrado' = entregado + pagado + cobrado (cierre total del proyecto).
ESTADOS_TERMINALES = {"entregado", "cerrado", "cancelado"}


class ProyectoActivosManager(models.Manager):
    """Proyectos NO archivados. Para listas, kanban, dashboard y selectores
    (LC 2026-07: archivar oculta proyectos de prueba/duplicados sin borrarlos,
    distinto de «Cancelado» que es un estado real del ciclo)."""

    def get_queryset(self):
        return super().get_queryset().filter(archivado=False)


def generar_codigo_proyecto() -> str:
    """Genera LC-NNNN correlativo (atómico vía select_for_update).

    Decisión S-LC-Feedback-V2: códigos correlativos LC-0001, LC-0002, … en
    lugar de PRY-NNNNNN aleatorio. Para go-live productivo existe el
    management command `resetear_contador_proyectos` que limpia demos y
    deja el contador en LC-0001.
    """
    with transaction.atomic():
        codigos = (
            Proyecto.objects.select_for_update()
            .filter(codigo__startswith="LC-")
            .values_list("codigo", flat=True)
        )
        max_n = 0
        for c in codigos:
            try:
                n = int(c.split("-", 1)[1])
                if n > max_n:
                    max_n = n
            except (ValueError, IndexError):
                continue
        return f"LC-{max_n + 1:04d}"


class Proyecto(models.Model):
    codigo = models.CharField(max_length=12, unique=True, db_index=True, default=generar_codigo_proyecto)
    # Slug para el Sistema de Referencias (#). Espejo del código en minúsculas.
    slug = models.CharField(max_length=80, unique=True)
    # S-LC-Feedback-V5 c9: el slug ahora se basa en el NOMBRE del proyecto.
    # El slug original (basado en código `lc-0001`) se preserva aquí para
    # resolver referencias `#lc-0001` en mensajes históricos.
    slug_legacy = models.CharField(max_length=80, null=True, blank=True, db_index=True)
    nombre = models.CharField(max_length=200)
    cliente = models.ForeignKey("cartera.Cliente", on_delete=models.PROTECT, related_name="proyectos")
    descripcion = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=32, default="por_cotizar", db_index=True)

    # C6 S-LC-Feedback-V6: Inicio y Entrega ahora llevan hora (default 12:00 PM
    # en el form). fecha_real_entrega se conserva como DateField (no se muestra
    # en la página; se setea al marcar "entregado").
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_compromiso = models.DateTimeField(null=True, blank=True)
    fecha_real_entrega = models.DateField(null=True, blank=True)

    monto_estimado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Montos del ciclo comercial (terreno para El Pipeline — S2b).
    # monto_estimado arriba es la primera aproximación; los siguientes se llenan
    # conforme avanza el ciclo. En S2b llegan flujos automáticos.
    monto_cotizado = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Monto formal cotizado al cliente (puede diferir del estimado inicial).",
    )
    monto_facturado = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Suma de lo facturado al cliente para este proyecto.",
    )
    monto_cobrado = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Suma de lo efectivamente cobrado para este proyecto.",
    )
    fecha_ingreso_esperado = models.DateField(
        null=True, blank=True,
        help_text="Fecha en la que se espera cobrar el grueso del proyecto. Usada para proyecciones.",
    )
    # C7 S-LC-Feedback-V6: IVA del proyecto. False = 16% (default); True = exento.
    # Se conserva por compatibilidad; la fuente real es `regimen_fiscal`.
    iva_exento = models.BooleanField(default=False)
    # LC 2026-07: régimen fiscal del proyecto — reemplaza el toggle IVA/exento por
    # un selector IVA (16%) / IVA y Retenciones (honorarios) / Exento. Las
    # cotizaciones y facturas del proyecto lo heredan.
    regimen_fiscal = models.CharField(
        max_length=12, choices=REGIMENES_FISCALES, default="iva", db_index=True
    )

    # LC 2026-07: soft-archive (proyectos de prueba/duplicados). Distinto de
    # «Cancelado» (estado real). Se oculta de listas/kanban/selectores.
    archivado = models.BooleanField(default=False, db_index=True)
    archivado_en = models.DateTimeField(null=True, blank=True)
    archivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="proyectos_archivados",
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="proyectos_creados",
    )

    objects = models.Manager()
    activos = ProyectoActivosManager()

    class Meta:
        db_table = "proyectos_proyecto"
        verbose_name = "proyecto"
        verbose_name_plural = "proyectos"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    def save(self, *args, **kwargs):
        # Si el código es el default y aún no se generó, hacerlo dentro de
        # la transacción para evitar colisiones bajo carga. generar_codigo_proyecto
        # ya hace select_for_update; aquí solo regeneramos si colisiona por
        # llamadas concurrentes que crearon mismo número antes del save.
        if not self.pk and self.codigo and self.codigo.startswith("LC-"):
            for _ in range(5):
                if not Proyecto.objects.filter(codigo=self.codigo).exists():
                    break
                self.codigo = generar_codigo_proyecto()
        if not self.slug:
            from lib.slug import generar_slug_proyecto
            self.slug = generar_slug_proyecto(self)
        super().save(*args, **kwargs)

    # ── Totales de productos (C4 S-LC-Feedback-V6) ───────────────────────────

    # Tasa de IVA fallback (C7). La tasa REAL vive en
    # `ajustes.ConfiguracionFiscal` (editable en Gerencia); se lee vía
    # `iva_tasa_efectiva`. Este constante solo es respaldo si no hay config.
    IVA_TASA = Decimal("0.16")

    @property
    def iva_tasa_efectiva(self) -> Decimal:
        """Fracción de IVA (ej. 0.16) desde la Configuración Fiscal; cae al
        constante si la tabla no existe todavía."""
        try:
            from ajustes.models import ConfiguracionFiscal
            return ConfiguracionFiscal.obtener().iva_fraccion
        except Exception:  # noqa: BLE001
            return self.IVA_TASA

    @property
    def iva_pct_label(self) -> str:
        """Etiqueta legible del IVA, ej. '16%' o '8%'."""
        return f"{float(self.iva_tasa_efectiva * 100):g}%"

    def _productos_calc(self):
        return list(
            self.productos
            .select_related("servicio", "variacion", "proveedor")
            .prefetch_related("procesos__proveedor")
            .all()
        )

    def _productos_incluidos(self):
        """C7: solo las líneas marcadas para entrar en los cálculos de dinero."""
        return [pp for pp in self._productos_calc() if pp.incluir_en_calculo]

    @property
    def productos_incluidos(self):
        """Accesor público (los templates Django no pueden llamar métodos con
        guión bajo) — usado por el desglose del panel Económico (Render-V2)."""
        return self._productos_incluidos()

    @property
    def monto_calculado(self):
        """C7: suma de subtotales de los productos INCLUIDOS (lo que se cobra,
        antes de IVA). Reemplaza al 'monto estimado' manual en la UI."""
        return sum((pp.subtotal for pp in self._productos_incluidos()), Decimal("0.00"))

    # Alias retro-compatible: 'valor_productos' = monto calculado.
    @property
    def valor_productos(self):
        return self.monto_calculado

    @property
    def costo_produccion(self):
        """Costo real de producir los productos incluidos: costo de la línea
        (con merma) MÁS los procesos fijos (impresión + operativos)."""
        return sum(
            (pp.costo_total_con_procesos for pp in self._productos_incluidos()),
            Decimal("0.00"),
        )

    # Alias retro-compatible.
    @property
    def costo_productos(self):
        return self.costo_produccion

    @property
    def regimen_fiscal_label(self) -> str:
        return dict(REGIMENES_FISCALES).get(self.regimen_fiscal, self.regimen_fiscal)

    @property
    def desglose_fiscal(self) -> dict:
        """Desglose de impuestos del proyecto según su régimen fiscal, para el
        panel Económico del sidebar. Devuelve base/iva/ret_isr/ret_iva/
        retenciones/trasladados/total (todos Decimal a 2 decimales)."""
        base = self.monto_calculado
        reg = self.regimen_fiscal
        cero = Decimal("0.00")
        if reg == "exento" or self.iva_exento:
            return {"regimen": "exento", "base": q2(base), "iva": cero,
                    "ret_isr": cero, "ret_iva": cero, "retenciones": cero,
                    "trasladados": cero, "total": q2(base)}
        if reg == "honorarios":
            d = desglose_honorarios(base)
            return {"regimen": "honorarios", "base": q2(base), **d}
        iva = q2(base * self.iva_tasa_efectiva)
        return {"regimen": "iva", "base": q2(base), "iva": iva,
                "ret_isr": cero, "ret_iva": cero, "retenciones": cero,
                "trasladados": iva, "total": q2(base + iva)}

    @property
    def iva_monto(self):
        """IVA trasladado sobre el monto calculado. 0 si es exento (C7)."""
        return self.desglose_fiscal["iva"]

    @property
    def retenciones_monto(self):
        """Total de retenciones (honorarios). 0 en IVA/exento."""
        return self.desglose_fiscal["retenciones"]

    @property
    def monto_a_facturar(self):
        """Total neto — lo que se le facturaría al cliente (con retenciones si
        el régimen es honorarios)."""
        return self.desglose_fiscal["total"]

    @property
    def merma_total(self) -> int:
        return sum(pp.merma for pp in self._productos_incluidos())

    @property
    def utilidad_productos(self):
        """Monto calculado menos el costo de producción (con merma)."""
        return self.monto_calculado - self.costo_produccion

    @property
    def margen_porcentaje(self):
        """% de margen global del proyecto (LC 2026-07): utilidad ÷ monto × 100."""
        base = self.monto_calculado
        if base <= 0:
            return Decimal("0.0")
        return (self.utilidad_productos / base * Decimal("100")).quantize(Decimal("0.1"))

    # ── Saldos de cobro/pago (S-Finanzas-UX) ──────────────────────────────────
    # Los ingresos/egresos se capturan con el monto = TOTAL (con IVA). El
    # "total del proyecto" comparable es `monto_a_facturar` (total con IVA /
    # retenciones según régimen).

    @property
    def ingresos_ligados(self):
        """Ingresos vigentes ligados al proyecto, del más antiguo al más nuevo."""
        return self.ingresos.filter(anulado=False).order_by("fecha", "pk")

    @property
    def total_cobrado_ingresos(self) -> Decimal:
        return sum((i.monto for i in self.ingresos_ligados), Decimal("0.00"))

    @property
    def saldo_por_cobrar(self) -> Decimal:
        """Total a facturar − suma de ingresos ligados (lo que falta cobrar)."""
        return (self.monto_a_facturar - self.total_cobrado_ingresos).quantize(Decimal("0.01"))

    @property
    def total_pagado_egresos(self) -> Decimal:
        return sum(
            (e.monto for e in self.egresos.filter(anulado=False)), Decimal("0.00"),
        )

    @property
    def saldo_por_pagar(self) -> Decimal:
        """Costo de producción − suma de egresos ligados (lo que falta pagar)."""
        return (self.costo_produccion - self.total_pagado_egresos).quantize(Decimal("0.01"))

    # ── Proveedores y gastos derivados de los productos (Render-V1) ───────────

    def deuda_por_proveedor(self):
        """Cuánto se le adeuda a cada proveedor por ESTE proyecto.

        Suma, de los productos INCLUIDOS:
        - costo del proveedor principal del producto = costo_total_linea
        - costo de cada proceso de impresión ligado a un proveedor (fijo o por
          pieza según `por_pieza`)

        Retorna lista de dicts {proveedor, total} ordenada por total desc.
        Los gastos operativos (sin proveedor) NO entran aquí — ver
        `gastos_operativos`. El tipo de entrega (entregan/recogemos) lo aporta
        `ProyectoProveedor` por separado en la UI.
        """
        acumulado: dict[int, dict] = {}
        for pp in self._productos_incluidos():
            if pp.proveedor_id:
                slot = acumulado.setdefault(
                    pp.proveedor_id, {"proveedor": pp.proveedor, "total": Decimal("0.00")}
                )
                slot["total"] += pp.costo_total_linea
            piezas = pp.cantidad + pp.merma
            for proc in pp.procesos.all():
                # Impresión (siempre con proveedor) u operativo con proveedor
                # ligado por @ (ticket UX 2026-07): suma a la deuda de ese proveedor.
                if proc.proveedor_id:
                    slot = acumulado.setdefault(
                        proc.proveedor_id,
                        {"proveedor": proc.proveedor, "total": Decimal("0.00")},
                    )
                    c = Decimal(str(proc.costo or 0))
                    slot["total"] += (c * piezas) if proc.por_pieza else c
        return sorted(acumulado.values(), key=lambda d: d["total"], reverse=True)

    def gastos_operativos(self):
        """Gastos operativos (sin proveedor) de los productos incluidos.

        Lista de dicts {descripcion, costo, producto} para enlistar en los
        gastos del proyecto (clavos, pegamento, viáticos, embalaje…)."""
        filas = []
        for pp in self._productos_incluidos():
            piezas = pp.cantidad + pp.merma
            for proc in pp.procesos.all():
                # Solo operativos SIN proveedor: los que ligan proveedor (@) ya
                # cuentan en `deuda_por_proveedor` (evita doble conteo).
                if proc.tipo == "operativo" and not proc.proveedor_id:
                    c = Decimal(str(proc.costo or 0))
                    filas.append({
                        "descripcion": proc.descripcion or "Gasto operativo",
                        "costo": (c * piezas) if proc.por_pieza else c,
                        "producto": pp,
                    })
        return filas

    @property
    def gastos_operativos_total(self):
        return sum((g["costo"] for g in self.gastos_operativos()), Decimal("0.00"))

    def recalcular_monto_estimado(self, guardar=True):
        """C4/C7: el monto estimado se deriva de los productos INCLUIDOS.
        Si no hay productos, se respeta el valor que ya tuviera."""
        productos = self._productos_incluidos()
        if not self._productos_calc():
            return
        self.monto_estimado = sum((pp.subtotal for pp in productos), Decimal("0.00"))
        if guardar:
            self.save(update_fields=["monto_estimado", "actualizado_en"])

    @property
    def es_terminal(self) -> bool:
        # Lookup DB primero (configurable); fallback al set hardcoded para
        # entornos donde la migración 0007 aún no corrió.
        from .estado import EstadoProyecto
        try:
            obj = EstadoProyecto.objects.only("terminal").get(slug=self.estado)
            return obj.terminal
        except EstadoProyecto.DoesNotExist:
            return self.estado in ESTADOS_TERMINALES

    @property
    def estado_obj(self):
        """Retorna EstadoProyecto correspondiente o None si el slug no existe."""
        from .estado import EstadoProyecto
        try:
            return EstadoProyecto.objects.get(slug=self.estado)
        except EstadoProyecto.DoesNotExist:
            return None

    def get_estado_display(self) -> str:
        """Override del método estándar de Django (que requería choices).

        Lee del modelo EstadoProyecto; fallback al label hardcoded.
        """
        obj = self.estado_obj
        if obj:
            return obj.label
        for slug, label in ESTADOS_PROYECTO:
            if slug == self.estado:
                return label
        return self.estado
