"""Foto de los Productos involucrados tal como quedaron en cada versión de
cotización (S-Ajustes-Ago12-B, Oscar 2026-08-12).

Oscar: «las tabs v1/v2/etc son para ver/cambiar productos involucrados que
llegaron a ser guardadas dentro del proyecto bajo cada cotización (v) se debería
de guardar todo siempre. A las cotizaciones en sí no agregaremos datos de merma,
costos, proveedores, ya que las cotizaciones son de salida y vista de clientes.»

Por eso el snapshot COMPLETO vive de este lado: `CotizacionItem` congela sólo lo
que ve el cliente (concepto, especificaciones, cantidad, precio, foto), y aquí
se guarda además el lado del costo — merma, costo unitario, proveedor y los
procesos de producción.

**Tabla aparte, a propósito.** `proyecto.productos` alimenta gastos, egresos,
Contaduría, el documento y los chips del Kanban. Meter filas históricas ahí
—con un campo `version`— haría que todo eso contara doble. Si alguna vez se
piensa «mejor un campo `version` en `ProyectoProducto`»: no.

**Los valores se guardan RESUELTOS, nunca heredados.** A diferencia de
`ProyectoProducto`, donde `precio_unitario = NULL` significa «usa el del
catálogo», aquí un nulo significa **desconocido**: si cayera al catálogo, un
cambio de precio de hoy reescribiría lo que se cotizó hace tres meses. Por eso
este modelo NO tiene `precio_efectivo` / `costo_efectivo`: al fotografiar se
escribe el valor ya resuelto, y un nulo se pinta «—».

Los procesos y las ventas van como JSON (lista) y no como dos tablas más porque
el JS de la tarjeta **ya** serializa exactamente esa forma (`serializar()` y
`serializarVentas()` en `proyectos/_form_productos_js.html`), la misma que
consumen `services_procesos.sincronizar_procesos` / `sincronizar_ventas`. Así la
tarjeta del proyecto se reutiliza tal cual para las pestañas.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

CERO = Decimal("0.00")


class ProyectoProductoVersion(models.Model):
    cotizacion = models.ForeignKey(
        "cotizaciones.Cotizacion",
        on_delete=models.CASCADE,
        related_name="productos_version",
    )
    # Línea del cliente que le corresponde. Sirve para EMPUJAR al documento lo
    # que se edite en la pestaña (concepto, especificaciones, cantidad, precio),
    # de modo que el PDF de esa versión siga coincidiendo con lo que se ve.
    # SET_NULL: si la línea se borra, la foto del costo no se pierde con ella.
    item = models.ForeignKey(
        "cotizaciones.CotizacionItem",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="snapshot_proyecto",
    )
    orden = models.PositiveIntegerField(default=0, db_index=True)

    # SET_NULL (no PROTECT como en `ProyectoProducto`): un producto se puede
    # borrar permanentemente del catálogo (permiso `catalogo.eliminar`, sólo
    # super_admin) y eso NO debe quedar bloqueado por un histórico. La foto
    # conserva el nombre en `nombre_proyecto`, así que sobrevive sin el FK.
    servicio = models.ForeignKey(
        "el_catalogo.Servicio",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="en_versiones_proyecto",
    )
    variacion = models.ForeignKey(
        "el_catalogo.Variacion",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="en_versiones_proyecto",
    )
    proveedor = models.ForeignKey(
        "el_catalogo.Proveedor",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="productos_version_proyecto",
    )

    # El alias del producto en el proyecto. Misma semántica que en
    # `ProyectoProducto` (vacío = el nombre del catálogo), para que «Restaurar
    # esta versión en edición» no invente un alias donde no había.
    # 150 = el largo de `ProyectoProducto.nombre_proyecto` y de
    # `CotizacionItem.concepto`; con 200 cabría aquí algo que no cabe allá.
    nombre_proyecto = models.CharField(max_length=150, blank=True, default="")

    cantidad = models.PositiveIntegerField(default=1)
    merma = models.PositiveIntegerField(
        default=0,
        help_text="Piezas extra que se produjeron y no se cobraron.",
    )
    # Nulo = desconocido (ver el docstring del módulo), NO «usa el catálogo».
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    costo_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    # La cuenta escrita del costo («15.75*100»), igual que en la línea viva
    # (`ProyectoProducto.costo_unitario_expr`, LC 2026-08-12). Sin esto, editar
    # o restaurar una versión perdería la cuenta y dejaría sólo su total.
    costo_unitario_expr = models.CharField(max_length=120, blank=True, default="")

    # La Descripción de la línea: la especificación que viaja al documento
    # (LC 2026-08-04 — el campo se sigue llamando `nota` del lado del proyecto).
    nota = models.TextField(blank=True, default="")
    # Foto con la que se cotizó. Vacío = se cae a la del catálogo al pintar.
    imagen_file_id = models.CharField(max_length=100, blank=True, default="")
    incluir_en_calculo = models.BooleanField(default=True)

    # Listas, NO diccionarios: es la forma que serializa el JS de la tarjeta y
    # la que consumen `sincronizar_procesos` / `sincronizar_ventas`, que
    # descartan en silencio cualquier cosa que no sea `list`.
    #   procesos_json → [{tipo, proveedor_id, descripcion, costo, costo_expr, por_pieza}]
    #   ventas_json   → [{descripcion, cantidad, precio}]
    procesos_json = models.JSONField(default=list, blank=True)
    ventas_json = models.JSONField(default=list, blank=True)

    # True = la fila la armó la migración de reconstrucción, no el generador de
    # la versión. El lado del costo (merma, costo, proveedor, procesos) se tomó
    # de la línea que el proyecto tiene HOY, porque la cotización nunca lo
    # guardó. La pestaña lo advierte para que nadie lea un margen histórico que
    # jamás se midió.
    reconstruido = models.BooleanField(default=False)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proyectos_producto_version"
        ordering = ["orden", "pk"]
        verbose_name = "producto de la versión"
        verbose_name_plural = "productos de la versión"
        constraints = [
            # Una foto por línea del cliente. Da idempotencia de regalo: ni la
            # reconstrucción ni un «generar» repetido pueden duplicar filas.
            models.UniqueConstraint(
                fields=["cotizacion", "item"],
                condition=models.Q(item__isnull=False),
                name="ppv_una_foto_por_item",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nombre_visible} ×{self.cantidad}"

    # ── Nombre (espejo de `ProyectoProducto`) ────────────────────────────────

    @property
    def nombre_catalogo(self) -> str:
        """Cómo se llama en el catálogo. Puede haber cambiado desde entonces —
        por eso el alias congelado (`nombre_proyecto`) manda cuando existe."""
        nombre = self.servicio.nombre if self.servicio_id else "Producto"
        if self.variacion_id:
            vnom = (self.variacion.nombre or "").strip()
            if not vnom or vnom.lower() in nombre.lower():
                pass
            elif nombre.lower() in vnom.lower():
                nombre = vnom
            else:
                nombre = f"{nombre} · {vnom}"
        return nombre

    @property
    def nombre_visible(self) -> str:
        """El nombre con el que se presenta esta línea en la pestaña."""
        return (self.nombre_proyecto or "").strip() or self.nombre_catalogo

    # ── Dinero (OJO: no heredan del catálogo) ────────────────────────────────

    @property
    def precio_efectivo(self) -> Decimal:
        """El precio con el que se cotizó. **No cae al catálogo** — a diferencia
        de `ProyectoProducto`, aquí un nulo es «desconocido», no «heredado»: si
        cayera, el precio de hoy reescribiría lo que se cotizó ayer."""
        return Decimal(str(self.precio_unitario)) if self.precio_unitario is not None else CERO

    @property
    def costo_efectivo(self) -> Decimal:
        """El costo con el que se produjo. Tampoco cae al catálogo (ver arriba)."""
        return Decimal(str(self.costo_unitario)) if self.costo_unitario is not None else CERO

    @property
    def imagen_efectiva_file_id(self) -> str:
        """La foto que representa la línea: la congelada o, si no hay, la del
        catálogo (las versiones anteriores a 2026-07-26 no congelaban foto)."""
        propia = (self.imagen_file_id or "").strip()
        if propia:
            return propia
        return (getattr(self.servicio, "imagen_file_id", "") or "").strip()

    @property
    def imagen_es_propia(self) -> bool:
        """True si la foto quedó congelada con la versión (no heredada)."""
        return bool((self.imagen_file_id or "").strip())

    @property
    def piezas_producidas(self) -> int:
        """Cantidad + merma: el divisor de los costos por pieza."""
        return (self.cantidad or 0) + (self.merma or 0)
