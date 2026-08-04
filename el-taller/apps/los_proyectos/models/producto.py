"""Productos/servicios del catálogo involucrados en un proyecto.

Permite mostrar el "resumen compacto" debajo de cada proyecto en la lista
y armar el form de Nuevo Proyecto eligiendo desde el catálogo. Una línea
puede apuntar a Servicio (genérico) o Variacion (específica del producto).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

CERO = Decimal("0.00")


class ProyectoProducto(models.Model):
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", on_delete=models.CASCADE, related_name="productos"
    )
    servicio = models.ForeignKey(
        "el_catalogo.Servicio", on_delete=models.PROTECT, related_name="en_proyectos"
    )
    variacion = models.ForeignKey(
        "el_catalogo.Variacion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="en_proyectos",
    )
    # S-LC-Proyecto-Render-V1: proveedor principal del producto (fila
    # "PROVEEDOR" del render). Su costo unitario es `costo_unitario`. El monto
    # se le adeuda a este proveedor (ver Proyecto.deuda_por_proveedor).
    proveedor = models.ForeignKey(
        "el_catalogo.Proveedor",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="productos_proyecto",
    )
    # LC 2026-07 (Oscar): nombre del producto DENTRO de este proyecto. El
    # despacho compra «TShirt Oversize Color» a Crea Blanks y la vende como
    # «TShirt Modelo Janet» — el alias es lo que ve el cliente en el proyecto y
    # en la cotización, mientras el FK a `servicio` y sus procesos conservan de
    # qué está hecha. Vacío = se usa el nombre del catálogo.
    nombre_proyecto = models.CharField(
        max_length=150, blank=True, default="",
        help_text="Cómo se llama este producto en este proyecto. Vacío = el nombre del catálogo.",
    )
    cantidad = models.PositiveIntegerField(default=1)
    # C4 S-LC-Feedback-V6: precio/costo por proyecto (override). Si quedan en
    # null, se heredan del catálogo (servicio.precio_base / costo de la
    # variación o servicio). `merma` = piezas extra que se fabrican para ESTE
    # proyecto: cuentan al costo pero NO se le cobran al cliente.
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Precio por unidad para este proyecto. Vacío = usa el del catálogo.",
    )
    costo_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Costo por unidad para este proyecto. Vacío = usa el del catálogo.",
    )
    merma = models.PositiveIntegerField(
        default=0,
        help_text="Piezas extra (muestras, control de calidad, regalos). Suman costo, no se cobran.",
    )
    # C7 S-LC-Feedback-V6: si está desmarcado, la línea NO entra en los
    # cálculos de dinero del proyecto (monto calculado / IVA / costo).
    incluir_en_calculo = models.BooleanField(default=True)
    nota = models.CharField(max_length=200, blank=True, default="")
    # LC Fase 2: orden manual (drag & drop) de las tarjetas en el detalle. Las
    # incluidas se muestran primero; entre iguales, por este `orden` ascendente.
    orden = models.PositiveIntegerField(default=0, db_index=True)

    # LC 2026-07-26 (Oscar): foto de ESTE uso del producto. La imagen se sube o
    # se pega desde la tarjeta del proyecto; si la línea tiene alias
    # (`nombre_proyecto`) la foto se guarda aquí —es «otro» producto para el
    # cliente—, y si no, se guarda en el catálogo (`Servicio.imagen_file_id`).
    # Vacío = se usa la del catálogo (ver `imagen_efectiva_file_id`).
    imagen_file_id = models.CharField(max_length=100, blank=True, default="")
    imagen_url = models.URLField(max_length=500, blank=True, default="")

    # B (2026-06-07): Egreso generado en Tesorería cuando el proyecto pasa a
    # producción. Marca de idempotencia — una línea con egreso no vuelve a
    # generar. SET_NULL: si el egreso se borra físicamente, la línea queda sin
    # marca (podría regenerarse). Ver apps.los_proyectos.signals_egresos.
    egreso = models.ForeignKey(
        "tesoreria.Egreso",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="lineas_proyecto",
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proyectos_producto"
        # LC Fase 2: incluidas primero (toggle On sube al tope), luego por el
        # orden manual del drag & drop, y por antigüedad al final.
        ordering = ["-incluir_en_calculo", "orden", "creado_en"]
        verbose_name = "producto del proyecto"
        verbose_name_plural = "productos del proyecto"

    def __str__(self) -> str:
        return f"{self.nombre_visible} ×{self.cantidad}"

    @property
    def nombre_catalogo(self) -> str:
        """Cómo se llama en el catálogo (lo que realmente se compra)."""
        nombre = self.servicio.nombre if self.servicio_id else "Producto"
        if self.variacion_id:
            # Higiene (Fase 3 §1.4): nunca «X · X». Si uno de los dos ya
            # contiene al otro, se queda el más informativo.
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
        """El nombre con el que se presenta: el alias del proyecto si lo hay,
        si no el del catálogo. **Fuente única** — de aquí lo toman la tarjeta,
        la lista, el Kanban y la cotización."""
        return (self.nombre_proyecto or "").strip() or self.nombre_catalogo

    # ── Imagen (LC 2026-07-26) ───────────────────────────────────────────────

    @property
    def imagen_efectiva_file_id(self) -> str:
        """La foto que representa esta línea: la propia si la tiene, si no la
        del catálogo. **Fuente única** — de aquí la toman la tarjeta, el
        historial de usos y el documento de la cotización."""
        propia = (self.imagen_file_id or "").strip()
        if propia:
            return propia
        return (getattr(self.servicio, "imagen_file_id", "") or "").strip()

    @property
    def imagen_es_propia(self) -> bool:
        """True si la foto es de este uso (no la heredada del catálogo)."""
        return bool((self.imagen_file_id or "").strip())

    @property
    def imagen_destino(self) -> str:
        """A dónde iría una foto nueva: `uso` si la línea tiene alias (es «otro»
        producto para el cliente), `catalogo` si no. Lo decide el modelo para
        que la vista y la UI digan lo mismo."""
        return "uso" if (self.nombre_proyecto or "").strip() else "catalogo"

    @property
    def etiqueta(self) -> str:
        """Etiqueta compacta para el resumen de lista de proyectos."""
        base = self.nombre_visible
        if self.cantidad > 1:
            return f"{base} ×{self.cantidad}"
        return base

    # ── Precio / costo / merma (C4 S-LC-Feedback-V6) ──────────────────────────

    @property
    def precio_efectivo(self) -> Decimal:
        """Precio unitario: override del proyecto o, si no, el del catálogo."""
        if self.precio_unitario is not None:
            return Decimal(str(self.precio_unitario))
        base = self.servicio.precio_base if self.servicio_id else None
        return Decimal(str(base)) if base is not None else CERO

    @property
    def costo_efectivo(self) -> Decimal:
        """Costo unitario: override del proyecto o, si no, el del catálogo
        (costo de la variación si existe, si no el del servicio)."""
        if self.costo_unitario is not None:
            return Decimal(str(self.costo_unitario))
        if self.variacion_id:
            return Decimal(str(self.variacion.costo_total or 0))
        base = self.servicio.costo if self.servicio_id else None
        return Decimal(str(base)) if base is not None else CERO

    @property
    def subtotal(self) -> Decimal:
        """Lo que se le cobra al cliente por el PRODUCTO (precio × cantidad).
        La merma NO se cobra, por eso no entra aquí; los procesos de venta
        tampoco — van aparte en `subtotal_ventas`."""
        return self.precio_efectivo * self.cantidad

    # ── Procesos de VENTA (LC 2026-07-26) ────────────────────────────────────

    @property
    def subtotal_ventas(self) -> Decimal:
        """Suma de los procesos de venta de la línea (Ponchado, arte…). Son cobros
        al cliente que se facturan como líneas propias de la cotización."""
        return sum((v.subtotal for v in self.ventas.all()), CERO)

    @property
    def subtotal_con_ventas(self) -> Decimal:
        """TODO lo que se le cobra al cliente por esta línea: el producto más sus
        procesos de venta. **Fuente única** del monto del proyecto."""
        return self.subtotal + self.subtotal_ventas

    @property
    def merma_costo(self) -> Decimal:
        """Costo de las piezas de merma (costo × merma)."""
        return self.costo_efectivo * self.merma

    @property
    def costo_total_linea(self) -> Decimal:
        """Costo real de producir la línea: incluye las piezas de merma.
        NO incluye los procesos (esos son montos fijos aparte)."""
        return self.costo_efectivo * (self.cantidad + self.merma)

    # ── Procesos / impresión (S-LC-Proyecto-Render-V1) ───────────────────────

    @property
    def costo_procesos(self) -> Decimal:
        """Suma de los procesos de esta línea (impresión + operativos). Cada
        proceso es fijo o por pieza (× cantidad + merma) según `por_pieza`.
        Usa los procesos precargados si los hay."""
        piezas = self.cantidad + self.merma
        total = CERO
        for p in self.procesos.all():
            c = Decimal(str(p.costo or 0))
            total += (c * piezas) if p.por_pieza else c
        return total

    @property
    def costo_total_con_procesos(self) -> Decimal:
        """Costo de la línea (producto + merma) más sus procesos fijos."""
        return self.costo_total_linea + self.costo_procesos

    @property
    def costo_unitario_real(self) -> Decimal:
        """Lo que cuesta CADA pieza que se cobra, con todo incluido.

        LC 2026-08-04 (Oscar, urgente): la tarjeta mostraba el costo del producto
        pelón como «costo unitario», ignorando la merma y los procesos. El costo
        real por pieza reparte TODO el costo de producción entre las piezas que
        se **cobran** (`cantidad`), no entre las producidas: la merma no se le
        factura al cliente, así que la absorben las piezas vendidas. De ahí que
        `utilidad_unitaria × cantidad` cuadre con la utilidad de la línea.
        """
        if self.cantidad <= 0:
            return CERO
        return self.costo_total_con_procesos / Decimal(str(self.cantidad))

    @property
    def utilidad_unitaria(self) -> Decimal:
        """Ganancia por pieza vendida: precio − costo unitario real."""
        return self.precio_efectivo - self.costo_unitario_real

    @property
    def utilidad(self) -> Decimal:
        """Lo cobrado (producto + procesos de venta) menos el costo real
        (merma + procesos de producción)."""
        return self.subtotal_con_ventas - self.costo_total_con_procesos

    @property
    def margen_porcentaje(self) -> Decimal:
        """% de margen de la línea (LC 2026-07): utilidad ÷ cobrado × 100.
        La merma ya está restada como pérdida directa dentro de `utilidad`."""
        sub = self.subtotal_con_ventas
        if sub <= 0:
            return CERO
        return (self.utilidad / sub * Decimal("100")).quantize(Decimal("0.1"))
