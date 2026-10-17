"""Gastos del proyecto ↔ Egresos de Tesorería — contabilidad en línea.

Decisión (Oscar, 2026-06-12): cada gasto del proyecto se liga POR SEPARADO a
un Egreso registrado. Unidades de gasto:

- **producto**: una línea `ProyectoProducto` incluida → monto = `costo_total_linea`
  (producto + merma, SIN procesos), proveedor = el de la línea.
- **impresion**: un `Proceso` tipo impresión → monto = su costo, proveedor del proceso.
- **operativo**: un `Proceso` tipo operativo (clavos, pegamento…) → monto = su
  costo, sin proveedor.

Un gasto está **registrado** si tiene un Egreso vigente (no anulado). Los que no,
salen como alerta en el proyecto y como "gastos no registrados" en Tesorería,
con un botón para registrarlos (crea el Egreso y lo liga).

**Pagos parciales (Oscar 2026-10-14).** «Registrar pago» de un proveedor permite
(a) elegir QUÉ conceptos se pagan (casilla por concepto: varios pedidos en una
tienda) y (b) CUÁNTO se paga ahora (todo, el 50% como anticipo, u otro monto).
Reglas, para no tener que adivinarlas leyendo el código:

* Cada concepto sigue teniendo un solo `egreso` (FK) = «ya se pagó completo».
  Lo parcial vive en `PagoGasto` (egreso + concepto + monto abonado, base sin IVA).
  Pendiente de un concepto = su costo − Σ abonos de egresos vigentes ya pagados.
* Un pago parcial crea UN egreso por el monto pagado y NO toca el FK de los
  conceptos que quedan a medias; sólo el concepto que ese pago termina de cubrir
  recibe el FK. Lo que falta sigue saliendo en la sección amarilla con su
  `monto` = lo pendiente (por eso IVA, totales y «gastos no registrados» cuadran).
* El monto parcial se reparte entre los conceptos elegidos **en proporción a lo
  que a cada uno le falta**, por el método del mayor resto en centavos
  (`repartir_proporcional`): la suma da exactamente el monto y ningún concepto
  recibe más de lo que le falta.
* Un concepto que ya es cuenta por pagar («pendiente») no se parte: se liquida
  completo o no se incluye. Un pago parcial que lo incluya se rechaza.
* Anular el egreso de un abono devuelve ese monto a «pendiente» sin más pasos.
* Lo que se captura en el modal está en la misma base que muestra el héroe (con IVA
  si la casilla está marcada); el egreso guarda la base sin IVA, igual que el pago
  completo de siempre (el IVA del modal es informativo, ver HISTORIAL «#163»).
"""

from __future__ import annotations

import contextlib
import logging
from datetime import date
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)

CENTRO_SLUG = "insumos-de-proyecto"
CERO = Decimal("0.00")

# S-LC-Feedback-V8 (Oscar): la alerta de gastos sin registrar solo aplica de
# "En proceso de diseño" en adelante (antes de eso el proyecto aún se cotiza).
ESTADOS_CON_GASTOS = {
    "en_proceso_diseno", "en_proceso_produccion", "entregado", "cerrado",
}

# LC 2026-07 (Oscar): el recuadro de egresos sale en TODOS los estados, pero la
# alerta de "pagos pendientes sin registrar" solo de PRODUCCIÓN en adelante.
ESTADOS_ALERTA_PAGOS = {"en_proceso_produccion", "entregado", "cerrado"}


def debe_mostrar_gastos(proyecto) -> bool:
    return getattr(proyecto, "estado", None) in ESTADOS_CON_GASTOS


def debe_mostrar_alerta_pagos(proyecto) -> bool:
    return getattr(proyecto, "estado", None) in ESTADOS_ALERTA_PAGOS


def desglose_iva(proyecto, pendientes: list[dict]) -> dict:
    """Subtotal + IVA = total de los gastos pendientes (S-LC-Feedback-V8).

    El monto de cada unidad es el costo SIN IVA (es lo que cuesta producir);
    el IVA que paga la empresa se calcula con la tasa efectiva del proyecto.
    """
    subtotal = sum((u["monto"] for u in pendientes), CERO)
    try:
        tasa = Decimal(str(proyecto.iva_tasa_efectiva))
    except Exception:  # noqa: BLE001
        tasa = Decimal("0.16")
    iva = (subtotal * tasa).quantize(Decimal("0.01"))
    return {
        "subtotal": subtotal.quantize(Decimal("0.01")),
        "iva": iva,
        "total": (subtotal + iva).quantize(Decimal("0.01")),
        "iva_label": f"{float(tasa * 100):g}%",
    }


def _quien(actor):
    """El usuario que registró el egreso (None si lo hizo el sistema).

    Importa: `creado_por` vacío es la huella con la que `limpiar_egresos_automaticos`
    reconoce los egresos que generaba solo el sistema (hasta 2026-10-14). Todo
    egreso que registra una persona lleva su nombre y queda a salvo de la limpieza."""
    return actor if getattr(actor, "pk", None) else None


def _registrado(egreso) -> bool:
    return egreso is not None and not egreso.anulado


def _pagado(egreso) -> bool:
    """Un gasto está PAGADO cuando su egreso vigente ya se saldó o quedó por
    reembolsar (LC 2026-07: solo se registra un egreso al realizarse). Un egreso
    'pendiente' (cuenta por pagar auto-generada) todavía cuenta como pendiente."""
    return (
        egreso is not None
        and not egreso.anulado
        and egreso.estado_pago in ("pagado", "por_reembolsar")
    )


def _nombre_base(pp) -> str:
    return pp.variacion.nombre if pp.variacion_id else pp.servicio.nombre


def _label_produccion(pp) -> str:
    """Etiqueta del gasto del producto con las piezas a PRODUCIR (cantidad +
    merma), no la cantidad vendida.

    LC 2026-07-25 (Oscar): siempre en el formato «× 35 pz» — sin el desglose
    «(30 + 5 merma)», que confundía en la lista de pagos pendientes.
    """
    return f"{_nombre_base(pp)} · × {pp.piezas_efectivas} pz"


def _monto_proceso(proc, pp) -> Decimal:
    """Costo del proceso: fijo o × piezas producidas según `por_pieza`.

    Se lee de `proc.costo_total`, que ya resuelve el override de la escala activa
    (LC 2026-08-17): el egreso debe cobrar lo de la opción que manda.
    """
    return Decimal(str(proc.costo_total)).quantize(Decimal("0.01"))


def _label_proceso(proc, pp) -> str:
    # Mismo formato «× N pz» que el gasto del producto (LC 2026-07-25). El
    # proceso fijo no lleva piezas: su costo no depende de la producción.
    suf = f" · × {pp.piezas_efectivas} pz" if proc.por_pieza_efectivo else ""
    return f"{_nombre_base(pp)} · {proc.etiqueta}{suf}"


TOLERANCIA = Decimal("0.01")


def _abonado(obj) -> Decimal:
    """Σ de los abonos (`PagoGasto`) del concepto cuyo egreso sigue vigente y ya se
    pagó (pagado o por reembolsar). Un egreso anulado devuelve su monto a pendiente."""
    total = CERO
    for ab in obj.pagos_gasto.all():
        eg = ab.egreso
        if not eg.anulado and eg.estado_pago in ("pagado", "por_reembolsar"):
            total += ab.monto
    return total


def _restante(egreso, monto_total: Decimal, abonado: Decimal) -> tuple[bool, Decimal]:
    """(pagado, restante) de un concepto. Pagado = su egreso vigente ya se saldó, o
    los abonos cubren todo su costo. `restante` = lo que falta por pagar."""
    if _pagado(egreso):
        return True, CERO
    restante = (monto_total - abonado).quantize(Decimal("0.01"))
    if restante < TOLERANCIA:
        return True, CERO
    return False, restante


def _unidad(clase, obj, tipo, label, monto_total, proveedor):
    egreso = obj.egreso
    abonado = _abonado(obj)
    pagado, restante = _restante(egreso, monto_total, abonado)
    return {
        "clase": clase, "pk": obj.pk, "tipo": tipo, "label": label,
        # `monto` = lo que FALTA por pagar (el costo completo si no hay abonos).
        "monto": monto_total if pagado else restante,
        "monto_total": monto_total,
        "pagado_parcial": CERO if pagado else abonado,
        "proveedor": proveedor, "egreso": egreso,
        "registrado": _registrado(egreso),
        "pagado": pagado,
    }


def iter_unidades(proyecto):
    """Genera dicts de unidad de gasto del proyecto (solo con monto > 0)."""
    lineas = (
        proyecto.productos
        .filter(incluir_en_calculo=True)
        .select_related("proveedor", "servicio", "variacion", "egreso")
        .prefetch_related("procesos", "procesos__proveedor", "procesos__egreso",
                          "pagos_gasto__egreso", "procesos__pagos_gasto__egreso")
    )
    for pp in lineas:
        monto = Decimal(str(pp.costo_total_linea)).quantize(Decimal("0.01"))
        if monto > 0:
            yield _unidad("producto", pp, "producto", _label_produccion(pp), monto, pp.proveedor)
        for proc in pp.procesos.all():
            c = _monto_proceso(proc, pp)
            if c <= 0:
                continue
            # Ticket UX 2026-07: los operativos pueden ligar proveedor (@).
            yield _unidad("proceso", proc, proc.tipo, _label_proceso(proc, pp), c, proc.proveedor)


def pendientes_de(proyecto) -> list[dict]:
    """Unidades de gasto del proyecto SIN egreso vigente (para la vista global
    de Tesorería «Gastos no registrados» y la auto-generación)."""
    return [u for u in iter_unidades(proyecto) if not u["registrado"]]


def pagos_pendientes_de(proyecto) -> list[dict]:
    """Unidades de gasto cuyo PAGO aún no se registra: sin egreso, egreso
    anulado, o egreso todavía en «Pendiente» (cuenta por pagar auto-generada).
    Alimenta la alerta del detalle del proyecto (LC 2026-07). Cada unidad trae
    su IVA por línea (LC #157): base, `iva` y `total_con_iva`."""
    try:
        tasa = Decimal(str(proyecto.iva_tasa_efectiva))
    except Exception:  # noqa: BLE001
        tasa = Decimal("0.16")
    out = []
    for u in iter_unidades(proyecto):
        if u["pagado"]:
            continue
        base = Decimal(str(u["monto"]))
        iva = (base * tasa).quantize(Decimal("0.01"))
        out.append({**u, "iva": iva, "total_con_iva": (base + iva).quantize(Decimal("0.01"))})
    return out


CLAVE_SIN_PROVEEDOR = 0


def grupos_pagos_pendientes_de(proyecto) -> list[dict]:
    """Pagos pendientes AGRUPADOS por proveedor.

    LC 2026-07-26 (Oscar): «se le paga una vez a cada uno, no por cada producto o
    proceso separado». El recuadro del proyecto listaba una fila por unidad de
    gasto, así que un proveedor que surte tres productos salía tres veces y había
    que registrar tres pagos. Ahora cada proveedor es UN renglón con la suma, y
    su detalle queda listado dentro.

    Cada grupo: `{clave, proveedor, proveedor_nombre, unidades, monto, iva,
    total_con_iva}`. `clave` es el pk del proveedor (0 = sin proveedor) y es lo
    que viaja en la URL del modal.
    """
    pendientes = pagos_pendientes_de(proyecto)
    grupos: dict[int, dict] = {}
    for u in pendientes:
        prov = u.get("proveedor")
        clave = prov.pk if prov is not None else CLAVE_SIN_PROVEEDOR
        g = grupos.get(clave)
        if g is None:
            g = grupos[clave] = {
                "clave": clave,
                "proveedor": prov,
                "proveedor_nombre": (prov.razon_social if prov is not None
                                     else "Sin proveedor asignado"),
                "unidades": [],
                "monto": CERO, "iva": CERO, "total_con_iva": CERO,
            }
        g["unidades"].append(u)
        g["monto"] += Decimal(str(u["monto"]))
        g["iva"] += Decimal(str(u.get("iva") or 0))
        g["total_con_iva"] += Decimal(str(u.get("total_con_iva") or 0))
    salida = list(grupos.values())
    # El más caro primero (mismo criterio que la vista global de Tesorería), y
    # «Sin proveedor asignado» al final: es el que necesita que alguien lo defina.
    salida.sort(key=lambda g: (g["clave"] == CLAVE_SIN_PROVEEDOR, -g["monto"]))
    return salida


def grupo_pago_de(proyecto, clave: int) -> dict | None:
    """Un grupo de `grupos_pagos_pendientes_de` por su clave. None si ya no hay
    nada pendiente para ese proveedor (p.ej. dos pestañas abiertas)."""
    for g in grupos_pagos_pendientes_de(proyecto):
        if g["clave"] == int(clave):
            return g
    return None


def repartir_proporcional(monto: Decimal, restantes: list[Decimal]) -> list[Decimal]:
    """Reparte `monto` entre conceptos EN PROPORCIÓN a lo que a cada uno le falta.

    Método del mayor resto, en centavos enteros: cada concepto recibe el piso de su
    parte exacta y los centavos que sobran se dan, de uno en uno, a quienes tienen
    el resto más grande (a igualdad, el primero de la lista). Garantías: la suma da
    EXACTAMENTE `monto` y ningún concepto recibe más de lo que le falta. Si `monto`
    cubre todo, cada uno recibe lo que le falta.
    """
    centavos = int((Decimal(str(monto)) * 100).to_integral_value())
    faltan = [int((Decimal(str(r)) * 100).to_integral_value()) for r in restantes]
    total = sum(faltan)
    if centavos >= total:
        return [Decimal(f) / 100 for f in faltan]
    base = [centavos * f // total for f in faltan]
    resto = [centavos * f % total for f in faltan]
    sobran = centavos - sum(base)
    for i in sorted(range(len(faltan)), key=lambda k: (-resto[k], k))[:sobran]:
        base[i] += 1
    return [Decimal(b) / 100 for b in base]


def _clave_unidad(u) -> str:
    return f"{u['clase']}:{u['pk']}"


def registrar_pago_grupo(proyecto, clave: int, *, actor=None, centro=None,
                         metodo="transferencia", estado_pago="pagado",
                         pagado_por=None, solicitado_por=None, proveedor=None,
                         fecha=None, unidades=None, monto=None, fraccion=None,
                         etiqueta="", pendiente_visto=None) -> dict:
    """Registra el pago de lo pendiente de un proveedor: TODO o una parte.

    Sin `unidades` ni `monto` es el pago completo de siempre: **un solo Egreso**
    con la suma de las unidades que aún no tienen uno, ligadas a él (el FK es
    muchos-a-uno). Las que ya traían un egreso «Pendiente» —la cuenta por pagar
    que se auto-generaba— se LIQUIDAN: esos egresos ya existen en contabilidad y
    no se pueden fusionar.

    Parcial (Oscar 2026-10-14; reglas completas en el docstring del módulo):

    * `unidades`: lista de «clase:pk» (o tuplas) = los conceptos que se pagan
      ahora; None = todos los pendientes del proveedor.
    * `monto`: cuánto se paga AHORA, sin IVA (misma base que el concepto). None, o
      un monto que cubre todo lo elegido (con un centavo de tolerancia), = pago
      completo. Menor = pago parcial, repartido con `repartir_proporcional`.
    * `fraccion`: alternativa a `monto`, una parte de lo elegido (0.5 = el anticipo
      del 50%); se calcula sobre lo que falta de los conceptos elegidos.
    * `pendiente_visto`: lo pendiente del proveedor que vio quien abrió el modal; si
      cambió (otro pago en medio, doble clic) se rechaza en vez de pagar dos veces.

    Lanza ValueError (con mensaje para mostrar) si la petición no es válida.
    Devuelve `{creado, liquidados, unidades, parcial, restante}`.
    """
    from apps.tesoreria.models import CentroDeCosto, Egreso
    from apps.tesoreria.services import liquidar_egreso_pendiente

    from .models import PagoGasto

    vacio = {"creado": None, "liquidados": [], "unidades": 0, "parcial": False,
             "restante": CERO}
    grupo = grupo_pago_de(proyecto, clave)
    if grupo is None:
        return vacio
    if pendiente_visto is not None and \
            abs(Decimal(str(pendiente_visto)) - grupo["monto"]) > TOLERANCIA:
        raise ValueError(
            "Lo pendiente de este proveedor cambió (alguien registró otro pago). "
            "Revisa los montos y vuelve a intentarlo.")

    elegidas = grupo["unidades"]
    if unidades is not None:
        claves = {u if isinstance(u, str) else f"{u[0]}:{u[1]}" for u in unidades}
        elegidas = [u for u in grupo["unidades"] if _clave_unidad(u) in claves]
        if not elegidas:
            raise ValueError("Elige al menos un concepto para pagar.")
    por_pagar = sum((Decimal(str(u["monto"])) for u in elegidas), CERO)

    if fraccion is not None:
        monto = (por_pagar * Decimal(str(fraccion))).quantize(Decimal("0.01"))
    parcial = False
    if monto is not None:
        monto = Decimal(str(monto)).quantize(Decimal("0.01"))
        if monto <= 0:
            raise ValueError("El monto a pagar debe ser mayor a cero.")
        if monto > por_pagar + TOLERANCIA:
            raise ValueError("El monto excede lo que falta por pagar de los conceptos elegidos.")
        parcial = monto < por_pagar - TOLERANCIA

    if centro is None:
        centro = CentroDeCosto.objects.filter(slug=CENTRO_SLUG).first()
    if centro is None:
        logger.warning("proyecto=%s: centro '%s' ausente — no se registra el pago.",
                       proyecto.pk, CENTRO_SLUG)
        return vacio

    if proveedor is None:
        proveedor = grupo["proveedor"]
    proveedor_nombre = (proveedor.razon_social if proveedor is not None
                        else "Gasto de proyecto")[:200]
    fecha = fecha or date.today()
    banco_o_caja = "caja" if metodo == "efectivo" else "banco"

    a_liquidar, a_crear = [], []
    for u in elegidas:
        eg = u.get("egreso")
        if eg is not None and not eg.anulado and eg.estado_pago == "pendiente":
            a_liquidar.append((u, eg))
        else:
            a_crear.append(u)

    if parcial and a_liquidar:
        nombres = ", ".join(u["label"] for u, _eg in a_liquidar[:2])
        raise ValueError(
            f"«{nombres}» ya está registrado como cuenta por pagar y se liquida "
            "completo: desmárcalo o paga todo.")

    liquidados = []
    for _u, eg in a_liquidar:
        campos = []
        if proveedor is not None and eg.proveedor_id != proveedor.pk:
            eg.proveedor = proveedor
            eg.proveedor_nombre = proveedor_nombre
            campos += ["proveedor", "proveedor_nombre"]
        if solicitado_por is not None and eg.solicitado_por_id != solicitado_por.pk:
            eg.solicitado_por = solicitado_por
            campos.append("solicitado_por")
        if campos:
            eg.save(update_fields=campos + ["actualizado_en"])
        liquidar_egreso_pendiente(
            eg, estado_destino=estado_pago, metodo=metodo,
            banco_o_caja=banco_o_caja, fecha=fecha, pagado_por=pagado_por,
            actor=actor,
        )
        liquidados.append(eg)

    # Cuánto abona este pago a cada concepto (sin IVA). Completo = lo que le falta.
    restantes = [Decimal(str(u["monto"])) for u in a_crear]
    abonos = repartir_proporcional(monto, restantes) if parcial else restantes
    monto_nuevo = sum(abonos, CERO)

    creado = None
    if a_crear and monto_nuevo > 0:
        etiquetas = [u["label"] for u in a_crear]
        detalle = " · ".join(etiquetas[:3])
        if len(etiquetas) > 3:
            detalle += f" · +{len(etiquetas) - 3} más"
        if parcial:
            prefijo = (etiqueta or "Pago parcial").strip()
        elif any(Decimal(str(u.get("pagado_parcial") or 0)) > 0 for u in a_crear):
            prefijo = "Liquidación"
        else:
            prefijo = ""
        if prefijo:
            detalle = f"{prefijo} · {detalle}"
        descripcion = f"Proyecto {proyecto.codigo} · {proveedor_nombre} · {detalle}"[:300]
        with transaction.atomic():
            creado = Egreso.objects.create(
                monto=monto_nuevo.quantize(Decimal("0.01")), fecha=fecha,
                descripcion=descripcion, proveedor=proveedor,
                proveedor_nombre=proveedor_nombre, centro_de_costo=centro,
                proyecto=proyecto, estado_pago=estado_pago or "pagado",
                metodo=metodo or "transferencia", pagado_por=pagado_por,
                solicitado_por=solicitado_por, origen="proyecto",
                creado_por=_quien(actor),
            )
            for u, abono, falta in zip(a_crear, abonos, restantes, strict=True):
                if abono <= 0:
                    continue
                obj = _obj_de(proyecto, u["clase"], u["pk"])
                if obj is None:
                    continue
                PagoGasto.objects.create(
                    egreso=creado, monto=abono,
                    **{"producto" if u["clase"] == "producto" else "proceso": obj})
                if abono >= falta:  # este pago termina de cubrirlo → queda «pagado»
                    obj.egreso = creado
                    obj.save(update_fields=["egreso"])

    en_cxp = sum((Decimal(str(u["monto"])) for u, _eg in a_liquidar), CERO)
    restante = max(CERO, (por_pagar - monto_nuevo - en_cxp).quantize(Decimal("0.01")))
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="proyecto.gasto_registrado",
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", None),
            payload={"proyecto_id": proyecto.pk, "codigo": proyecto.codigo,
                     "agrupado_por_proveedor": True,
                     "proveedor": proveedor_nombre,
                     "unidades": len(elegidas), "parcial": parcial,
                     "monto": float(monto_nuevo),
                     "egreso_codigo": creado.codigo if creado else "",
                     "liquidados": [e.codigo for e in liquidados]},
        ))
    return {"creado": creado, "liquidados": liquidados,
            "unidades": len(elegidas), "parcial": parcial, "restante": restante}


def _obj_de(proyecto, clase: str, pk: int):
    from .models import ProyectoProducto, ProyectoProductoProceso
    if clase == "producto":
        return ProyectoProducto.objects.filter(proyecto=proyecto, pk=pk).first()
    if clase == "proceso":
        return ProyectoProductoProceso.objects.filter(producto__proyecto=proyecto, pk=pk).first()
    return None


def _datos_egreso(proyecto, clase: str, obj):
    """(monto, proveedor, proveedor_nombre, descripcion) para el egreso."""
    if clase == "producto":
        monto = Decimal(str(obj.costo_total_linea)).quantize(Decimal("0.01"))
        proveedor = obj.proveedor
        etiqueta = _label_produccion(obj)
    else:  # proceso
        monto = _monto_proceso(obj, obj.producto)
        proveedor = obj.proveedor  # impresión u operativo con proveedor (@)
        etiqueta = _label_proceso(obj, obj.producto)
    # Un concepto con abonos parciales sólo registra lo que le FALTA (si no, el
    # egreso duplicaría lo ya pagado).
    monto = max(CERO, (monto - _abonado(obj)).quantize(Decimal("0.01")))
    proveedor_nombre = (proveedor.razon_social if proveedor else "Gasto de proyecto")[:200]
    descripcion = f"Proyecto {proyecto.codigo} · {etiqueta}"[:300]
    return monto, proveedor, proveedor_nombre, descripcion


def datos_para_modal(proyecto, clase: str, pk: int):
    """Info de la unidad de gasto para precargar el modal 'Registrar'.
    Devuelve `{monto, label, proveedor, ya_registrado}` o None."""
    obj = _obj_de(proyecto, clase, pk)
    if obj is None:
        return None
    monto, proveedor, proveedor_nombre, descripcion = _datos_egreso(proyecto, clase, obj)
    eg = obj.egreso
    pendiente = eg is not None and not eg.anulado and eg.estado_pago == "pendiente"
    return {
        "monto": monto, "label": getattr(obj, "etiqueta", descripcion),
        "proveedor": proveedor, "proveedor_nombre": proveedor_nombre,
        "ya_registrado": _registrado(obj.egreso),
        "pagado": _pagado(obj.egreso),
        "egreso": eg,
        "pendiente": pendiente,
    }


def registrar_egreso(proyecto, clase: str, pk: int, *, actor=None,
                     centro=None, metodo="transferencia", estado_pago="pendiente",
                     pagado_por=None, solicitado_por=None, proveedor=None, fecha=None):
    """Crea el Egreso de una unidad de gasto y lo liga. Idempotente (si ya
    tiene egreso vigente, lo devuelve). Devuelve el Egreso o None si no se
    pudo (catálogo incompleto / objeto inexistente / monto 0).

    Los parámetros opcionales (centro, metodo, estado_pago, pagado_por,
    solicitado_por, proveedor) vienen del modal "Registrar" (S-LC-Feedback-V8 /
    V2). Sin ellos usa los defaults (centro `insumos-de-proyecto`,
    transferencia, pendiente, proveedor derivado del gasto). `proveedor`
    permite elegir/corregir el proveedor desde el modal."""
    from apps.tesoreria.models import CentroDeCosto, Egreso

    obj = _obj_de(proyecto, clase, pk)
    if obj is None:
        return None
    if _registrado(obj.egreso):
        return obj.egreso

    monto, proveedor_def, proveedor_nombre, descripcion = _datos_egreso(proyecto, clase, obj)
    if proveedor is not None:
        proveedor_def = proveedor
        proveedor_nombre = (proveedor.razon_social or proveedor_nombre)[:200]
    proveedor = proveedor_def
    if monto <= 0:
        return None
    if centro is None:
        centro = CentroDeCosto.objects.filter(slug=CENTRO_SLUG).first()
    if centro is None:
        logger.warning("proyecto=%s: centro '%s' ausente — no se registra el gasto.",
                       proyecto.pk, CENTRO_SLUG)
        return None

    with transaction.atomic():
        egreso = Egreso.objects.create(
            monto=monto, fecha=fecha or date.today(), descripcion=descripcion,
            proveedor=proveedor, proveedor_nombre=proveedor_nombre,
            centro_de_costo=centro, proyecto=proyecto,
            estado_pago=estado_pago or "pendiente", metodo=metodo or "transferencia",
            pagado_por=pagado_por, solicitado_por=solicitado_por, origen="proyecto",
            creado_por=_quien(actor),
        )
        obj.egreso = egreso
        obj.save(update_fields=["egreso"])

    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="proyecto.gasto_registrado",
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", None),
            payload={"proyecto_id": proyecto.pk, "codigo": proyecto.codigo,
                     "clase": clase, "monto": float(monto), "egreso_codigo": egreso.codigo},
        ))
    return egreso


def registrar_pendientes(proyecto, *, actor=None) -> list:
    """Registra TODOS los gastos pendientes del proyecto. Devuelve los egresos
    creados. Usado por el botón 'registrar todos' y por el signal de producción."""
    creados = []
    for u in pendientes_de(proyecto):
        eg = registrar_egreso(proyecto, u["clase"], u["pk"], actor=actor)
        if eg is not None:
            creados.append(eg)
    return creados


# ── Vista global para Tesorería ──────────────────────────────────────────

def proyectos_con_pendientes():
    """Lista [{proyecto, unidades, subtotal}] de proyectos no cancelados con
    gastos sin registrar. Para la página 'Gastos no registrados' de Tesorería."""
    from .models import Proyecto
    salida = []
    qs = (
        Proyecto.objects.filter(estado__in=ESTADOS_CON_GASTOS)
        .prefetch_related("productos", "productos__procesos")
    )
    for proyecto in qs:
        pend = pendientes_de(proyecto)
        if pend:
            subtotal = sum((u["monto"] for u in pend), CERO)
            salida.append({"proyecto": proyecto, "unidades": pend, "subtotal": subtotal})
    salida.sort(key=lambda d: d["subtotal"], reverse=True)
    return salida


def conteo_no_registrados() -> dict:
    """{cantidad, total} de gastos no registrados (para el KPI de Tesorería)."""
    cantidad = 0
    total = CERO
    for grupo in proyectos_con_pendientes():
        cantidad += len(grupo["unidades"])
        total += grupo["subtotal"]
    return {"cantidad": cantidad, "total": total.quantize(Decimal("0.01"))}
