"""Lo que un cliente puede ver — y NADA más. Fuente única de las vistas.

**Cada función recibe el `cliente` de la sesión** (`request.cliente`, lo pone el
middleware) y filtra por él. Ninguna vista busca un objeto por su id a secas:
todas pasan por aquí, así que un id ajeno en la URL da 404, no el documento de
otro cliente. Es la regla más importante del portal y tiene candado con dos
clientes en `tests/recepcion/test_aislamiento.py`.

**Qué NO sale nunca**, aunque el modelo lo tenga: costos, proveedores, utilidad
y margen, notas y comentarios internos, quién del equipo lo hizo, motivos de
cancelación. Por eso aquí se arman diccionarios con los campos permitidos en vez
de pasarle el modelo entero a la plantilla: una plantilla que mañana escriba
`{{ p.costo_produccion }}` no encuentra nada que pintar.

**Decisiones de qué se ve** (S5, 2026-09-29):

- Proyectos **archivados**: nunca. Archivar es para pruebas y duplicados.
- Proyectos **cancelados**: tampoco. El cliente ya sabe que no va, y el motivo
  de la cancelación es una nota interna; enseñarlos sólo llenaría su lista.
- La **fecha de entrega** se enseña a partir de «En diseño»: antes es una fecha
  tentativa del equipo (la misma regla con la que el Calendario la cuenta como
  compromiso, `slugs_con_compromiso_visible`).
- **Productos**: sólo las líneas que entran en la cuenta (`incluir_en_calculo`);
  las apagadas son alternativas o borradores del equipo.
- **Cotizaciones**: sólo las que ya se le mandaron (fase enviada, ganada o
  perdida). Las que el equipo arma todavía y las anuladas no se ven.
- **Facturas**: las emitidas (o con su CFDI encima: Learning Center sube el CFDI
  y a veces no pica «Emitir»). Borradores sin CFDI y canceladas, no.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Q

CERO = Decimal("0.00")

# ── Proyectos ────────────────────────────────────────────────────────────────

#: El ciclo de Learning Center dicho como se le dice a un cliente. Un estado que
#: el despacho agregue en Gerencia y no esté aquí sale como «En proceso»: su
#: nombre lo escribió el equipo para el equipo.
ESTADO_PARA_CLIENTE: dict[str, tuple[str, str, int]] = {
    # slug: (texto, tono, paso 1-4)
    "por_cotizar": ("Preparando tu cotización", "azul", 1),
    "esperando_respuesta": ("Esperando tu respuesta", "ambar", 1),
    "en_proceso_diseno": ("En diseño", "marca", 2),
    "en_proceso_produccion": ("En producción", "marca", 3),
    "entregado": ("Entregado", "verde", 4),
    "cerrado": ("Terminado", "verde", 4),
    "en_pausa": ("En pausa", "gris", 0),
}
PASOS = ("Cotización", "Diseño", "Producción", "Entrega")
ESTADOS_OCULTOS = frozenset({"cancelado"})
ESTADOS_TERMINADOS = frozenset({"entregado", "cerrado"})


def estado_para_cliente(slug: str) -> tuple[str, str, int]:
    return ESTADO_PARA_CLIENTE.get(slug, ("En proceso", "marca", 2))


@dataclass
class ProyectoCliente:
    pk: int
    codigo: str
    nombre: str
    estado: str
    tono: str
    paso: int
    terminado: bool
    en_pausa: bool
    entrega: date | None
    entrega_real: date | None
    productos: list[dict] = field(default_factory=list)


def _proyectos_qs(cliente):
    from apps.los_proyectos.models import Proyecto

    return (Proyecto.objects.filter(cliente=cliente, archivado=False)
            .exclude(estado__in=ESTADOS_OCULTOS))


def _a_proyecto(p, compromiso_visible: set[str], con_productos: bool) -> ProyectoCliente:
    texto, tono, paso = estado_para_cliente(p.estado)
    entrega = None
    if p.fecha_compromiso and p.estado in compromiso_visible:
        from django.utils import timezone

        entrega = timezone.localtime(p.fecha_compromiso).date()
    productos = []
    if con_productos:
        productos = [
            {"nombre": pp.nombre_visible, "cantidad": pp.cantidad}
            for pp in p.productos.all() if pp.incluir_en_calculo
        ]
    return ProyectoCliente(
        pk=p.pk, codigo=p.codigo, nombre=p.nombre, estado=texto, tono=tono, paso=paso,
        terminado=p.estado in ESTADOS_TERMINADOS, en_pausa=p.estado == "en_pausa",
        entrega=entrega, entrega_real=p.fecha_real_entrega, productos=productos,
    )


def proyectos_de(cliente, *, con_productos: bool = True) -> list[ProyectoCliente]:
    from apps.los_proyectos.models.estado import slugs_con_compromiso_visible

    visibles = slugs_con_compromiso_visible()
    qs = _proyectos_qs(cliente).order_by("-creado_en")
    if con_productos:
        qs = qs.prefetch_related("productos__servicio")
    return [_a_proyecto(p, visibles, con_productos) for p in qs]


def proyecto_de(cliente, codigo: str) -> ProyectoCliente | None:
    from apps.los_proyectos.models.estado import slugs_con_compromiso_visible

    p = (_proyectos_qs(cliente).filter(codigo__iexact=(codigo or "").strip())
         .prefetch_related("productos__servicio").first())
    if p is None:
        return None
    return _a_proyecto(p, slugs_con_compromiso_visible(), True)


# ── Cotizaciones ─────────────────────────────────────────────────────────────


def _q_cotizaciones_mandadas() -> Q:
    """Las que el cliente ya tiene en la mano: las de fase enviada/ganada/perdida
    en el catálogo de estados, y cualquiera con sello de envío, de aprobación o
    de rechazo. Los sellos cubren los estados que el catálogo no conoce (el
    servicio cae a los slugs literales «aprobada»/«rechazada» cuando el despacho
    no tiene un estado activo de esa fase)."""
    from apps.cotizaciones.models import FASE_ENVIADA, FASE_GANADA, FASE_PERDIDA
    from apps.cotizaciones.models.estado_cotizacion import slugs_de_fase

    return (Q(estado__in=slugs_de_fase(FASE_ENVIADA, FASE_GANADA, FASE_PERDIDA))
            | Q(enviada_en__isnull=False) | Q(aprobada_en__isnull=False)
            | Q(rechazada_en__isnull=False))


def cotizaciones_qs(cliente):
    from apps.cotizaciones.models import Cotizacion

    return (Cotizacion.objects.filter(cliente=cliente)
            .exclude(estado="anulada")
            .filter(_q_cotizaciones_mandadas())
            .select_related("proyecto"))


def cotizacion_de(cliente, pk):
    """La cotización `pk` SI es de este cliente y ya se le mandó; si no, None."""
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return None
    return cotizaciones_qs(cliente).filter(pk=pk).first()


def _es_ultima_version(cot) -> bool:
    """Una cotización vieja de un proyecto con versión más nueva no se aprueba:
    el trato vigente es el de la última."""
    if not cot.proyecto_id:
        return True
    from apps.cotizaciones.models import Cotizacion

    mayor = (Cotizacion.objects.filter(proyecto_id=cot.proyecto_id, cliente_id=cot.cliente_id)
             .exclude(estado="anulada").order_by("-version", "-pk").values_list("pk", flat=True).first())
    return mayor == cot.pk


@dataclass
class CotizacionCliente:
    obj: object
    pk: int
    codigo: str
    titulo: str
    proyecto: str
    fase: str
    estado: str
    tono: str
    total: Decimal
    moneda: str
    fecha_emision: date | None
    fecha_validez: date | None
    vencida: bool
    ultima: bool
    tiene_pdf: bool
    anticipo: Decimal
    aprobada_por: str
    aprobada_en: object
    rechazada_en: object

    @property
    def por_responder(self) -> bool:
        return self.fase == "enviada"

    @property
    def se_puede_aprobar(self) -> bool:
        return self.fase == "enviada" and self.ultima and not self.vencida

    @property
    def se_puede_rechazar(self) -> bool:
        return self.fase == "enviada"


_TEXTO_FASE = {
    "enviada": ("Por responder", "ambar"),
    "ganada": ("Aprobada", "verde"),
    "perdida": ("Rechazada", "gris"),
}


def _a_cotizacion(cot) -> CotizacionCliente:
    from apps.cotizaciones.embudo import fase_efectiva

    fase = fase_efectiva(cot)
    # Un rechazo registrado manda aunque el catálogo de estados no tenga uno de
    # fase «perdida» activo: `marcar_rechazada` cae entonces al slug literal
    # «rechazada», que sin fila en el catálogo se lee como «armada» y —con su
    # sello de envío— como «enviada». Sin esto la cotización rechazada volvería a
    # salir «por responder» y se podría aprobar después de rechazarla.
    if cot.rechazada_en and fase != "ganada":
        fase = "perdida"
    texto, tono = _TEXTO_FASE.get(fase, ("Enviada", "azul"))
    try:
        total = Decimal(str(cot.calcular_totales()["total"]))
    except Exception:  # noqa: BLE001
        total = CERO
    vencida = bool(cot.fecha_validez and cot.fecha_validez < date.today())
    if fase == "enviada" and vencida:
        texto, tono = "Vencida", "gris"
    try:
        anticipo = cot.anticipo_monto if fase == "ganada" else CERO
    except Exception:  # noqa: BLE001
        anticipo = CERO
    return CotizacionCliente(
        obj=cot, pk=cot.pk, codigo=cot.codigo, titulo=cot.titulo,
        proyecto=(cot.proyecto.nombre if cot.proyecto_id else ""),
        fase=fase, estado=texto, tono=tono, total=total, moneda=cot.moneda,
        fecha_emision=cot.fecha_emision, fecha_validez=cot.fecha_validez,
        vencida=vencida, ultima=_es_ultima_version(cot), tiene_pdf=bool(cot.pdf_file_id),
        anticipo=anticipo, aprobada_por=cot.aprobada_por_nombre, aprobada_en=cot.aprobada_en,
        rechazada_en=cot.rechazada_en,
    )


def cotizaciones_de(cliente) -> list[CotizacionCliente]:
    qs = cotizaciones_qs(cliente).prefetch_related("items", "impuestos__tasa").order_by("-fecha_emision", "-pk")
    return [_a_cotizacion(c) for c in qs]


def cotizacion_cliente(cliente, pk) -> CotizacionCliente | None:
    cot = cotizacion_de(cliente, pk)
    return _a_cotizacion(cot) if cot is not None else None


# ── Facturas ─────────────────────────────────────────────────────────────────


def facturas_qs(cliente):
    from apps.facturacion.models import Factura
    from apps.facturacion.models.factura import q_facturadas

    return (Factura.objects.filter(cliente=cliente).filter(q_facturadas())
            .exclude(estado="cancelada").select_related("proyecto"))


def factura_de(cliente, pk):
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return None
    return facturas_qs(cliente).filter(pk=pk).first()


@dataclass
class FacturaCliente:
    obj: object
    pk: int
    folio: str
    concepto: str
    proyecto: str
    estado: str
    tono: str
    total: Decimal
    cobrado: Decimal
    saldo: Decimal
    moneda: str
    fecha_emision: date | None
    fecha_vencimiento: date | None
    vencida: bool
    tiene_pdf: bool
    tiene_xml: bool


def _a_factura(f) -> FacturaCliente:
    try:
        total = Decimal(str(f.calcular_totales()["total"]))
    except Exception:  # noqa: BLE001
        total = CERO
    saldo = f.saldo_pendiente if f.saldo_pendiente is not None else CERO
    vencida = bool(f.vencida_real)
    if saldo <= 0:
        texto, tono = "Pagada", "verde"
    elif vencida:
        texto, tono = "Vencida", "rojo"
    elif (f.monto_cobrado or CERO) > 0:
        texto, tono = "Pago parcial", "ambar"
    else:
        texto, tono = "Por pagar", "azul"
    return FacturaCliente(
        obj=f, pk=f.pk, folio=f.folio or f.codigo, concepto=f.concepto or f.titulo,
        proyecto=(f.proyecto.nombre if f.proyecto_id else ""), estado=texto, tono=tono,
        total=total, cobrado=f.monto_cobrado or CERO, saldo=max(saldo, CERO), moneda=f.moneda,
        fecha_emision=f.fecha_emision, fecha_vencimiento=f.fecha_vencimiento,
        vencida=vencida, tiene_pdf=bool(f.pdf_file_id), tiene_xml=bool(f.xml_file_id),
    )


def facturas_de(cliente) -> list[FacturaCliente]:
    qs = facturas_qs(cliente).prefetch_related("items", "impuestos__tasa").order_by("-fecha_emision", "-pk")
    return [_a_factura(f) for f in qs]


def factura_cliente(cliente, pk) -> FacturaCliente | None:
    f = factura_de(cliente, pk)
    return _a_factura(f) if f is not None else None


def pagos_de_factura(factura) -> list[dict]:
    """Los ingresos vigentes ligados a la factura: fecha, monto y forma de pago.

    La referencia bancaria y quién lo capturó NO salen: son datos del equipo.
    """
    from apps.tesoreria.models import Ingreso

    return [
        {"fecha": i.fecha, "monto": i.monto, "metodo": i.get_metodo_display()}
        for i in Ingreso.objects.filter(factura=factura, anulado=False).order_by("fecha", "pk")
    ]


# ── Pagar (La Caja, contrato del sprint) ─────────────────────────────────────


def url_pago(objeto) -> str | None:
    """`apps.caja.services.url_pago(objeto)` importado de forma defensiva.

    Si La Caja no está en esta imagen, no tiene llaves o no hay nada que cobrar,
    devuelve None y la plantilla no pinta el botón. Nunca lanza.
    """
    try:
        from apps.caja.services import url_pago as _url_pago
    except Exception:  # noqa: BLE001 — La Caja todavía no está: sin botón
        return None
    try:
        url = _url_pago(objeto)
    except Exception:  # noqa: BLE001 — el contrato dice que no lanza; por si acaso
        return None
    if not url or not str(url).startswith(("https://", "http://")):
        return None
    return str(url)


# ── Resumen del inicio ───────────────────────────────────────────────────────


def resumen(cliente) -> dict:
    proyectos = proyectos_de(cliente, con_productos=False)
    cotizaciones = cotizaciones_de(cliente)
    facturas = facturas_de(cliente)
    return {
        "proyectos_activos": [p for p in proyectos if not p.terminado],
        "proyectos_terminados": sum(1 for p in proyectos if p.terminado),
        "por_responder": [c for c in cotizaciones if c.por_responder],
        "facturas_con_saldo": [f for f in facturas if f.saldo > 0],
        "saldo_total": sum((f.saldo for f in facturas), CERO),
    }
