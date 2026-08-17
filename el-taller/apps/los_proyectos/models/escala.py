"""Escalas de volumen de un producto del proyecto (LC 2026-08-17, Oscar).

Un mismo producto se cotiza a varias cantidades: 70 pz a $195, 100 a $175, 200
a $160, y el cliente escoge. La **Opción A es la fila principal de la tarjeta**
(el propio `ProyectoProducto`, no una fila más); cada escala es una alternativa
B, C, D…

Dos interruptores por opción, que NO son lo mismo:

- **El radio (`activa`)**: cuál calcula el dinero del proyecto —monto, costo,
  margen, egresos, la cotización—. Sólo puede haber una activa por producto y
  lo garantiza un `UniqueConstraint` parcial en la base, no sólo el JS. Ninguna
  activa = manda la Opción A.
- **El ojo (`visible_pdf`)**: si la opción se imprime en la propuesta. Apagado,
  la opción existe para el despacho pero el cliente no la ve.

**Un nulo significa «hereda de la Opción A»**, igual que en `ProyectoProducto`
un nulo hereda del catálogo. Es deliberado que no sea «vacío o 0 heredan»: un 0
escrito es un valor legítimo («esta opción no lleva impresión») y se respeta
como cero. La resolución vive en las propiedades `*_efectivo`.

El producto, el alias, la descripción, la foto, el proveedor y los procesos de
venta son del PADRE: una escala sólo cambia cuánto se hace, cuánta merma, a cómo
se vende y cuánto cuesta. Los procesos operativos del padre también se heredan
(se recalculan con las piezas de la escala); la impresión se puede pisar con un
costo propio, y `extras_json` guarda los costos que se agregan con el «+» de la
sub-fila —montos pelones, sin descripción ni proveedor, porque ésos los hereda
de la Opción A—.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

CERO = Decimal("0.00")

# Tope de opciones por producto (A + 6 escalas alcanzan de sobra para una
# cotización por volumen, y acotan el ancho del documento).
MAX_ESCALAS = 6
# Tope de costos extra por escala (los que agrega el «+» de la sub-fila).
MAX_EXTRAS = 6


class ProyectoProductoEscala(models.Model):
    producto = models.ForeignKey(
        "proyectos.ProyectoProducto",
        on_delete=models.CASCADE,
        related_name="escalas",
    )
    orden = models.PositiveSmallIntegerField(default=0)
    cantidad = models.PositiveIntegerField(default=1)
    merma = models.PositiveIntegerField(
        default=0,
        help_text="Piezas extra de ESTA escala. Suman costo, no se cobran.",
    )
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Precio por unidad de esta escala. Vacío = el de la Opción A.",
    )
    costo_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Costo por unidad de esta escala. Vacío = el de la Opción A.",
    )
    # La cuenta escrita («15.75*100»); `costo_unitario` guarda su total, que lo
    # saca el servidor. Mismo contrato que en `ProyectoProducto`.
    costo_unitario_expr = models.CharField(max_length=120, blank=True, default="")
    # Impresión: sólo el costo. El PROVEEDOR es el de la Opción A — una escala no
    # cambia con quién se imprime, cambia cuánto cuesta imprimir ese volumen.
    impresion_costo = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Costo de impresión de esta escala. Vacío = el de la Opción A.",
    )
    impresion_costo_expr = models.CharField(max_length=120, blank=True, default="")
    impresion_por_pieza = models.BooleanField(default=False)
    # Costos extra del «+» de la sub-fila: lista de
    # {"costo": "35.00", "costo_expr": "", "por_pieza": false}.
    extras_json = models.JSONField(default=list, blank=True)
    activa = models.BooleanField(
        default=False,
        help_text="Esta escala es la que calcula el dinero del proyecto.",
    )
    visible_pdf = models.BooleanField(
        default=True,
        help_text="Esta escala se imprime en la cotización.",
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proyectos_producto_escala"
        ordering = ["orden", "creado_en"]
        verbose_name = "escala de volumen del producto"
        verbose_name_plural = "escalas de volumen del producto"
        constraints = [
            # La regla de negocio («sólo 1 opción activa por tarjeta») en la
            # base, no sólo en el JS: dos escalas activas harían que el monto
            # del proyecto dependiera del orden de lectura.
            models.UniqueConstraint(
                fields=["producto"],
                condition=models.Q(activa=True),
                name="escala_activa_unica_por_producto",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.letra}: {self.cantidad} pz"

    # ── Identidad ────────────────────────────────────────────────────────────

    @property
    def letra(self) -> str:
        """B, C, D… — la Opción A es la fila principal de la tarjeta. El
        sanitizador renumera `orden` de forma contigua desde 0."""
        indice = min(int(self.orden or 0), 24)
        return chr(ord("B") + indice)

    @property
    def etiqueta(self) -> str:
        return f"{self.cantidad} pz"

    # ── Dinero: lo propio, y lo que se hereda de la Opción A ─────────────────

    @property
    def precio_efectivo(self) -> Decimal:
        """Precio unitario de la escala; si va vacío, el de la Opción A."""
        if self.precio_unitario is not None:
            return Decimal(str(self.precio_unitario))
        return self.producto.precio_propio

    @property
    def costo_efectivo(self) -> Decimal:
        """Costo unitario de la escala; si va vacío, el de la Opción A."""
        if self.costo_unitario is not None:
            return Decimal(str(self.costo_unitario))
        return self.producto.costo_propio

    @property
    def piezas(self) -> int:
        """Piezas a producir de esta escala (cantidad + merma)."""
        return (self.cantidad or 0) + (self.merma or 0)

    @property
    def subtotal(self) -> Decimal:
        """Lo que se le cobra al cliente por el PRODUCTO a esta cantidad. Es lo
        que se imprime en el renglón de la escala en la cotización."""
        return self.precio_efectivo * (self.cantidad or 0)

    @property
    def subtotal_con_ventas(self) -> Decimal:
        """El producto más los procesos de venta del padre (Ponchado, arte…),
        que se cobran igual con cualquier escala. Es el MONTO de su pie."""
        return self.subtotal + self.producto.subtotal_ventas

    @property
    def costo_procesos(self) -> Decimal:
        """Procesos de producción con las piezas de ESTA escala.

        La impresión es la propia si se capturó, si no la de la Opción A; los
        gastos operativos del padre se heredan tal cual (recalculados con estas
        piezas), y encima van los `extras_json` de la escala.
        """
        piezas = self.piezas
        total = CERO

        costo_imp, por_pieza_imp = self._impresion_efectiva()
        total += (costo_imp * piezas) if por_pieza_imp else costo_imp

        for p in self.producto.procesos.all():
            if p.tipo == "impresion":
                continue          # la impresión ya se contó (propia o heredada)
            c = Decimal(str(p.costo or 0))
            total += (c * piezas) if p.por_pieza else c

        for extra in self.extras():
            c = extra["costo"]
            total += (c * piezas) if extra["por_pieza"] else c
        return total

    def _impresion_efectiva(self) -> tuple[Decimal, bool]:
        """`(costo, por_pieza)` de la impresión: la propia, o la de la Opción A."""
        if self.impresion_costo is not None:
            return Decimal(str(self.impresion_costo)), bool(self.impresion_por_pieza)
        for p in self.producto.procesos.all():
            if p.tipo == "impresion":
                return Decimal(str(p.costo or 0)), bool(p.por_pieza)
        return CERO, False

    def extras(self) -> list[dict]:
        """Los costos extra, normalizados y tolerantes a basura en el JSON."""
        salida = []
        for fila in (self.extras_json or [])[:MAX_EXTRAS]:
            if not isinstance(fila, dict):
                continue
            try:
                costo = Decimal(str(fila.get("costo") or 0)).quantize(Decimal("0.01"))
            except (ArithmeticError, ValueError, TypeError):
                continue
            salida.append({
                "costo": costo,
                "costo_expr": str(fila.get("costo_expr") or "")[:120],
                "por_pieza": bool(fila.get("por_pieza")),
            })
        return salida

    @property
    def costo_total(self) -> Decimal:
        """Costo real de producir esta escala: producto (con merma) + procesos."""
        return self.costo_efectivo * self.piezas + self.costo_procesos

    @property
    def costo_unitario_real(self) -> Decimal:
        """Lo que cuesta CADA pieza producida de esta escala, con todo incluido.

        El divisor son las piezas producidas, igual que en `ProyectoProducto`:
        una pieza de merma cuesta lo mismo que una vendible, así que la merma no
        se amortiza aquí — su pérdida vive en `utilidad`.
        """
        piezas = self.piezas
        if piezas <= 0:
            return CERO
        return self.costo_total / Decimal(str(piezas))

    @property
    def utilidad_unitaria(self) -> Decimal:
        return self.precio_efectivo - self.costo_unitario_real

    @property
    def utilidad(self) -> Decimal:
        return self.subtotal_con_ventas - self.costo_total

    @property
    def margen_porcentaje(self) -> Decimal:
        sub = self.subtotal_con_ventas
        if sub <= 0:
            return CERO
        return (self.utilidad / sub * Decimal("100")).quantize(Decimal("0.1"))
