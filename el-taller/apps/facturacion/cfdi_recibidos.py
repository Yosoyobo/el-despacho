"""Resolver los CFDI que quedaron pendientes (S-Pendientes-Sep28).

La ingesta (`ingesta_cfdi.py`) liga sola lo que es inequívoco. Todo lo demás
llega a `CfdiEntrante` con estado `pendiente` y el motivo escrito. Hasta este
sprint no había cómo resolverlos desde la interfaz, y los CFDI de proveedor
—las facturas que le mandan a Learning Center— se archivaban sin generar su
egreso: el gasto existía en papel y no en Tesorería.

Aquí vive todo lo que decide qué hacer con un pendiente. Lo usan tres
superficies y ninguna repite la lógica:

  - la pantalla de El Taller → Tesorería → CFDI recibidos,
  - el modal de «Nuevo egreso» cuando viene prellenado desde un CFDI,
  - los ejecutores del Chalán (`el_dictado/ejecutores/cfdi.py`).

**La regla es la de siempre en este repo: el sistema propone, una persona
confirma.** Nada de aquí se dispara solo. Y la regla del ligado automático se
conserva: se propone lo que casa, pero entre dos candidatos no se adivina.

Los CFDI de proveedor tienen una trampa que se cuida en `egresos_que_casan`: si
alguien ya capturó el gasto a mano —pagó con tarjeta y registró el egreso antes
de que llegara la factura por correo—, crear otro lo contaría doble. Antes de
ofrecer «Crear egreso» se busca el que ya existe (mismo proveedor, monto ±$1,
fecha ±15 días, sin CFDI ligado) y se ofrece ligarlo.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

#: Cuánto puede diferir el monto de un egreso capturado a mano del total del
#: CFDI para ofrecerlo como «ya existe». Un peso cubre el redondeo de quien
#: capturó sin centavos, sin confundir dos gastos de distinto monto.
TOLERANCIA_MONTO = Decimal("1.00")

#: La factura del proveedor suele llegar días después de pagar (o antes).
DIAS_VENTANA = 15

TIPO_PROVEEDOR = "proveedor"
TIPO_PROPIO = "propio"
TIPO_DUDOSO = "dudoso"

ETIQUETA_TIPO = {
    TIPO_PROVEEDOR: "Factura de un proveedor (un gasto)",
    TIPO_PROPIO: "Factura nuestra a un cliente",
    TIPO_DUDOSO: "No se sabe de quién es",
}

IVA_FACTOR = Decimal("1.16")


class CfdiNoResoluble(ValueError):
    """Lo que se pidió no se puede hacer con ese comprobante. El mensaje va en
    español porque lo lee quien lo intentó."""


# ── Clasificar ───────────────────────────────────────────────────────────────


def rfc_propio() -> str:
    from .ingesta_cfdi import _rfc_propio

    return _rfc_propio()


def clasificar(c, propio: str | None = None) -> str:
    """¿Es la factura de un proveedor, una nuestra, o no se sabe?

    La ingesta ya decidió cuando el RFC del despacho estaba configurado. Pero
    hay pendientes de antes de configurarlo, así que aquí se vuelve a mirar con
    todo lo que se sabe, de lo más seguro a lo menos.
    """
    if c.egreso_id or c.proveedor_id:
        return TIPO_PROVEEDOR
    if c.factura_id:
        return TIPO_PROPIO
    propio = (rfc_propio() if propio is None else propio or "").strip().upper()
    if propio:
        if (c.receptor_rfc or "").upper() == propio:
            return TIPO_PROVEEDOR
        if (c.emisor_rfc or "").upper() == propio:
            return TIPO_PROPIO
    if (c.motivo or "").startswith("Es una factura que nos emitió"):
        return TIPO_PROVEEDOR
    # Sin RFC propio configurado: lo que dice el catálogo.
    if c.emisor_rfc and _hay_proveedor_con_rfc(c.emisor_rfc):
        return TIPO_PROVEEDOR
    if c.receptor_rfc and _hay_cliente_con_rfc(c.receptor_rfc):
        return TIPO_PROPIO
    return TIPO_DUDOSO


def _hay_proveedor_con_rfc(rfc: str) -> bool:
    from apps.el_catalogo.models import Proveedor

    return Proveedor.objects.filter(rfc__iexact=rfc.strip()).exists()


def _hay_cliente_con_rfc(rfc: str) -> bool:
    from apps.la_cartera.models import Cliente
    from django.db.models import Q

    rfc = rfc.strip()
    return Cliente.objects.filter(
        Q(rfc__iexact=rfc) | Q(razones_sociales__rfc__iexact=rfc)).exists()


# ── Proveedor ────────────────────────────────────────────────────────────────


def proveedor_sugerido(c):
    """El proveedor al que pertenece el comprobante, si se puede decir sin
    adivinar: el que ya se eligió, el ÚNICO con ese RFC, o el ÚNICO con ese
    nombre (sin acentos ni «S.A. de C.V.»)."""
    if c.proveedor_id:
        return c.proveedor
    from apps.el_catalogo.models import Proveedor

    if c.emisor_rfc:
        por_rfc = list(Proveedor.objects.filter(rfc__iexact=c.emisor_rfc, activo=True)[:2])
        if len(por_rfc) == 1:
            return por_rfc[0]
        if len(por_rfc) > 1:
            return None  # dos con el mismo RFC: que elija una persona
    if c.emisor_nombre:
        from lib.nombres import normalizar

        buscado = normalizar(c.emisor_nombre)
        if len(buscado) >= 4:
            iguales = [p for p in Proveedor.objects.filter(activo=True).only("pk", "razon_social")
                       if normalizar(p.razon_social) == buscado]
            if len(iguales) == 1:
                return iguales[0]
    return None


@transaction.atomic
def asignar_proveedor(c, proveedor, actor=None, *, aprender_rfc: bool = True):
    """Dice a qué proveedor pertenece el comprobante.

    Con `aprender_rfc`, si el proveedor no tenía RFC se le pone el del
    emisor: así el siguiente CFDI de ese proveedor se reconoce solo.
    """
    c = type(c).objects.select_for_update().get(pk=c.pk)
    if c.egreso_id:
        raise CfdiNoResoluble("Ese comprobante ya tiene su egreso; el proveedor sale de ahí.")
    c.proveedor = proveedor
    c.save(update_fields=["proveedor"])
    aprendio = False
    if aprender_rfc and proveedor is not None and c.emisor_rfc and not (proveedor.rfc or "").strip():
        proveedor.rfc = c.emisor_rfc[:20]
        proveedor.save(update_fields=["rfc"])
        aprendio = True
    _emitir("cfdi.proveedor_asignado", actor, {
        "cfdi_id": c.pk, "uuid": c.uuid,
        "proveedor_id": getattr(proveedor, "pk", None), "rfc_aprendido": aprendio,
    })
    return c


# ── El desglose ──────────────────────────────────────────────────────────────


def completar_desglose(c) -> None:
    """Los CFDI que llegaron antes de guardar el desglose se releen del XML.

    Best-effort: si el archivo no está, el comprobante sigue sirviendo con su
    total (el subtotal se deriva del IVA al 16% como en cualquier captura).
    """
    if c.subtotal is not None or not c.archivo_id:
        return
    try:
        from lib import almacen, cfdi

        contenido, _mime, _nombre = almacen.leer(c.archivo_id)
        lec = cfdi.leer(contenido)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cfdi_recibidos: no se pudo releer %s: %s", c.uuid, exc)
        return
    if not lec.ok:
        return
    c.subtotal, c.descuento = lec.subtotal, lec.descuento
    c.iva, c.retenciones = lec.iva, lec.retenciones
    c.concepto = c.concepto or lec.concepto
    try:
        c.save(update_fields=["subtotal", "descuento", "iva", "retenciones", "concepto"])
    except Exception as exc:  # noqa: BLE001 — releerlo la próxima vez no cuesta
        logger.debug("cfdi_recibidos: no se pudo guardar el desglose: %s", exc)


def lleva_iva(c) -> bool:
    """¿El gasto trae IVA? Lo dice el comprobante; sin desglose, se infiere."""
    if c.iva is not None:
        return c.iva > 0
    if c.total is not None and c.subtotal is not None:
        return c.total > (c.base or c.subtotal)
    return True  # el default de toda captura de egreso


def base_del_gasto(c) -> Decimal | None:
    """La base sin IVA que se guarda en `Egreso.subtotal`.

    La del comprobante si la trae (SubTotal − Descuento). Si no, la misma
    cuenta que hace el formulario de egreso: total ÷ 1.16 con IVA, total sin él.
    """
    if c.base is not None:
        return Decimal(c.base).quantize(Decimal("0.01"))
    if c.total is None:
        return None
    total = Decimal(c.total)
    return (total / IVA_FACTOR).quantize(Decimal("0.01")) if lleva_iva(c) else total


def concepto_del_gasto(c) -> str:
    """La descripción del egreso: lo que dice la factura, o de quién es."""
    if c.concepto:
        return c.concepto[:300]
    quien = c.emisor_nombre or c.emisor_rfc or "proveedor"
    ref = f" {c.referencia}" if c.referencia else ""
    return f"Factura{ref} de {quien}"[:300]


def centro_sugerido(proveedor):
    """El centro de costo del último egreso a ese proveedor. Sólo sugiere."""
    if proveedor is None:
        return None
    from apps.tesoreria.models import Egreso

    ultimo = (Egreso.vigentes.filter(proveedor=proveedor, centro_de_costo__activo=True)
              .order_by("-fecha", "-pk").select_related("centro_de_costo").first())
    return ultimo.centro_de_costo if ultimo else None


def datos_para_egreso(c) -> dict:
    """El `initial` del formulario de egreso, sacado del comprobante.

    Ojo con el campo `subtotal` del formulario: desde LC Fase 2 **se captura
    el TOTAL** (IVA incluido) y el formulario deriva la base. Por eso aquí va
    el total del CFDI, no su subtotal.
    """
    completar_desglose(c)
    initial = {
        "subtotal": c.total,
        "incluye_iva": lleva_iva(c),
        "descripcion": concepto_del_gasto(c),
    }
    fecha = c.fecha
    if fecha:
        initial["fecha"] = fecha
    prov = proveedor_sugerido(c)
    if prov is not None:
        initial["proveedor"] = prov.pk
        centro = centro_sugerido(prov)
        if centro is not None:
            initial["centro_de_costo"] = centro.pk
    return initial


# ── Egresos que ya existen ───────────────────────────────────────────────────


def egresos_que_casan(c, proveedor=None) -> list:
    """Los egresos vigentes que podrían ser éste: mismo proveedor, monto ±$1,
    fecha ±15 días y sin CFDI ligado.

    Sin proveedor conocido no se ofrece nada: comparar sólo por monto ligaría
    el gasto de un proveedor al comprobante de otro.
    """
    proveedor = proveedor or proveedor_sugerido(c)
    if proveedor is None or c.total is None:
        return []
    from apps.tesoreria.models import Egreso

    total = Decimal(c.total)
    qs = Egreso.vigentes.filter(
        proveedor=proveedor,
        monto__gte=total - TOLERANCIA_MONTO,
        monto__lte=total + TOLERANCIA_MONTO,
        cfdi_entrante__isnull=True,
    )
    fecha = c.fecha
    if fecha:
        qs = qs.filter(fecha__gte=fecha - timedelta(days=DIAS_VENTANA),
                       fecha__lte=fecha + timedelta(days=DIAS_VENTANA))
    return list(qs.order_by("-fecha", "-pk")[:10])


# ── Facturas propias ─────────────────────────────────────────────────────────


def facturas_candidatas(c) -> list:
    """Las facturas nuestras que casan (mismo criterio que el ligado solo)."""
    from types import SimpleNamespace

    from .ingesta_cfdi import _candidatas

    total = Decimal(c.total) if c.total is not None else None
    return _candidatas(SimpleNamespace(receptor_rfc=c.receptor_rfc, total=total))


def facturas_sin_comprobante(limite: int = 200) -> list:
    """Para elegir a mano: todas las facturas vigentes que aún no tienen CFDI."""
    from .models import Factura

    return list(Factura.objects.filter(cfdi_uuid="").exclude(estado="cancelada")
                .select_related("cliente").order_by("-fecha_emision", "-pk")[:limite])


# ── Resolver ─────────────────────────────────────────────────────────────────


def _marcar_resuelto(c, actor) -> None:
    from .models import ESTADO_LIGADO

    c.estado = ESTADO_LIGADO
    c.resuelto_en = timezone.now()
    c.resuelto_por = actor if getattr(actor, "pk", None) else None


def _pendiente_bloqueado(c):
    """Relee el comprobante con candado. Dos personas resolviendo el mismo
    pendiente a la vez no deben ligarlo dos veces."""
    return type(c).objects.select_for_update().get(pk=c.pk)


@transaction.atomic
def ligar_egreso(c, egreso, actor=None):
    """Liga el comprobante a un egreso que ya existe (o que se acaba de crear).

    Si el egreso no tenía comprobante, el CFDI pasa a serlo: el PDF si llegó,
    si no el XML.
    """
    from .models import ESTADO_IGNORADO

    c = _pendiente_bloqueado(c)
    if c.egreso_id and c.egreso_id != egreso.pk:
        raise CfdiNoResoluble(
            f"Ese comprobante ya está ligado al egreso {c.egreso.codigo}.")
    if c.factura_id:
        raise CfdiNoResoluble(
            "Ese comprobante es de una factura nuestra: no respalda un gasto.")
    if c.estado == ESTADO_IGNORADO:
        raise CfdiNoResoluble("Ese comprobante se marcó como ignorado.")
    if egreso.anulado:
        raise CfdiNoResoluble(f"El egreso {egreso.codigo} está anulado.")
    ya = type(c).objects.filter(egreso=egreso).exclude(pk=c.pk).first()
    if ya is not None:
        raise CfdiNoResoluble(
            f"El egreso {egreso.codigo} ya tiene su comprobante ({ya.referencia or ya.uuid[:8]}).")

    c.egreso = egreso
    if c.proveedor_id is None and egreso.proveedor_id:
        c.proveedor_id = egreso.proveedor_id
    _marcar_resuelto(c, actor)
    try:
        c.save()
    except IntegrityError as exc:  # la base es la última palabra (uno a uno)
        raise CfdiNoResoluble("Ese egreso ya tiene otro comprobante ligado.") from exc

    comprobante = c.comprobante_id
    if comprobante and not (egreso.tiene_comprobante and egreso.drive_file_id):
        # El Almacén está direccionado por contenido: compartir la llave es
        # compartir el mismo archivo, sin copiarlo.
        egreso.drive_file_id = comprobante
        egreso.tiene_comprobante = True
        egreso.save(update_fields=["drive_file_id", "tiene_comprobante"])

    _emitir("cfdi.ligado_egreso", actor, {
        "cfdi_id": c.pk, "uuid": c.uuid, "egreso_id": egreso.pk,
        "egreso": egreso.codigo, "monto": str(egreso.monto),
    })
    return c


def crear_egreso(c, *, actor, centro_de_costo=None, metodo: str = "",
                 estado_pago: str = "", proyecto=None, proveedor=None,
                 descripcion: str = "", fecha=None, pagado_por=None):
    """Crea el egreso del comprobante y lo liga. Lo usa El Chalán, tras la
    confirmación de una persona (el modal de la pantalla usa el formulario de
    siempre y llama `ligar_egreso` al guardar).

    Mismas reglas que la captura manual: el proveedor es obligatorio
    (S-LC-julio) y el monto es el TOTAL con IVA.
    """
    from apps.tesoreria.models import METODOS_REEMBOLSO, CentroDeCosto, Egreso

    from .models import ESTADO_IGNORADO

    if c.egreso_id:
        raise CfdiNoResoluble(f"Ese comprobante ya tiene su egreso ({c.egreso.codigo}).")
    if c.factura_id:
        raise CfdiNoResoluble("Ese comprobante es de una factura nuestra: no es un gasto.")
    if c.estado == ESTADO_IGNORADO:
        raise CfdiNoResoluble("Ese comprobante se marcó como ignorado.")
    if c.total is None or Decimal(c.total) <= 0:
        raise CfdiNoResoluble("El comprobante no trae un total que registrar.")

    proveedor = proveedor or proveedor_sugerido(c)
    if proveedor is None:
        raise CfdiNoResoluble(
            f"No sé qué proveedor es «{c.emisor_nombre or c.emisor_rfc}». "
            "Dime cuál (o dalo de alta) y lo registro.")

    centro = (centro_de_costo or centro_sugerido(proveedor)
              or CentroDeCosto.objects.filter(slug="otros", activo=True).first())
    if centro is None:
        raise CfdiNoResoluble("No hay un centro de costo al que cargarlo.")

    metodo = (metodo or "transferencia").strip().lower()
    estado = (estado_pago or "pagado").strip().lower()
    if estado not in {"pagado", "por_reembolsar", "pendiente"}:
        estado = "pagado"
    if metodo in METODOS_REEMBOLSO:
        estado = "por_reembolsar"

    completar_desglose(c)
    with transaction.atomic():
        egreso = Egreso.objects.create(
            monto=Decimal(c.total).quantize(Decimal("0.01")),
            subtotal=base_del_gasto(c),
            incluye_iva=lleva_iva(c),
            fecha=fecha or c.fecha or date.today(),
            descripcion=(descripcion or concepto_del_gasto(c))[:300],
            proveedor=proveedor, proveedor_nombre=proveedor.razon_social[:200],
            centro_de_costo=centro, proyecto=proyecto,
            pagado_por=pagado_por or actor, estado_pago=estado, metodo=metodo,
            origen="cfdi", creado_por=actor,
        )
        ligar_egreso(c, egreso, actor)
    return egreso


@transaction.atomic
def ligar_factura(c, factura, actor=None):
    """Liga un comprobante nuestro a su factura, con su XML (y su PDF).

    Hace lo mismo que el ligado solo de la ingesta: el archivo queda en la
    factura por el camino de siempre (`services.almacenar_cfdi`).
    """
    from .models import ESTADO_IGNORADO

    c = _pendiente_bloqueado(c)
    if c.factura_id and c.factura_id != factura.pk:
        raise CfdiNoResoluble(f"Ese comprobante ya está ligado a {c.factura.codigo}.")
    if c.egreso_id:
        raise CfdiNoResoluble(
            "Ese comprobante respalda un gasto: no es una factura nuestra.")
    if c.estado == ESTADO_IGNORADO:
        raise CfdiNoResoluble("Ese comprobante se marcó como ignorado.")
    if factura.estado == "cancelada":
        raise CfdiNoResoluble(f"La factura {factura.codigo} está cancelada.")
    if factura.cfdi_uuid and factura.cfdi_uuid.upper() != c.uuid.upper():
        raise CfdiNoResoluble(
            f"La factura {factura.codigo} ya tiene su comprobante ({factura.cfdi_uuid[:8]}…).")

    c.factura = factura
    _marcar_resuelto(c, actor)
    c.save()

    xml_file = pdf_file = None
    try:
        from lib import almacen

        from .ingesta_cfdi import como_archivo

        if c.archivo_id:
            contenido, _m, nombre = almacen.leer(c.archivo_id)
            xml_file = como_archivo(contenido, nombre or f"{c.uuid}.xml", "application/xml")
        if c.pdf_id:
            contenido, _m, nombre = almacen.leer(c.pdf_id)
            pdf_file = como_archivo(contenido, nombre or f"{c.uuid}.pdf", "application/pdf")
    except Exception as exc:  # noqa: BLE001 — sin archivo queda el folio fiscal
        logger.warning("cfdi_recibidos: no se pudo releer el archivo de %s: %s", c.uuid, exc)

    from . import services

    services.almacenar_cfdi(factura, xml_file=xml_file, pdf_file=pdf_file,
                            cfdi_uuid=c.uuid, actor=actor)
    _emitir("cfdi.ligado_factura", actor, {
        "cfdi_id": c.pk, "uuid": c.uuid, "factura_id": factura.pk, "factura": factura.codigo,
    })
    return c


@transaction.atomic
def ignorar(c, actor=None, motivo: str = ""):
    from .models import ESTADO_IGNORADO

    c = _pendiente_bloqueado(c)
    if c.egreso_id or c.factura_id:
        raise CfdiNoResoluble("Ese comprobante ya está ligado; no se ignora.")
    c.estado = ESTADO_IGNORADO
    c.resuelto_en = timezone.now()
    c.resuelto_por = actor if getattr(actor, "pk", None) else None
    campos = ["estado", "resuelto_en", "resuelto_por"]
    motivo = (motivo or "").strip()
    if motivo:
        c.motivo = f"Ignorado: {motivo}"[:300]
        campos.append("motivo")
    c.save(update_fields=campos)
    _emitir("cfdi.ignorado", actor, {"cfdi_id": c.pk, "uuid": c.uuid})
    return c


# ── Buscar ───────────────────────────────────────────────────────────────────


def buscar(referencia: str):
    """Encuentra un comprobante por su folio fiscal (completo o el principio),
    su serie-folio o su pk. Devuelve None si no hay UNO."""
    from .models import CfdiEntrante

    ref = (referencia or "").strip()
    if not ref:
        return None
    if ref.isdigit():
        por_pk = CfdiEntrante.objects.filter(pk=int(ref)).first()
        if por_pk:
            return por_pk
    exacto = CfdiEntrante.objects.filter(uuid__iexact=ref).first()
    if exacto:
        return exacto
    for qs in (CfdiEntrante.objects.filter(uuid__istartswith=ref) if len(ref) >= 8 else None,
               CfdiEntrante.objects.filter(referencia__iexact=ref)):
        if qs is None:
            continue
        hallados = list(qs[:2])
        if len(hallados) == 1:
            return hallados[0]
    return None


def pendientes():
    from .models import ESTADO_PENDIENTE, CfdiEntrante

    return (CfdiEntrante.objects.filter(estado=ESTADO_PENDIENTE)
            .select_related("proveedor", "factura", "egreso").order_by("-recibido_en"))


def resumen(c, propio: str | None = None) -> dict:
    """Lo que hace falta saber para resolver un pendiente, en datos."""
    tipo = clasificar(c, propio)
    prov = proveedor_sugerido(c) if tipo != TIPO_PROPIO else None
    datos = {
        "id": c.pk,
        "uuid": c.uuid,
        "referencia": c.referencia,
        "emisor": c.emisor_nombre or c.emisor_rfc,
        "emisor_rfc": c.emisor_rfc,
        "receptor": c.receptor_nombre or c.receptor_rfc,
        "total": c.total,
        "fecha": c.fecha.isoformat() if c.fecha else "",
        "concepto": c.concepto,
        "tipo": tipo,
        "que_es": ETIQUETA_TIPO[tipo],
        "motivo": c.motivo,
    }
    if tipo in (TIPO_PROVEEDOR, TIPO_DUDOSO):
        datos["proveedor_sugerido"] = prov.razon_social if prov else ""
        datos["egresos_que_casan"] = [e.codigo for e in egresos_que_casan(c, prov)]
    if tipo in (TIPO_PROPIO, TIPO_DUDOSO):
        datos["facturas_candidatas"] = [f.codigo for f in facturas_candidatas(c)]
    return datos


def _emitir(tipo: str, actor, payload: dict) -> None:
    """Best-effort: un evento que no se encola no deshace lo que ya se hizo."""
    try:
        from lib import portavoz
        from lib.portavoz_eventos import EventoPortavoz

        portavoz.emitir(EventoPortavoz(
            tipo=tipo, actor_id=getattr(actor, "pk", None),
            actor_email=getattr(actor, "email", "") or "", payload=payload,
        ))
    except Exception as exc:  # noqa: BLE001
        logger.debug("cfdi_recibidos: no se pudo emitir %s: %s", tipo, exc)


__all__ = [
    "CfdiNoResoluble",
    "DIAS_VENTANA",
    "ETIQUETA_TIPO",
    "TIPO_DUDOSO",
    "TIPO_PROPIO",
    "TIPO_PROVEEDOR",
    "TOLERANCIA_MONTO",
    "asignar_proveedor",
    "buscar",
    "clasificar",
    "crear_egreso",
    "datos_para_egreso",
    "egresos_que_casan",
    "facturas_candidatas",
    "facturas_sin_comprobante",
    "ignorar",
    "ligar_egreso",
    "ligar_factura",
    "pendientes",
    "proveedor_sugerido",
    "resumen",
]
