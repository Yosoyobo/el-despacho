"""Los KPIs de desempeño: ventas y cobranza, entregas y equipo, rentabilidad,
control y papeleo, y lo que faltaba medir del resto del negocio (2026-09-29).

Oscar, en la ronda de KPIs: «lo que sea que me falte y no esté viendo». A
diferencia del catálogo original, cada uno declara aquí mismo cómo se juzga
(`direccion`, `acumula`, `formato`) y, cuando el dato lo permite, cómo se
reparte por persona o por cliente (`desglose`), que es lo que habilita ponerle
meta a una persona o a un cliente.

Reglas que siguen todos:

- **El valor es un número**, nunca texto pintado («$12,345»): la tarjeta lo
  formatea con `formato`, y la foto diaria, las metas y los umbrales lo leen tal
  cual.
- **Vacío no es cero.** Un promedio o un porcentaje sin nada que promediar
  devuelve «—» con la nota «sin datos», no un 0 inventado. Un conteo o una suma
  sí son cero de verdad cuando no hay nada: «cero facturas canceladas» es un
  dato.
- **Un KPI roto no tumba el tablero**: si el cálculo truena, sale «—» y queda
  la advertencia en el log (`_protegido`). Las pruebas vigilan ese log, para
  que un campo mal escrito no se esconda detrás del «—».
- **Duraciones en Python**: se traen los pares de fechas (ventanas acotadas) y
  se resta aquí, para no depender de la aritmética de fechas del motor
  (las pruebas corren en SQLite y producción en Postgres 16).
- **El reparto (`desglose`) sale de la misma cuenta que el valor**: la suma de
  un reparto de dinero u horas es el valor; en los porcentajes, cada persona o
  cliente trae su propio porcentaje y el valor es el del conjunto.
- Los porcentajes se miden sobre una ventana móvil (30 o 90 días) y no
  «acumulan»: una meta de 90% no se prorratea por el avance del mes.
"""

from __future__ import annotations

import functools
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

# Tolerancia para llamar «puntual» a una parada con hora de cita.
TOLERANCIA_PARADA_MIN = 15

# Estados de proyecto en los que el trabajo está vivo (igual que `kpis.py`).
_PROYECTO_ACTIVO = ("en_proceso_diseno", "en_proceso_produccion")


# ── Utilidades ───────────────────────────────────────────────────────────


def _res(valor, *, nota: str = "", link: str = "") -> dict:
    return {"valor": valor, "nota": nota, "link": link}


def _sin_datos(link: str = "", nota: str = "sin datos") -> dict:
    """Lo que se enseña cuando no hay con qué medir: no es un cero."""
    return {"valor": "—", "nota": nota, "link": link}


def _protegido(link: str):
    """El cálculo, pero si truena sale «—» y queda la advertencia en el log."""
    def deco(fn):
        @functools.wraps(fn)
        def envoltura(user):
            try:
                return fn(user)
            except Exception:  # noqa: BLE001 — un KPI roto no tumba el tablero
                logger.warning("KPI de desempeño falló: %s", fn.__name__, exc_info=True)
                return _sin_datos(link)
        return envoltura
    return deco


def _reparto(*ambitos: str):
    """`desglose(ambito)`: el reparto si ese ámbito se sabe dar; `{}` si no o si
    la cuenta truena (con su advertencia en el log)."""
    def deco(fn):
        @functools.wraps(fn)
        def envoltura(ambito: str) -> dict[int, float]:
            if ambito not in ambitos:
                return {}
            try:
                return fn(ambito)
            except Exception:  # noqa: BLE001
                logger.warning("Desglose de KPI falló: %s", fn.__name__, exc_info=True)
                return {}
        return envoltura
    return deco


def _hoy() -> date:
    from django.utils import timezone
    return timezone.localdate()


def _inicio_mes() -> date:
    return _hoy().replace(day=1)


def _hace(dias: int) -> date:
    return _hoy() - timedelta(days=dias)


def _dia(valor) -> date | None:
    """La fecha local de un `datetime` (o la fecha tal cual)."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        from django.utils import timezone
        return timezone.localtime(valor).date() if timezone.is_aware(valor) else valor.date()
    return valor


def _dias_entre(inicio, fin) -> float | None:
    """Días (con fracción si son horas) de `inicio` a `fin`; None si falta uno
    o si el orden es imposible (un sello mal capturado no promedia)."""
    if inicio is None or fin is None:
        return None
    if isinstance(inicio, datetime) and isinstance(fin, datetime):
        dias = (fin - inicio).total_seconds() / 86400
    else:
        dias = float((_dia(fin) - _dia(inicio)).days)
    return dias if dias >= 0 else None


def _promedio(valores) -> float | None:
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


def _pct(parte, total) -> float | None:
    return round(float(parte) / float(total) * 100, 1) if total else None


def _redondo(valor, decimales: int = 1):
    return round(float(valor), decimales)


def _solo_lo_suyo(user) -> bool:
    from lib.permisos import solo_proyectos_asignados
    return solo_proyectos_asignados(user)


def _total(documento) -> Decimal:
    """El total de una cotización o factura, con sus impuestos."""
    return documento.calcular_totales()["total"]


def _num_desglose(reparto: dict) -> dict[int, float]:
    return {pk: _redondo(v, 2) for pk, v in reparto.items() if pk is not None}


# ═════════════════════════════════════════════════════════════════════════
# 1. Ventas y cobranza
# ═════════════════════════════════════════════════════════════════════════

_L_COT = "/cotizaciones/"
_L_FAC = "/facturacion/"


@_protegido(_L_COT)
def _kpi_dias_para_aprobar(user) -> dict:
    """De enviada a aprobada, cotizaciones aprobadas en 90 días."""
    from apps.cotizaciones.models import Cotizacion

    pares = Cotizacion.vigentes.filter(
        aprobada_en__date__gte=_hace(90), enviada_en__isnull=False,
    ).values_list("enviada_en", "aprobada_en")
    dias = [_dias_entre(e, a) for e, a in pares]
    prom = _promedio(dias)
    if prom is None:
        return _sin_datos(_L_COT)
    n = len([d for d in dias if d is not None])
    return _res(_redondo(prom), nota=f"{n} aprobadas, 90 días", link=_L_COT)


@_protegido(_L_COT)
def _kpi_dias_para_enviar(user) -> dict:
    """De creada a enviada: cuánto tarda en salir una cotización."""
    from apps.cotizaciones.models import Cotizacion

    pares = Cotizacion.vigentes.filter(
        enviada_en__date__gte=_hace(90),
    ).values_list("creado_en", "enviada_en")
    dias = [_dias_entre(c, e) for c, e in pares]
    prom = _promedio(dias)
    if prom is None:
        return _sin_datos(_L_COT)
    n = len([d for d in dias if d is not None])
    return _res(_redondo(prom), nota=f"{n} enviadas, 90 días", link=_L_COT)


@_protegido(_L_COT)
def _kpi_cotizacion_a_factura(user) -> dict:
    """De las aprobadas en 90 días, cuántas ya tienen su factura."""
    from apps.cotizaciones.models import Cotizacion
    from django.db.models import Count, Q

    qs = Cotizacion.vigentes.filter(aprobada_en__date__gte=_hace(90)).annotate(
        n_fac=Count("facturas", filter=~Q(facturas__estado="cancelada")),
    )
    total = qs.count()
    con_factura = qs.filter(n_fac__gt=0).count()
    pct = _pct(con_factura, total)
    if pct is None:
        return _sin_datos(_L_COT)
    return _res(pct, nota=f"{con_factura} de {total} aprobadas", link=_L_COT)


@_protegido(_L_FAC)
def _kpi_dias_de_cobro(user) -> dict:
    """De emitida a cobrada por completo (último cobro vigente), 90 días."""
    from apps.facturacion.models import Factura
    from django.db.models import Max, Q

    filas = (
        Factura.objects.filter(estado="cobrada_total")
        .annotate(ultimo=Max("cobros__fecha", filter=Q(cobros__anulado=False)))
        .filter(ultimo__gte=_hace(90))
        .values_list("emitida_en", "fecha_emision", "ultimo")
    )
    dias = [_dias_entre(_dia(emitida) or emision, ultimo) for emitida, emision, ultimo in filas]
    prom = _promedio(dias)
    if prom is None:
        return _sin_datos(_L_FAC)
    n = len([d for d in dias if d is not None])
    return _res(_redondo(prom), nota=f"{n} facturas cobradas, 90 días", link=_L_FAC)


@_protegido(_L_COT)
def _kpi_descuento_promedio(user) -> dict:
    """Descuento global promedio de lo que se envió al cliente en 90 días."""
    from apps.cotizaciones.models import Cotizacion
    from django.db.models import Avg, Count

    agg = Cotizacion.vigentes.filter(enviada_en__date__gte=_hace(90)).aggregate(
        p=Avg("descuento_global_porcentaje"), n=Count("pk"),
    )
    if not agg["n"]:
        return _sin_datos(_L_COT)
    return _res(_redondo(agg["p"] or 0), nota=f"{agg['n']} enviadas, 90 días", link=_L_COT)


@_protegido(_L_COT)
def _kpi_rechazadas_mes(user) -> dict:
    from apps.cotizaciones.models import Cotizacion

    n = Cotizacion.objects.filter(
        estado="rechazada", rechazada_en__date__gte=_inicio_mes(),
    ).count()
    return _res(n, link=f"{_L_COT}?estado=rechazada")


@_protegido(_L_COT)
def _kpi_por_vencer_7d(user) -> dict:
    from apps.cotizaciones.models import Cotizacion

    hoy = _hoy()
    n = Cotizacion.objects.filter(
        estado="enviada", fecha_validez__gte=hoy, fecha_validez__lte=hoy + timedelta(days=7),
    ).count()
    return _res(n, nota="vencen en 7 días" if n else "", link=f"{_L_COT}?estado=enviada")


def _aprobadas_mes():
    """Cotizaciones aprobadas este mes (con sus renglones precargados)."""
    from apps.cotizaciones.models import Cotizacion

    return (
        Cotizacion.vigentes.filter(aprobada_en__date__gte=_inicio_mes())
        .exclude(estado="rechazada")
        .prefetch_related("items")
    )


def _vendido_por_persona() -> dict[int | None, Decimal]:
    reparto: dict[int | None, Decimal] = defaultdict(Decimal)
    for cot in _aprobadas_mes():
        reparto[cot.creado_por_id] += _total(cot)
    return reparto


@_protegido(_L_COT)
def _kpi_vendido_mes(user) -> dict:
    """Lo aprobado este mes, en pesos. Se reparte por quien hizo la cotización."""
    reparto = _vendido_por_persona()
    total = sum(reparto.values(), Decimal("0"))
    sin_autor = reparto.get(None)
    nota = f"{len([k for k in reparto if k])} personas"
    if sin_autor:
        nota += f" · ${sin_autor:,.0f} sin autor"
    return _res(_redondo(total, 2), nota=nota, link=f"{_L_COT}?estado=aprobada")


@_reparto("persona")
def _desglose_vendido_mes(ambito: str) -> dict[int, float]:
    return _num_desglose(_vendido_por_persona())


@_protegido(_L_COT)
def _kpi_ticket_cotizacion(user) -> dict:
    """Monto promedio de una cotización aprobada (90 días)."""
    from apps.cotizaciones.models import Cotizacion

    qs = (
        Cotizacion.vigentes.filter(aprobada_en__date__gte=_hace(90))
        .exclude(estado="rechazada").prefetch_related("items")
    )
    totales = [float(_total(c)) for c in qs]
    prom = _promedio(totales)
    if prom is None:
        return _sin_datos(_L_COT)
    return _res(_redondo(prom, 2), nota=f"{len(totales)} aprobadas, 90 días", link=_L_COT)


@_protegido(_L_FAC)
def _kpi_cobrado_de_facturado(user) -> dict:
    """De lo facturado en 90 días, qué parte ya entró."""
    from apps.facturacion.models import ESTADOS_FACTURADA, Factura

    qs = Factura.objects.filter(
        estado__in=ESTADOS_FACTURADA, emitida_en__date__gte=_hace(90),
    ).prefetch_related("items")
    facturado = Decimal("0")
    cobrado = Decimal("0")
    for f in qs:
        facturado += _total(f)
        cobrado += f.monto_cobrado or Decimal("0")
    pct = _pct(min(cobrado, facturado), facturado)
    if pct is None:
        return _sin_datos(_L_FAC)
    return _res(pct, nota=f"${cobrado:,.0f} de ${facturado:,.0f}", link=_L_FAC)


def _facturado_por_cliente_mes() -> dict[int, Decimal]:
    """Mismo universo que «Facturado del mes»: emitidas este mes, no canceladas."""
    from apps.facturacion.models import Factura

    hoy = _hoy()
    reparto: dict[int, Decimal] = defaultdict(Decimal)
    qs = Factura.objects.exclude(estado="cancelada").filter(
        emitida_en__year=hoy.year, emitida_en__month=hoy.month,
    ).prefetch_related("items")
    for f in qs:
        reparto[f.cliente_id] += _total(f)
    return reparto


@_protegido(_L_FAC)
def _kpi_facturado_por_cliente_mes(user) -> dict:
    reparto = _facturado_por_cliente_mes()
    total = sum(reparto.values(), Decimal("0"))
    return _res(_redondo(total, 2), nota=f"{len(reparto)} clientes", link=_L_FAC)


@_reparto("cliente")
def _desglose_facturado_por_cliente_mes(ambito: str) -> dict[int, float]:
    return _num_desglose(_facturado_por_cliente_mes())


# ═════════════════════════════════════════════════════════════════════════
# 2. Entregas y equipo
# ═════════════════════════════════════════════════════════════════════════

_L_PRY = "/proyectos/"
_L_TAREAS = "/tareas/"
_L_EQUIPO = "/checador/equipo/"


def _entregados_90d(user):
    from apps.los_proyectos.models import Proyecto

    qs = Proyecto.objects.filter(
        archivado=False, fecha_real_entrega__gte=_hace(90),
    ).exclude(estado="cancelado")
    if _solo_lo_suyo(user):
        qs = qs.filter(asignaciones__usuario=user).distinct()
    return qs


@_protegido(_L_PRY)
def _kpi_proyectos_a_tiempo(user) -> dict:
    """Entregados en 90 días en o antes de su fecha de compromiso."""
    filas = _entregados_90d(user).filter(fecha_compromiso__isnull=False).values_list(
        "fecha_real_entrega", "fecha_compromiso",
    )
    total = 0
    a_tiempo = 0
    for entrega, compromiso in filas:
        total += 1
        if entrega <= _dia(compromiso):
            a_tiempo += 1
    pct = _pct(a_tiempo, total)
    if pct is None:
        return _sin_datos(_L_PRY)
    return _res(pct, nota=f"{a_tiempo} de {total} entregas, 90 días", link=_L_PRY)


@_protegido(_L_PRY)
def _kpi_duracion_proyecto(user) -> dict:
    """Días de arranque (o de alta, si no se capturó arranque) a entrega."""
    filas = _entregados_90d(user).values_list("fecha_inicio", "creado_en", "fecha_real_entrega")
    dias = [_dias_entre(_dia(inicio or creado), entrega) for inicio, creado, entrega in filas]
    prom = _promedio(dias)
    if prom is None:
        return _sin_datos(_L_PRY)
    n = len([d for d in dias if d is not None])
    return _res(_redondo(prom), nota=f"{n} entregados, 90 días", link=_L_PRY)


def _tareas_cerradas_30d():
    """(asignada_a, ¿a tiempo?) de las tareas cerradas en 30 días con fecha."""
    from apps.el_pizarron.models import Tarea
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea

    filas = Tarea.objects.filter(
        estado__in=slugs_terminales_tarea(), completada_en__date__gte=_hace(30),
        fecha_compromiso__isnull=False,
    ).values_list("asignada_a_id", "completada_en", "fecha_compromiso")
    return [(persona, _dia(cerrada) <= compromiso) for persona, cerrada, compromiso in filas]


@_protegido(_L_TAREAS)
def _kpi_tareas_a_tiempo(user) -> dict:
    filas = _tareas_cerradas_30d()
    a_tiempo = sum(1 for _, ok in filas if ok)
    pct = _pct(a_tiempo, len(filas))
    if pct is None:
        return _sin_datos(_L_TAREAS)
    return _res(pct, nota=f"{a_tiempo} de {len(filas)} cerradas, 30 días", link=_L_TAREAS)


@_reparto("persona")
def _desglose_tareas_a_tiempo(ambito: str) -> dict[int, float]:
    cuenta: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for persona, ok in _tareas_cerradas_30d():
        if persona is None:
            continue
        cuenta[persona][1] += 1
        cuenta[persona][0] += int(ok)
    return {pk: _pct(ok, total) for pk, (ok, total) in cuenta.items()}


def _tareas_abiertas_por_persona() -> dict[int, int]:
    from apps.el_pizarron.models import Tarea
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    from django.db.models import Count

    filas = (
        Tarea.objects.filter(archivada=False, asignada_a__isnull=False)
        .exclude(estado__in=slugs_terminales_tarea())
        .values("asignada_a").annotate(n=Count("pk"))
    )
    return {f["asignada_a"]: f["n"] for f in filas}


@_protegido(_L_TAREAS)
def _kpi_tareas_abiertas_persona(user) -> dict:
    reparto = _tareas_abiertas_por_persona()
    total = sum(reparto.values())
    nota = f"entre {len(reparto)} personas" if reparto else ""
    return _res(total, nota=nota, link=_L_TAREAS)


@_reparto("persona")
def _desglose_tareas_abiertas(ambito: str) -> dict[int, float]:
    return {pk: float(n) for pk, n in _tareas_abiertas_por_persona().items()}


def _minutos_horario(horario) -> int:
    """Minutos esperados de un horario (salida − entrada)."""
    base = date(2000, 1, 1)
    ent = datetime.combine(base, horario.hora_entrada)
    sal = datetime.combine(base, horario.hora_salida)
    return int((sal - ent).total_seconds() // 60) if sal > ent else 0


def _horas_extra_por_persona() -> dict[int, float] | None:
    """Horas trabajadas arriba de su horario, por persona, este mes.

    OJO: `Jornada.minutos_extra` NO son horas extra —son los segmentos previos
    del mismo día (la persona checó salida y volvió a entrar)—. Las horas extra
    son lo trabajado contra lo esperado de su horario (misma precedencia que
    `checador.services.horario_vigente`: su horario propio completo, o el
    global si no declaró uno). Un día sin horario es día libre: todo lo que se
    trabaje ahí cuenta como extra. Quien no tiene ningún horario (ni propio ni
    global) no se puede medir y no entra. `None` si nadie se puede medir.
    """
    from apps.checador.models import HorarioLaboral, Jornada

    propios: dict[int, dict[int, int]] = defaultdict(dict)
    globales: dict[int, int] = {}
    # `setdefault`: si hay dos para el mismo día manda el primero, como el
    # `.first()` de `horario_vigente`.
    for h in HorarioLaboral.objects.filter(activo=True):
        if h.usuario_id is None:
            globales.setdefault(h.dia_semana, _minutos_horario(h))
        else:
            propios[h.usuario_id].setdefault(h.dia_semana, _minutos_horario(h))

    extra: dict[int, float] = defaultdict(float)
    medibles = 0
    jornadas = Jornada.objects.filter(fecha__gte=_inicio_mes()).only(
        "usuario_id", "fecha", "entrada_en", "salida_en", "minutos_extra",
    )
    for j in jornadas:
        horario = propios.get(j.usuario_id)
        if horario is None:
            if not globales:
                continue  # sin ningún horario: no se puede medir
            horario = globales
        trabajado = j.minutos_trabajados or 0
        esperado = horario.get(j.fecha.weekday(), 0)
        medibles += 1
        if trabajado > esperado:
            extra[j.usuario_id] += (trabajado - esperado) / 60
        else:
            extra.setdefault(j.usuario_id, 0.0)
    if not medibles:
        return None
    return dict(extra)


@_protegido(_L_EQUIPO)
def _kpi_horas_extra_mes(user) -> dict:
    reparto = _horas_extra_por_persona()
    if reparto is None:
        return _sin_datos(_L_EQUIPO, "sin horarios o sin jornadas")
    return _res(_redondo(sum(reparto.values())), nota="arriba del horario de cada quien",
                link=_L_EQUIPO)


@_reparto("persona")
def _desglose_horas_extra(ambito: str) -> dict[int, float]:
    return {pk: _redondo(h, 2) for pk, h in (_horas_extra_por_persona() or {}).items()}


@_protegido("/checador/correcciones/")
def _kpi_correcciones_pendientes(user) -> dict:
    from apps.checador.models import SolicitudCorreccion
    from django.utils import timezone

    qs = SolicitudCorreccion.objects.filter(estado="pendiente")
    n = qs.count()
    viejas = qs.filter(creado_en__lt=timezone.now() - timedelta(days=3)).count()
    nota = "alerta" if viejas else ("esperan respuesta" if n else "")
    return _res(n, nota=nota, link="/checador/correcciones/")


def _checadas_30d() -> tuple[int, int, int]:
    """(checadas, sin ubicación, fuera de línea) de entradas y salidas, 30 días."""
    from apps.checador.models import Jornada

    total = sin_geo = offline = 0
    for ent_en, ent_geo, ent_off, sal_en, sal_geo, sal_off in Jornada.objects.filter(
        fecha__gte=_hace(30),
    ).values_list("entrada_en", "entrada_sin_geo", "entrada_offline",
                  "salida_en", "salida_sin_geo", "salida_offline"):
        for sello, geo, off in ((ent_en, ent_geo, ent_off), (sal_en, sal_geo, sal_off)):
            if sello is None:
                continue
            total += 1
            sin_geo += int(bool(geo))
            offline += int(bool(off))
    return total, sin_geo, offline


@_protegido(_L_EQUIPO)
def _kpi_checadas_sin_ubicacion(user) -> dict:
    total, sin_geo, _ = _checadas_30d()
    pct = _pct(sin_geo, total)
    if pct is None:
        return _sin_datos(_L_EQUIPO)
    return _res(pct, nota=f"{sin_geo} de {total} checadas, 30 días", link=_L_EQUIPO)


@_protegido(_L_EQUIPO)
def _kpi_checadas_fuera_de_linea(user) -> dict:
    total, _, offline = _checadas_30d()
    pct = _pct(offline, total)
    if pct is None:
        return _sin_datos(_L_EQUIPO)
    return _res(pct, nota=f"{offline} de {total} checadas, 30 días", link=_L_EQUIPO)


def _horas_equipo_mes() -> dict[int, float]:
    from apps.checador.models import Jornada

    reparto: dict[int, float] = defaultdict(float)
    for j in Jornada.objects.filter(fecha__gte=_inicio_mes()).only(
        "usuario_id", "entrada_en", "salida_en", "minutos_extra",
    ):
        reparto[j.usuario_id] += (j.minutos_trabajados or 0) / 60
    return dict(reparto)


@_protegido(_L_EQUIPO)
def _kpi_horas_equipo_mes(user) -> dict:
    reparto = _horas_equipo_mes()
    return _res(_redondo(sum(reparto.values())), nota=f"{len(reparto)} personas",
                link=_L_EQUIPO)


@_reparto("persona")
def _desglose_horas_equipo_mes(ambito: str) -> dict[int, float]:
    return {pk: _redondo(h, 2) for pk, h in _horas_equipo_mes().items()}


# ═════════════════════════════════════════════════════════════════════════
# 3. Rentabilidad
# ═════════════════════════════════════════════════════════════════════════

_L_ING = "/tesoreria/ingresos/"
_L_EGR = "/tesoreria/egresos/"
_L_RENT = "/analisis/#rentabilidad"


def _cobrado_por_cliente_12m() -> dict[int, Decimal]:
    from apps.tesoreria.models import Ingreso
    from django.db.models import Sum

    filas = (
        Ingreso.vigentes.filter(fecha__gte=_hace(365), cliente__isnull=False)
        .values("cliente").annotate(t=Sum("monto"))
    )
    return {f["cliente"]: f["t"] or Decimal("0") for f in filas}


@_protegido(_L_ING)
def _kpi_cobrado_por_cliente(user) -> dict:
    """Lo cobrado a clientes en 12 meses (los cobros sin cliente no entran)."""
    reparto = _cobrado_por_cliente_12m()
    total = sum(reparto.values(), Decimal("0"))
    return _res(_redondo(total, 2), nota=f"{len(reparto)} clientes, 12 meses", link=_L_ING)


@_reparto("cliente")
def _desglose_cobrado_por_cliente(ambito: str) -> dict[int, float]:
    return _num_desglose(_cobrado_por_cliente_12m())


def _rentabilidad_por_cliente() -> dict[int, list[float]]:
    """{cliente: [ingreso, costo]} de los proyectos dados de alta en 12 meses,
    con la misma cuenta de `los_proyectos.rentabilidad` (materiales)."""
    from apps.los_proyectos import rentabilidad as rent
    from apps.los_proyectos.models import Proyecto

    cliente_de = dict(
        Proyecto.objects.filter(creado_en__date__gte=_hace(365)).values_list("pk", "cliente_id")
    )
    if not cliente_de:
        return {}
    reparto: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for fila in rent.tabla():
        cliente = cliente_de.get(fila["id"])
        if cliente is None or fila["ingreso"] <= 0:
            continue
        reparto[cliente][0] += fila["ingreso"]
        reparto[cliente][1] += fila["costo_materiales"]
    return dict(reparto)


@_protegido(_L_RENT)
def _kpi_margen_por_cliente(user) -> dict:
    """Margen (materiales) de lo vendido en 12 meses. El número es el del
    despacho; lo que aporta es el reparto: permite meta de margen por cliente."""
    reparto = _rentabilidad_por_cliente()
    ingreso = sum(i for i, _ in reparto.values())
    costo = sum(c for _, c in reparto.values())
    pct = _pct(ingreso - costo, ingreso)
    if pct is None:
        return _sin_datos(_L_RENT)
    peor = min(reparto.items(), key=lambda kv: (kv[1][0] - kv[1][1]) / kv[1][0])
    from apps.la_cartera.models import Cliente
    nombre = Cliente.objects.filter(pk=peor[0]).values_list("razon_social", flat=True).first()
    return _res(pct, nota=f"el más bajo: {nombre}" if nombre else "", link=_L_RENT)


@_reparto("cliente")
def _desglose_margen_por_cliente(ambito: str) -> dict[int, float]:
    return {
        pk: _pct(ing - costo, ing) for pk, (ing, costo) in _rentabilidad_por_cliente().items()
    }


@_protegido(_L_EGR)
def _kpi_gasto_ligado_a_proyecto(user) -> dict:
    """Qué parte del gasto del mes se sabe a qué proyecto fue."""
    from apps.tesoreria.models import Egreso
    from django.db.models import Q, Sum

    agg = Egreso.vigentes.filter(fecha__gte=_inicio_mes()).aggregate(
        total=Sum("monto"), ligado=Sum("monto", filter=Q(proyecto__isnull=False)),
    )
    pct = _pct(agg["ligado"] or 0, agg["total"] or 0)
    if pct is None:
        return _sin_datos(_L_EGR, "sin gastos este mes")
    return _res(pct, nota=f"${agg['ligado'] or 0:,.0f} de ${agg['total']:,.0f}", link=_L_EGR)


def _gasto_por_cliente_mes() -> dict[int, Decimal]:
    from apps.tesoreria.models import Egreso
    from django.db.models import Sum

    filas = (
        Egreso.vigentes.filter(fecha__gte=_inicio_mes(), proyecto__isnull=False)
        .values("proyecto__cliente").annotate(t=Sum("monto"))
    )
    return {f["proyecto__cliente"]: f["t"] or Decimal("0") for f in filas}


@_protegido(_L_EGR)
def _kpi_gasto_por_cliente_mes(user) -> dict:
    reparto = _gasto_por_cliente_mes()
    total = sum(reparto.values(), Decimal("0"))
    return _res(_redondo(total, 2), nota=f"{len(reparto)} clientes", link=_L_EGR)


@_reparto("cliente")
def _desglose_gasto_por_cliente_mes(ambito: str) -> dict[int, float]:
    return _num_desglose(_gasto_por_cliente_mes())


def _horas_por_cliente_mes() -> dict[int, float] | None:
    from apps.los_proyectos.mano_obra import horas_por_proyecto
    from apps.los_proyectos.models import Proyecto

    horas = horas_por_proyecto(_inicio_mes(), _hoy())
    if not horas:
        return None
    cliente_de = dict(Proyecto.objects.filter(pk__in=list(horas)).values_list("pk", "cliente_id"))
    reparto: dict[int, float] = defaultdict(float)
    for pid, datos in horas.items():
        if pid in cliente_de:
            reparto[cliente_de[pid]] += datos["horas"]
    return dict(reparto)


@_protegido("/analisis/")
def _kpi_horas_por_cliente_mes(user) -> dict:
    """Horas del equipo que se pueden atribuir a proyectos este mes."""
    reparto = _horas_por_cliente_mes()
    if reparto is None:
        return _sin_datos("/analisis/", "sin horas en proyectos")
    return _res(_redondo(sum(reparto.values())), nota=f"{len(reparto)} clientes",
                link="/analisis/")


@_reparto("cliente")
def _desglose_horas_por_cliente(ambito: str) -> dict[int, float]:
    return {pk: _redondo(h, 2) for pk, h in (_horas_por_cliente_mes() or {}).items()}


@_protegido("/catalogo/proveedores/")
def _kpi_concentracion_proveedor(user) -> dict:
    """Qué parte de lo comprado (12 meses) se le compró a un solo proveedor."""
    from apps.tesoreria.models import Egreso
    from django.db.models import Sum

    filas = list(
        Egreso.vigentes.filter(fecha__gte=_hace(365), proveedor__isnull=False)
        .values("proveedor__razon_social").annotate(t=Sum("monto")).order_by("-t")
    )
    total = sum(float(f["t"] or 0) for f in filas)
    pct = _pct(float(filas[0]["t"] or 0), total) if filas else None
    if pct is None:
        return _sin_datos("/catalogo/proveedores/")
    return _res(pct, nota=filas[0]["proveedor__razon_social"] or "", link="/catalogo/proveedores/")


# ═════════════════════════════════════════════════════════════════════════
# 4. Control y papeleo
# ═════════════════════════════════════════════════════════════════════════

_L_CFDI = "/tesoreria/cfdi-recibidos/"
_L_CONCILIA = "/contaduria/conciliacion/"
_L_CIERRE = "/contaduria/cierre/"


@_protegido(_L_CFDI)
def _kpi_cfdi_entrantes_pendientes(user) -> dict:
    from apps.facturacion.models import ESTADO_PENDIENTE, CfdiEntrante
    from django.utils import timezone

    qs = CfdiEntrante.objects.filter(estado=ESTADO_PENDIENTE)
    n = qs.count()
    viejos = qs.filter(recibido_en__lt=timezone.now() - timedelta(days=7)).count()
    nota = "alerta" if viejos else ("por asignar" if n else "")
    return _res(n, nota=nota, link=_L_CFDI)


@_protegido(_L_CONCILIA)
def _kpi_lineas_sin_conciliar(user) -> dict:
    """Movimientos del banco sin cuadrar en las conciliaciones abiertas."""
    from apps.contaduria.models import LineaBancaria

    n = LineaBancaria.objects.filter(conciliada=False, conciliacion__estado="abierta").count()
    return _res(n, link=_L_CONCILIA)


@_protegido(_L_EGR)
def _kpi_egresos_sin_comprobante_mes(user) -> dict:
    from apps.tesoreria.models import Egreso

    n = Egreso.vigentes.filter(fecha__gte=_inicio_mes(), tiene_comprobante=False).count()
    return _res(n, nota="sin ticket ni factura adjunta" if n else "", link=_L_EGR)


def _fin_de_mes(inicio: date) -> date:
    siguiente = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
    return siguiente - timedelta(days=1)


@_protegido(_L_CIERRE)
def _kpi_meses_sin_cerrar(user) -> dict:
    """De los 12 meses completos anteriores, los que tienen asientos y ningún
    cierre vigente que los cubra."""
    from apps.contaduria.models import Asiento, CierrePeriodo

    inicio_mes = _inicio_mes()
    desde = (inicio_mes - timedelta(days=365)).replace(day=1)
    meses = list(
        Asiento.vigentes.filter(fecha__gte=desde, fecha__lt=inicio_mes).dates("fecha", "month")
    )
    if not meses:
        return _sin_datos(_L_CIERRE, "sin asientos en el año")
    cierres = list(CierrePeriodo.vigentes.values_list("desde", "hasta"))
    abiertos = [
        m for m in meses
        if not any(d <= m and h >= _fin_de_mes(m) for d, h in cierres)
    ]
    return _res(len(abiertos), nota=f"de {len(meses)} meses con movimientos", link=_L_CIERRE)


@_protegido("/tesoreria/por-pagar/")
def _kpi_dias_para_reembolsar(user) -> dict:
    """De que el empleado pone el dinero a que se le devuelve (90 días)."""
    from apps.tesoreria.models import METODOS_REEMBOLSO, Egreso

    pares = Egreso.vigentes.filter(
        metodo__in=METODOS_REEMBOLSO, pagado_en__gte=_hace(90),
    ).values_list("fecha", "pagado_en")
    dias = [_dias_entre(f, p) for f, p in pares]
    prom = _promedio(dias)
    if prom is None:
        return _sin_datos("/tesoreria/por-pagar/")
    n = len([d for d in dias if d is not None])
    return _res(_redondo(prom), nota=f"{n} reembolsos, 90 días", link="/tesoreria/por-pagar/")


@_protegido(_L_FAC)
def _kpi_facturas_canceladas_mes(user) -> dict:
    from apps.facturacion.models import Factura

    n = Factura.objects.filter(estado="cancelada", cancelada_en__date__gte=_inicio_mes()).count()
    return _res(n, link=f"{_L_FAC}?estado=cancelada")


@_protegido("/cartera/")
def _kpi_clientes_sin_rfc(user) -> dict:
    """Clientes activos sin RFC propio ni en alguna de sus razones sociales."""
    from apps.la_cartera.models import Cliente, ClienteRazonSocial

    con_rfc = ClienteRazonSocial.objects.exclude(rfc="").values("cliente_id")
    n = (
        Cliente.objects.filter(activo=True, estado="activo", rfc="")
        .exclude(pk__in=con_rfc).count()
    )
    return _res(n, nota="no se les puede facturar" if n else "", link="/cartera/")


@_protegido(_L_PRY)
def _kpi_proyectos_sin_documentos(user) -> dict:
    """Proyectos en diseño o producción sin ningún documento del archivo ligado."""
    from apps.los_proyectos.models import Proyecto

    from papeleo.models import PapeleoLigado

    ligados = PapeleoLigado.objects.filter(proyecto__isnull=False).values("proyecto_id")
    n = (
        Proyecto.objects.filter(estado__in=_PROYECTO_ACTIVO, archivado=False)
        .exclude(pk__in=ligados).count()
    )
    return _res(n, link=_L_PRY)


@_protegido(_L_EGR)
def _kpi_gastos_por_ocr(user) -> dict:
    """De los gastos capturados en 30 días, cuántos se leyeron de la foto del ticket."""
    from apps.tesoreria.models import Egreso
    from django.db.models import Count, Q

    agg = Egreso.vigentes.filter(creado_en__date__gte=_hace(30)).aggregate(
        total=Count("pk"), ocr=Count("pk", filter=Q(origen="ocr")),
    )
    pct = _pct(agg["ocr"], agg["total"])
    if pct is None:
        return _sin_datos(_L_EGR)
    return _res(pct, nota=f"{agg['ocr']} de {agg['total']} gastos, 30 días", link=_L_EGR)


@_protegido(_L_EGR)
def _kpi_ocr_corregidos(user) -> dict:
    """De los tickets leídos por la IA y guardados (30 días), cuántos hubo que corregir."""
    from apps.tesoreria.models import EgresoOcrLog
    from django.db.models import Count, Q

    agg = EgresoOcrLog.objects.filter(
        creado_en__date__gte=_hace(30), egreso__isnull=False,
    ).aggregate(total=Count("pk"), mal=Count("pk", filter=Q(fue_corregido=True)))
    pct = _pct(agg["mal"], agg["total"])
    if pct is None:
        return _sin_datos(_L_EGR)
    return _res(pct, nota=f"{agg['mal']} de {agg['total']} lecturas", link=_L_EGR)


# ═════════════════════════════════════════════════════════════════════════
# 5. Lo que faltaba: rutas, mandados, campañas, catálogo, visitas, cartera
# ═════════════════════════════════════════════════════════════════════════

_L_RUTAS = "/rutas/"
_L_MANDADOS = "/mandados/"


@_protegido(_L_RUTAS)
def _kpi_rutas_km_mes(user) -> dict:
    """Kilómetros planeados de las rutas que salieron este mes."""
    from apps.el_pizarron.models import Ruta
    from django.db.models import Count, Sum

    agg = Ruta.objects.filter(
        fecha__gte=_inicio_mes(), estado__in=("despachada", "cerrada"),
    ).aggregate(m=Sum("distancia_m"), n=Count("pk"))
    return _res(_redondo((agg["m"] or 0) / 1000), nota=f"{agg['n']} rutas", link=_L_RUTAS)


@_protegido(_L_RUTAS)
def _kpi_paradas_puntuales(user) -> dict:
    """Paradas con hora de cita entregadas a tiempo (con tolerancia), 30 días."""
    from apps.el_pizarron.models import ParadaRuta
    from django.utils import timezone

    filas = ParadaRuta.objects.filter(
        ruta__fecha__gte=_hace(30), ruta__estado__in=("despachada", "cerrada"),
        hora_cita__isnull=False, mandado__estado="entregado",
        mandado__entregado_en__isnull=False,
    ).values_list("ruta__fecha", "hora_cita", "mandado__entregado_en")
    total = puntuales = 0
    holgura = timedelta(minutes=TOLERANCIA_PARADA_MIN)
    for fecha, cita, entregado in filas:
        limite = timezone.make_aware(datetime.combine(fecha, cita)) + holgura
        total += 1
        puntuales += int(entregado <= limite)
    pct = _pct(puntuales, total)
    if pct is None:
        return _sin_datos(_L_RUTAS)
    return _res(pct, nota=f"{puntuales} de {total} citas, 30 días", link=_L_RUTAS)


@_protegido(_L_RUTAS)
def _kpi_rutas_sin_cerrar(user) -> dict:
    from apps.el_pizarron.models import Ruta

    n = Ruta.objects.filter(estado="despachada", fecha__lt=_hoy()).count()
    return _res(n, nota="alerta" if n else "", link=_L_RUTAS)


@_protegido(_L_MANDADOS)
def _kpi_minutos_para_asignar(user) -> dict:
    """De que se pide un mandado a que alguien lo toma (30 días)."""
    from apps.el_pizarron.models import Mandado

    pares = Mandado.objects.filter(asignado_en__date__gte=_hace(30)).values_list(
        "creado_en", "asignado_en",
    )
    dias = [_dias_entre(c, a) for c, a in pares]
    prom = _promedio(dias)
    if prom is None:
        return _sin_datos(_L_MANDADOS)
    n = len([d for d in dias if d is not None])
    return _res(round(prom * 24 * 60), nota=f"{n} mandados, 30 días", link=_L_MANDADOS)


@_protegido(_L_MANDADOS)
def _kpi_mandados_cancelados(user) -> dict:
    """De los mandados que terminaron en 30 días, cuántos se cancelaron."""
    from apps.el_pizarron.models import Mandado
    from django.db.models import Count, Q

    desde = _hace(30)
    agg = Mandado.objects.aggregate(
        entregados=Count("pk", filter=Q(estado="entregado", entregado_en__date__gte=desde)),
        cancelados=Count("pk", filter=Q(estado="cancelado", cancelado_en__date__gte=desde)),
    )
    total = agg["entregados"] + agg["cancelados"]
    pct = _pct(agg["cancelados"], total)
    if pct is None:
        return _sin_datos(_L_MANDADOS)
    return _res(pct, nota=f"{agg['cancelados']} de {total}, 30 días", link=_L_MANDADOS)


@_protegido("/campanas/")
def _kpi_campanas_fallos(user) -> dict:
    """Correos de campaña que no llegaron a salir (30 días)."""
    from django.db.models import Count, Q

    from campanas.models import CampanaEnvio

    agg = CampanaEnvio.objects.filter(enviado_en__date__gte=_hace(30)).aggregate(
        total=Count("pk"), fallidos=Count("pk", filter=Q(estado="fallido")),
    )
    pct = _pct(agg["fallidos"], agg["total"])
    if pct is None:
        return _sin_datos("/campanas/")
    return _res(pct, nota=f"{agg['fallidos']} de {agg['total']} correos",
                link="/campanas/")


@_protegido("/catalogo/")
def _kpi_productos_sin_uso(user) -> dict:
    """Productos activos que no aparecen en ningún proyecto, cotización ni
    factura de los últimos 90 días."""
    from apps.cotizaciones.models import CotizacionItem
    from apps.el_catalogo.models import Servicio
    from apps.facturacion.models import FacturaItem
    from apps.los_proyectos.models import ProyectoProducto

    desde = _hace(90)
    activos = Servicio.objects.filter(activo=True)
    n_activos = activos.count()
    n = (
        activos
        .exclude(pk__in=ProyectoProducto.objects.filter(creado_en__date__gte=desde)
                 .values("servicio_id"))
        .exclude(pk__in=CotizacionItem.objects.filter(cotizacion__creado_en__date__gte=desde,
                                                      servicio__isnull=False)
                 .values("servicio_id"))
        .exclude(pk__in=FacturaItem.objects.filter(factura__creado_en__date__gte=desde,
                                                   servicio__isnull=False)
                 .values("servicio_id"))
        .count()
    )
    return _res(n, nota=f"de {n_activos} activos" if n_activos else "", link="/catalogo/")


@_protegido("/checador/")
def _kpi_visitas_con_resumen(user) -> dict:
    """Visitas de 30 días a las que El Chalán ya les hizo su resumen."""
    from apps.checador.models import Visita
    from django.db.models import Count, Q

    agg = Visita.objects.filter(registrado_en__date__gte=_hace(30)).aggregate(
        total=Count("pk"), con=Count("pk", filter=~Q(ia_resumen="")),
    )
    pct = _pct(agg["con"], agg["total"])
    if pct is None:
        return _sin_datos("/checador/")
    return _res(pct, nota=f"{agg['con']} de {agg['total']} visitas", link="/checador/")


@_protegido("/cartera/")
def _kpi_prospectos(user) -> dict:
    from apps.la_cartera.models import Cliente
    from django.db.models import Count, Q

    agg = Cliente.objects.filter(activo=True).aggregate(
        prospectos=Count("pk", filter=Q(estado="prospecto")),
        activos=Count("pk", filter=Q(estado="activo")),
    )
    return _res(agg["prospectos"], nota=f"frente a {agg['activos']} clientes activos",
                link="/cartera/")


# ── Registro ─────────────────────────────────────────────────────────────


def catalogo_desempeno() -> list:
    """Los KPIs de este archivo, ya construidos (`kpis.KPI`)."""
    from .kpis import KPI
    from .permisos_kpi import (
        COTIZA_Y_FACTURA,
        EDITA_CATALOGO,
        ENVIA_CAMPANAS,
        GESTIONA_PROYECTOS,
        SUPERVISA_JORNADAS,
        VE_CARTERA,
        VE_CONTADURIA,
        VE_COTIZACIONES,
        VE_DINERO,
        VE_FACTURACION,
        VE_MANDADOS_EQUIPO,
        VE_PAPELEO_PROYECTOS,
        VE_PROYECTOS,
        VE_RUTAS,
    )

    return [
        # ── Ventas y cobranza ──
        KPI("cotizacion-dias-para-aprobar", "Días en que aprueban una cotización",
            "Promedio de días entre que se manda una cotización y el cliente la aprueba (90 días).",
            "ventas", VE_COTIZACIONES, _kpi_dias_para_aprobar,
            direccion="baja", formato="dias"),
        KPI("cotizacion-dias-para-enviar", "Días en mandar una cotización",
            "Promedio de días entre que se arma una cotización y sale al cliente (90 días).",
            "ventas", VE_COTIZACIONES, _kpi_dias_para_enviar,
            direccion="baja", formato="dias"),
        KPI("cotizaciones-con-factura-pct", "Aprobadas que ya se facturaron",
            "De las cotizaciones aprobadas en 90 días, qué porcentaje ya tiene su factura.",
            "ventas", COTIZA_Y_FACTURA, _kpi_cotizacion_a_factura,
            direccion="sube", formato="pct"),
        KPI("facturas-dias-de-cobro", "Días en cobrar una factura",
            "Promedio de días entre que se emite una factura y se termina de cobrar (90 días).",
            "ventas", VE_FACTURACION, _kpi_dias_de_cobro,
            direccion="baja", formato="dias"),
        KPI("cotizaciones-descuento-promedio", "Descuento promedio",
            "Descuento general promedio de las cotizaciones que se mandaron en 90 días.",
            "ventas", VE_COTIZACIONES, _kpi_descuento_promedio,
            direccion="baja", formato="pct"),
        KPI("cotizaciones-rechazadas-mes", "Cotizaciones rechazadas (mes)",
            "Cuántas cotizaciones dijo el cliente que no este mes.",
            "ventas", VE_COTIZACIONES, _kpi_rechazadas_mes,
            direccion="baja", acumula="mes"),
        KPI("cotizaciones-por-vencer-7d", "Cotizaciones por vencer",
            "Enviadas que dejan de valer en los próximos 7 días: último aviso para darles seguimiento.",
            "ventas", VE_COTIZACIONES, _kpi_por_vencer_7d,
            direccion="neutro"),
        KPI("vendido-mes", "Vendido este mes",
            "Lo aprobado por los clientes este mes, en pesos. Se reparte por quien hizo la cotización.",
            "ventas", VE_COTIZACIONES, _kpi_vendido_mes,
            direccion="sube", acumula="mes", formato="dinero",
            desglose=_desglose_vendido_mes, desgloses=("persona",)),
        KPI("cotizacion-ticket-promedio", "Venta promedio",
            "Cuánto vale en promedio una cotización aprobada (90 días).",
            "ventas", VE_COTIZACIONES, _kpi_ticket_cotizacion,
            direccion="sube", formato="dinero"),
        KPI("facturado-cobrado-pct", "Cobrado de lo facturado",
            "De lo facturado en los últimos 90 días, qué porcentaje ya entró a la cuenta.",
            "ventas", VE_FACTURACION, _kpi_cobrado_de_facturado,
            direccion="sube", formato="pct"),
        KPI("facturado-por-cliente-mes", "Facturado por cliente (mes)",
            "Lo facturado este mes, repartido por cliente.",
            "ventas", VE_FACTURACION, _kpi_facturado_por_cliente_mes,
            direccion="sube", acumula="mes", formato="dinero",
            desglose=_desglose_facturado_por_cliente_mes, desgloses=("cliente",)),

        # ── Entregas y equipo ──
        KPI("proyectos-a-tiempo-pct", "Proyectos entregados a tiempo",
            "De lo entregado en 90 días, qué porcentaje llegó en o antes de la fecha prometida.",
            "entregas", VE_PROYECTOS, _kpi_proyectos_a_tiempo,
            direccion="sube", formato="pct", acotado=True),
        KPI("proyectos-duracion-promedio", "Duración promedio de un proyecto",
            "Días de arranque a entrega de los proyectos entregados en 90 días.",
            "entregas", VE_PROYECTOS, _kpi_duracion_proyecto,
            direccion="baja", formato="dias", acotado=True),
        KPI("tareas-a-tiempo-pct", "Tareas cerradas a tiempo",
            "De las tareas cerradas en 30 días, qué porcentaje se cerró en o antes de su fecha.",
            "entregas", GESTIONA_PROYECTOS, _kpi_tareas_a_tiempo,
            direccion="sube", formato="pct",
            desglose=_desglose_tareas_a_tiempo, desgloses=("persona",)),
        KPI("tareas-abiertas-por-persona", "Carga de tareas del equipo",
            "Tareas abiertas asignadas a alguien. Repartido, dice quién está saturado.",
            "entregas", GESTIONA_PROYECTOS, _kpi_tareas_abiertas_persona,
            direccion="baja",
            desglose=_desglose_tareas_abiertas, desgloses=("persona",)),
        KPI("horas-extra-mes", "Horas extra del mes",
            "Horas trabajadas arriba del horario de cada quien este mes.",
            "gente", SUPERVISA_JORNADAS, _kpi_horas_extra_mes,
            direccion="baja", acumula="mes", formato="horas",
            desglose=_desglose_horas_extra, desgloses=("persona",)),
        KPI("checador-correcciones-pendientes", "Correcciones del checador por resolver",
            "Ajustes de horario que el equipo pidió y nadie ha aprobado o rechazado.",
            "gente", SUPERVISA_JORNADAS, _kpi_correcciones_pendientes,
            direccion="baja"),
        KPI("checadas-sin-ubicacion-pct", "Checadas sin ubicación",
            "Entradas y salidas de 30 días que se registraron sin GPS.",
            "gente", SUPERVISA_JORNADAS, _kpi_checadas_sin_ubicacion,
            direccion="baja", formato="pct"),
        KPI("checadas-fuera-de-linea-pct", "Checadas sin internet",
            "Entradas y salidas de 30 días que se guardaron sin conexión y llegaron después.",
            "gente", SUPERVISA_JORNADAS, _kpi_checadas_fuera_de_linea,
            direccion="baja", formato="pct"),
        KPI("horas-equipo-mes", "Horas trabajadas del equipo (mes)",
            "Suma de las jornadas del mes, repartida por persona.",
            "gente", SUPERVISA_JORNADAS, _kpi_horas_equipo_mes,
            direccion="sube", acumula="mes", formato="horas",
            desglose=_desglose_horas_equipo_mes, desgloses=("persona",)),

        # ── Rentabilidad ──
        KPI("cobrado-por-cliente-12m", "Cobrado a clientes (12 meses)",
            "Lo que entró de clientes en un año, repartido por cliente.",
            "rentabilidad", VE_DINERO, _kpi_cobrado_por_cliente,
            direccion="sube", formato="dinero",
            desglose=_desglose_cobrado_por_cliente, desgloses=("cliente",)),
        KPI("margen-por-cliente", "Margen por cliente",
            "Lo vendido contra lo que costó en materiales, de los proyectos del último año. "
            "Repartido por cliente dice cuál deja menos.",
            "rentabilidad", VE_DINERO, _kpi_margen_por_cliente,
            direccion="sube", formato="pct",
            desglose=_desglose_margen_por_cliente, desgloses=("cliente",)),
        KPI("gasto-ligado-a-proyecto-pct", "Gasto que se sabe a qué proyecto fue",
            "Qué parte del gasto del mes está ligada a un proyecto: sin eso no se puede costear.",
            "rentabilidad", VE_DINERO, _kpi_gasto_ligado_a_proyecto,
            direccion="sube", formato="pct"),
        KPI("gasto-por-cliente-mes", "Gasto de proyectos por cliente (mes)",
            "Lo gastado este mes en proyectos, repartido por el cliente de cada proyecto.",
            "rentabilidad", VE_DINERO, _kpi_gasto_por_cliente_mes,
            direccion="baja", acumula="mes", formato="dinero",
            desglose=_desglose_gasto_por_cliente_mes, desgloses=("cliente",)),
        KPI("horas-por-cliente-mes", "Horas del equipo por cliente (mes)",
            "Horas de este mes que se pueden atribuir a proyectos, repartidas por cliente.",
            "rentabilidad", SUPERVISA_JORNADAS, _kpi_horas_por_cliente_mes,
            direccion="neutro", acumula="mes", formato="horas",
            desglose=_desglose_horas_por_cliente, desgloses=("cliente",)),
        KPI("concentracion-proveedor", "Dependencia del mayor proveedor",
            "Qué porcentaje de lo comprado en un año se le compró a un solo proveedor.",
            "rentabilidad", VE_DINERO, _kpi_concentracion_proveedor,
            direccion="baja", formato="pct"),

        # ── Control y papeleo ──
        KPI("cfdi-recibidos-pendientes", "Facturas de proveedores por asignar",
            "CFDI que llegaron por correo y no se han ligado a un gasto ni descartado.",
            "control", VE_DINERO, _kpi_cfdi_entrantes_pendientes,
            direccion="baja"),
        KPI("lineas-bancarias-sin-conciliar", "Movimientos del banco sin cuadrar",
            "Renglones del estado de cuenta que aún no se ligan a un asiento.",
            "control", VE_CONTADURIA, _kpi_lineas_sin_conciliar,
            direccion="baja"),
        KPI("egresos-sin-comprobante-mes", "Gastos sin comprobante (mes)",
            "Gastos del mes sin ticket ni factura adjunta.",
            "control", VE_DINERO, _kpi_egresos_sin_comprobante_mes,
            direccion="baja", acumula="mes"),
        KPI("meses-sin-cerrar", "Meses sin cerrar",
            "Meses del último año con movimientos contables que no tienen su cierre.",
            "control", VE_CONTADURIA, _kpi_meses_sin_cerrar,
            direccion="baja"),
        KPI("reembolsos-dias-promedio", "Días en reembolsar a un empleado",
            "Promedio de días entre que alguien paga de su bolsa y se le devuelve (90 días).",
            "control", VE_DINERO, _kpi_dias_para_reembolsar,
            direccion="baja", formato="dias"),
        KPI("facturas-canceladas-mes", "Facturas canceladas (mes)",
            "Facturas que se cancelaron este mes.",
            "control", VE_FACTURACION, _kpi_facturas_canceladas_mes,
            direccion="baja", acumula="mes"),
        KPI("clientes-sin-rfc", "Clientes sin RFC",
            "Clientes activos sin RFC capturado: no se les puede facturar.",
            "control", VE_CARTERA, _kpi_clientes_sin_rfc,
            direccion="baja"),
        KPI("proyectos-sin-documentos", "Proyectos sin documentos",
            "Proyectos en diseño o producción sin ningún documento del archivo ligado.",
            "control", VE_PAPELEO_PROYECTOS, _kpi_proyectos_sin_documentos,
            direccion="baja"),
        KPI("gastos-por-ocr-pct", "Gastos leídos de la foto",
            "De los gastos capturados en 30 días, cuántos se llenaron solos con la foto del ticket.",
            "control", VE_DINERO, _kpi_gastos_por_ocr,
            direccion="sube", formato="pct"),
        KPI("ocr-corregidos-pct", "Lecturas de tickets corregidas",
            "De los tickets que leyó la IA en 30 días, cuántos hubo que corregir a mano.",
            "control", VE_DINERO, _kpi_ocr_corregidos,
            direccion="baja", formato="pct"),

        # ── Lo que faltaba ──
        KPI("rutas-km-mes", "Kilómetros de las rutas (mes)",
            "Distancia planeada de las rutas de reparto que salieron este mes.",
            "rutas", VE_RUTAS, _kpi_rutas_km_mes,
            direccion="neutro", acumula="mes", formato="km"),
        KPI("paradas-puntuales-pct", "Citas de reparto cumplidas",
            f"Paradas con hora de cita entregadas a tiempo (con {TOLERANCIA_PARADA_MIN} minutos "
            "de tolerancia), últimos 30 días.",
            "rutas", VE_RUTAS, _kpi_paradas_puntuales,
            direccion="sube", formato="pct"),
        KPI("rutas-sin-cerrar", "Rutas sin cerrar",
            "Rutas de días pasados que salieron y nadie cerró.",
            "rutas", VE_RUTAS, _kpi_rutas_sin_cerrar,
            direccion="baja"),
        KPI("mandado-minutos-para-asignar", "Minutos en tomar un mandado",
            "Cuánto tarda en promedio un mandado en tener repartidor (30 días).",
            "runner", VE_MANDADOS_EQUIPO, _kpi_minutos_para_asignar,
            direccion="baja", formato="minutos"),
        KPI("mandados-cancelados-pct", "Mandados cancelados",
            "De los mandados que terminaron en 30 días, qué porcentaje se canceló.",
            "runner", VE_MANDADOS_EQUIPO, _kpi_mandados_cancelados,
            direccion="baja", formato="pct"),
        KPI("campanas-fallos-pct", "Correos de campaña que fallaron",
            "De los correos de campaña de 30 días, cuántos no se pudieron mandar.",
            "cartera", ENVIA_CAMPANAS, _kpi_campanas_fallos,
            direccion="baja", formato="pct"),
        KPI("productos-sin-uso-90d", "Productos sin movimiento",
            "Productos activos que no aparecen en proyectos, cotizaciones ni facturas en 90 días.",
            "catalogo", EDITA_CATALOGO, _kpi_productos_sin_uso,
            direccion="baja"),
        KPI("visitas-con-resumen-pct", "Visitas con resumen de El Chalán",
            "De las visitas de 30 días, cuántas ya tienen su resumen hecho por la IA.",
            "gente", SUPERVISA_JORNADAS, _kpi_visitas_con_resumen,
            direccion="sube", formato="pct"),
        KPI("prospectos-cartera", "Prospectos en la cartera",
            "Clientes posibles que todavía no compran, frente a los clientes activos.",
            "cartera", VE_CARTERA, _kpi_prospectos,
            direccion="sube"),
    ]
