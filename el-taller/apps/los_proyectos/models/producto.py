"""Productos/servicios del catálogo involucrados en un proyecto.

Permite mostrar el "resumen compacto" debajo de cada proyecto en la lista
y armar el form de Nuevo Proyecto eligiendo desde el catálogo. Una línea
puede apuntar a Servicio (genérico) o Variacion (específica del producto).
"""

from __future__ import annotations

import contextlib
from decimal import Decimal

from django.db import models

from .. import colores

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
    # LC 2026-08-18 (Oscar): el precio también acepta una CUENTA escrita
    # («150+45», «2400/12»). Aquí queda tal como se escribió; `precio_unitario`
    # guarda el total, que lo saca el SERVIDOR. Mismo contrato que el costo.
    precio_unitario_expr = models.CharField(max_length=120, blank=True, default="")
    costo_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Costo por unidad para este proyecto. Vacío = usa el del catálogo.",
    )
    # LC 2026-08-12 (Oscar): el costo se puede escribir como una CUENTA
    # («15.75*100»). Aquí queda la cuenta tal como se escribió; `costo_unitario`
    # guarda el total, que lo saca el SERVIDOR — mismo contrato que el
    # `costo_expr` de la impresión.
    costo_unitario_expr = models.CharField(max_length=120, blank=True, default="")
    merma = models.PositiveIntegerField(
        default=0,
        help_text="Piezas extra (muestras, control de calidad, regalos). Suman costo, no se cobran.",
    )
    # C7 S-LC-Feedback-V6: si está desmarcado, la línea NO entra en los
    # cálculos de dinero del proyecto (monto calculado / IVA / costo).
    incluir_en_calculo = models.BooleanField(default=True)
    # LC 2026-08-17 (Oscar): el OJO de la Opción A. Distinto de
    # `incluir_en_calculo`: éste decide si la opción se IMPRIME en la cotización.
    # Con escalas de volumen se puede querer cotizar sólo 100 y 200 piezas y no
    # la cantidad base con la que se armó la línea. Ver `models/escala.py`.
    visible_pdf = models.BooleanField(default=True)
    # LC 2026-08-04 (Oscar): esta «nota corta» pasó a ser la **DESCRIPCIÓN** del
    # elemento — la especificación que viaja a la cotización (colores, medidas,
    # dónde va el bordado…). Por eso deja de ser un renglón de 200 caracteres y
    # acepta varias líneas. El nombre del campo se conserva para no arrastrar una
    # migración de rename por todo el repo (undo, duplicar, el mini-Chalán);
    # lo que cambia es su significado y su etiqueta visible.
    # Ver `apps.cotizaciones.descripcion.esqueleto`.
    nota = models.TextField(blank=True, default="")
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

    # LC 2026-08-18 (Oscar): «los necesito 100% variados y contrastados, y
    # sólidamente ligados a cada uno de sus productos». El color se reparte UNA
    # vez —el primero libre de `colores.PALETA`, en orden— y se guarda aquí, que
    # es lo que lo vuelve inamovible: arrastrar, apagar o borrar otra línea ya no
    # lo mueve. Si el nombre o la descripción mencionan un color, ése manda sobre
    # éste (ver `color_efectivo`).
    color = models.CharField(max_length=7, blank=True, default="")

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
        # LC 2026-08-04 (Oscar): «prender y apagar toggles no debe cambiar el
        # orden». Se quitó `-incluir_en_calculo` del ordering — mandaba las
        # incluidas al tope, así que apagar una línea la reacomodaba al recargar.
        # El orden lo manda SOLO el arrastre (`orden`), y por antigüedad al final.
        ordering = ["orden", "creado_en"]
        verbose_name = "producto del proyecto"
        verbose_name_plural = "productos del proyecto"

    def __str__(self) -> str:
        return f"{self.nombre_visible} ×{self.cantidad}"

    def save(self, *args, **kwargs):
        """Reparte el color de la tarjeta la primera vez que se guarda la línea.

        Se hace aquí y no en el form para que valga por TODAS las vías de alta:
        el formset del detalle, el modal de agregar, duplicar, el mini-Chalán y
        los ejecutores del Dictado. Es una consulta por alta, y sólo cuando el
        color está vacío. Defensivo: si algo falla, la línea se guarda igual y
        el color cae al derivado del nombre.
        """
        if not self.color and self.proyecto_id:
            with contextlib.suppress(Exception):
                # Cuentan como ocupados tanto el color repartido a cada hermana
                # como el que le dicta su nombre: si otra línea ya se llama
                # «Bandana roja», el rojo está tomado aunque su columna `color`
                # diga otra cosa. Una sola consulta, sólo al dar de alta.
                hermanas = (
                    ProyectoProducto.objects.filter(proyecto_id=self.proyecto_id)
                    .exclude(pk=self.pk)
                    .values_list("color", "nombre_proyecto", "nota", "servicio__nombre")
                )
                usados = [
                    colores.color_del_texto(alias or catalogo, nota) or color
                    for color, alias, nota, catalogo in hermanas
                ]
                self.color = colores.elegir_color_libre(usados)
        super().save(*args, **kwargs)

    @property
    def color_asignado(self) -> str:
        """El color que se le repartió, sin la regla del nombre.

        Es al que vuelve la tarjeta si se le quita el color del nombre: el front
        lo usa como base para repintarla en vivo mientras escribes.
        """
        return colores.normalizar(self.color) or colores.color_estable(self.nombre_visible)

    @property
    def color_efectivo(self) -> str:
        """El HEX con el que se pinta la tarjeta de este producto.

        Manda el color que menciona el texto («Playera negra» sale en negro);
        si no menciona ninguno, el que se le repartió al darla de alta; y si es
        una línea vieja que todavía no tiene, uno derivado de su nombre para que
        nunca aparezca sin identidad.
        """
        return colores.color_del_texto(self.nombre_visible, self.nota) or self.color_asignado

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
        if self.cantidad_efectiva > 1:
            return f"{base} ×{self.cantidad_efectiva}"
        return base

    # ── Escalas de volumen (LC 2026-08-17) ───────────────────────────────────

    @property
    def escala_activa(self):
        """La escala que manda el dinero de esta línea, o None si manda la
        Opción A (la fila principal). Recorre `escalas.all()` para aprovechar el
        prefetch; la unicidad la garantiza el constraint del modelo.

        Una línea SIN GUARDAR no tiene escalas (y preguntarle por ellas
        levantaría `ValueError`): manda la Opción A. Pasa de verdad — la tarjeta
        en blanco del formset lee `precio_efectivo` para su resumen.
        """
        if not self.pk:
            return None
        for e in self.escalas.all():
            if e.activa:
                return e
        return None

    @property
    def tiene_escalas(self) -> bool:
        return bool(self.pk) and bool(self.escalas.all())

    def opciones_documento(self) -> list:
        """Las opciones que se IMPRIMEN, la activa primero.

        La activa va al frente porque es la que carga el concepto, la
        descripción y la foto del bloque —y la única que suma al total—; las
        demás la siguen en el orden en que se acomodaron en la tarjeta. Cada
        elemento es la propia escala, o `None` para la Opción A (que se lee de
        los campos de la línea).
        """
        if not self.pk:
            return [None]
        activa = self.escala_activa
        # Se compara por pk y NO por identidad: sin prefetch, `escalas.all()`
        # vuelve a consultar y devuelve otro objeto Python para la misma fila —
        # con `is not` la activa se colaba dos veces en el documento.
        activa_pk = activa.pk if activa is not None else None
        visibles = [e for e in self.escalas.all()
                    if e.visible_pdf and e.pk != activa_pk]
        if activa is not None:
            opciones = [activa]
            if self.visible_pdf:
                opciones.append(None)     # la Opción A como alternativa
            opciones += visibles
        else:
            opciones = ([None] if self.visible_pdf else []) + visibles
        # El formato nunca se queda sin renglón: si apagaron TODOS los ojos, se
        # imprime la opción que manda (es la que cuadra con el total).
        return opciones or [activa]

    # ── Precio / costo / merma (C4 S-LC-Feedback-V6) ──────────────────────────
    #
    # LC 2026-08-17: `*_propio` es lo de la LÍNEA (override del proyecto o
    # catálogo) y `*_efectivo` es lo que de verdad cuenta, que puede venir de la
    # escala activa. Todo el proyecto —monto, costo, margen, egresos, la
    # cotización, los chips del Kanban— lee los `*_efectivo` / `*_efectiva`, así
    # que las escalas se propagan sin tocar a sus consumidores.

    @property
    def precio_propio(self) -> Decimal:
        """Precio unitario de la línea: override del proyecto o el del catálogo."""
        if self.precio_unitario is not None:
            return Decimal(str(self.precio_unitario))
        base = self.servicio.precio_base if self.servicio_id else None
        return Decimal(str(base)) if base is not None else CERO

    @property
    def costo_propio(self) -> Decimal:
        """Costo unitario de la línea: override del proyecto o, si no, el del
        catálogo (costo de la variación si existe, si no el del servicio)."""
        if self.costo_unitario is not None:
            return Decimal(str(self.costo_unitario))
        if self.variacion_id:
            return Decimal(str(self.variacion.costo_total or 0))
        base = self.servicio.costo if self.servicio_id else None
        return Decimal(str(base)) if base is not None else CERO

    @property
    def precio_efectivo(self) -> Decimal:
        """Precio unitario que cuenta: el de la escala activa, o el de la línea."""
        escala = self.escala_activa
        return escala.precio_efectivo if escala else self.precio_propio

    @property
    def costo_efectivo(self) -> Decimal:
        """Costo unitario que cuenta: el de la escala activa, o el de la línea."""
        escala = self.escala_activa
        return escala.costo_efectivo if escala else self.costo_propio

    @property
    def cantidad_efectiva(self) -> int:
        """Piezas que se cobran: las de la escala activa, o las de la línea."""
        escala = self.escala_activa
        return int(escala.cantidad if escala else (self.cantidad or 0))

    @property
    def merma_efectiva(self) -> int:
        """Merma que cuenta: la de la escala activa, o la de la línea."""
        escala = self.escala_activa
        return int(escala.merma if escala else (self.merma or 0))

    @property
    def piezas_efectivas(self) -> int:
        """Piezas a producir (cantidad + merma) de la opción que manda."""
        return self.cantidad_efectiva + self.merma_efectiva

    @property
    def subtotal(self) -> Decimal:
        """Lo que se le cobra al cliente por el PRODUCTO (precio × cantidad).
        La merma NO se cobra, por eso no entra aquí; los procesos de venta
        tampoco — van aparte en `subtotal_ventas`."""
        return self.precio_efectivo * self.cantidad_efectiva

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
        return self.costo_efectivo * self.merma_efectiva

    @property
    def costo_total_linea(self) -> Decimal:
        """Costo real de producir la línea: incluye las piezas de merma.
        NO incluye los procesos (esos son montos fijos aparte)."""
        return self.costo_efectivo * self.piezas_efectivas

    # ── Procesos / impresión (S-LC-Proyecto-Render-V1) ───────────────────────

    @property
    def costo_procesos(self) -> Decimal:
        """Suma de los procesos de esta línea (impresión + operativos). Cada
        proceso es fijo o por pieza (× cantidad + merma) según `por_pieza`.
        Usa los procesos precargados si los hay.

        Con una escala activa el cálculo se delega en ella: puede pisar el costo
        de impresión y traer sus propios costos extra (ver `models/escala.py`).
        """
        escala = self.escala_activa
        if escala is not None:
            return escala.costo_procesos
        piezas = self.piezas_efectivas
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
        """Lo que cuesta CADA pieza producida, con todo incluido.

        LC 2026-08-04 (Oscar, urgente): la tarjeta mostraba el costo del producto
        pelón como «costo unitario», sin la impresión ni los procesos repartidos.
        Aquí se suma todo lo que cuesta una pieza: el producto, la impresión y los
        procesos fijos divididos.

        El divisor son las piezas **producidas** (`cantidad + merma`), no las que
        se cobran (Oscar: «el costo unitario del producto no debe de sumar la merma
        diferida — o sea cada pz de merma tiene el mismo costo unitario»). Una
        pieza de merma cuesta lo mismo que una vendible, así que la merma **no se
        amortiza** en el costo por pieza; su pérdida aparece donde corresponde, en
        `utilidad` y `margen_porcentaje`, que son totales.

        Consecuencia esperada: `utilidad_unitaria × cantidad` **no** da `utilidad`
        — lo que falta es lo que se perdió produciendo la merma. Es correcto, no un
        bug: el costo por pieza habla de UNA pieza; la merma es un total.
        """
        piezas = self.piezas_efectivas
        if piezas <= 0:
            return CERO
        return self.costo_total_con_procesos / Decimal(str(piezas))

    @property
    def utilidad_unitaria(self) -> Decimal:
        """Ganancia por pieza: precio − costo unitario real (con todo incluido)."""
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
