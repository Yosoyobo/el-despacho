from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

# Enum reflejando el ciclo real del despacho (LC, 2026-05-22).
ESTADOS_PROYECTO = (
    ("por_cotizar", "Por cotizar"),
    ("esperando_respuesta", "Esperando respuesta"),
    ("en_proceso_diseno", "En proceso de diseño"),
    ("en_proceso_produccion", "En proceso de producción"),
    ("entregado", "Entregado"),
    ("en_pausa", "En pausa"),
    ("cancelado", "Cancelado"),
)

ESTADOS_TERMINALES = {"entregado", "cancelado"}


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
    iva_exento = models.BooleanField(default=False)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="proyectos_creados",
    )

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

    # Tasa de IVA estándar México (C7). Si en el futuro se quiere configurable,
    # mover a TasaImpositiva sin tocar las properties.
    IVA_TASA = Decimal("0.16")

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
    def iva_monto(self):
        """IVA sobre el monto calculado. 0 si el proyecto es exento (C7)."""
        if self.iva_exento:
            return Decimal("0.00")
        return (self.monto_calculado * self.IVA_TASA).quantize(Decimal("0.01"))

    @property
    def monto_a_facturar(self):
        """Monto calculado + IVA — lo que se le facturaría al cliente."""
        return self.monto_calculado + self.iva_monto

    @property
    def merma_total(self) -> int:
        return sum(pp.merma for pp in self._productos_incluidos())

    @property
    def utilidad_productos(self):
        """Monto calculado menos el costo de producción (con merma)."""
        return self.monto_calculado - self.costo_produccion

    # ── Proveedores y gastos derivados de los productos (Render-V1) ───────────

    def deuda_por_proveedor(self):
        """Cuánto se le adeuda a cada proveedor por ESTE proyecto.

        Suma, de los productos INCLUIDOS:
        - costo del proveedor principal del producto = costo_total_linea
        - costo de cada proceso de impresión ligado a un proveedor (fijo)

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
            for proc in pp.procesos.all():
                if proc.tipo == "impresion" and proc.proveedor_id:
                    slot = acumulado.setdefault(
                        proc.proveedor_id,
                        {"proveedor": proc.proveedor, "total": Decimal("0.00")},
                    )
                    slot["total"] += Decimal(str(proc.costo or 0))
        return sorted(acumulado.values(), key=lambda d: d["total"], reverse=True)

    def gastos_operativos(self):
        """Gastos operativos (sin proveedor) de los productos incluidos.

        Lista de dicts {descripcion, costo, producto} para enlistar en los
        gastos del proyecto (clavos, pegamento, viáticos, embalaje…)."""
        filas = []
        for pp in self._productos_incluidos():
            for proc in pp.procesos.all():
                if proc.tipo == "operativo":
                    filas.append({
                        "descripcion": proc.descripcion or "Gasto operativo",
                        "costo": Decimal(str(proc.costo or 0)),
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
