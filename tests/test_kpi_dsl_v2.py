"""DSL de KPIs v2 — cada capacidad nueva con datos reales y el número exacto.

«Hoy» se congela en el martes 2026-09-29 para que las ventanas (semana, mes,
trimestre…) no dependan del día en que corre la suite.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db

HOY = date(2026, 9, 29)  # martes


def _dt(d: date, h: int = 12, m: int = 0) -> datetime:
    return timezone.make_aware(datetime.combine(d, time(h, m)))


@pytest.fixture
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: HOY)
    return HOY


@pytest.fixture
def cc(db):
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.create(slug="op", nombre="Operación")


def _egreso(cc, monto, fecha, **kw):
    from apps.tesoreria.models import Egreso
    return Egreso.objects.create(monto=Decimal(str(monto)), fecha=fecha, descripcion=kw.pop("descripcion", "x"),
                                 centro_de_costo=cc, **kw)


# ── Ventanas: rango y periodo anterior (puro) ───────────────────────────────


@pytest.mark.parametrize(("ventana", "rango", "anterior"), [
    ("esta_semana", (date(2026, 9, 28), HOY), (date(2026, 9, 21), date(2026, 9, 22))),
    ("este_mes", (date(2026, 9, 1), HOY), (date(2026, 8, 1), date(2026, 8, 29))),
    ("mes_pasado", (date(2026, 8, 1), date(2026, 8, 31)), (date(2026, 7, 1), date(2026, 7, 31))),
    ("este_trimestre", (date(2026, 7, 1), HOY), (date(2026, 4, 1), date(2026, 6, 30))),
    ("este_ano", (date(2026, 1, 1), HOY), (date(2025, 1, 1), date(2025, 9, 29))),
    ("ultimos_7d", (date(2026, 9, 22), HOY), (date(2026, 9, 14), date(2026, 9, 21))),
    ("ultimos_30d", (date(2026, 8, 30), HOY), (date(2026, 7, 30), date(2026, 8, 29))),
    ("ultimos_90d", (date(2026, 7, 1), HOY), (date(2026, 4, 1), date(2026, 6, 30))),
    ("ultimos_12m", (date(2025, 9, 29), HOY), (date(2024, 9, 29), date(2025, 9, 28))),
])
def test_ventana_y_su_periodo_anterior(ventana, rango, anterior):
    from lib.kpi_dsl.ejecutor import _ventana_a_rango, ventana_anterior
    assert _ventana_a_rango(ventana, HOY) == rango
    assert ventana_anterior(ventana, HOY) == anterior


def test_periodo_anterior_recorta_fin_de_mes():
    from lib.kpi_dsl.ejecutor import ventana_anterior
    # El 31 de marzo se compara contra el 1–28 de febrero (no hay 31 de febrero).
    assert ventana_anterior("este_mes", date(2026, 3, 31)) == (date(2026, 2, 1), date(2026, 2, 28))
    assert ventana_anterior("este_ano", date(2028, 2, 29)) == (date(2027, 1, 1), date(2027, 2, 28))
    assert ventana_anterior("siempre", HOY) is None


# ── Ventanas + comparar, con datos ──────────────────────────────────────────


@pytest.fixture
def egresos_fechados(hoy_fijo, cc):
    for monto, fecha in [
        (100, date(2026, 9, 29)), (10, date(2026, 9, 28)), (1000, date(2026, 9, 20)),
        (5000, date(2026, 8, 15)), (7, date(2026, 8, 31)), (20000, date(2026, 7, 1)),
        (300000, date(2026, 6, 30)), (4, date(2025, 10, 1)), (60000, date(2025, 9, 28)),
    ]:
        _egreso(cc, monto, fecha)


@pytest.mark.parametrize(("ventana", "suma"), [
    ("esta_semana", 110.0),
    ("este_mes", 1110.0),
    ("mes_pasado", 5007.0),
    ("este_trimestre", 26117.0),
    ("ultimos_90d", 26117.0),
    ("ultimos_12m", 326121.0),
])
def test_ventanas_nuevas_suman_lo_exacto(egresos_fechados, ventana, suma):
    from lib.kpi_dsl import ejecutar
    res = ejecutar({"entidad": "egreso", "agregacion": "sum", "campo": "monto", "ventana_tiempo": ventana})
    assert res["valor"] == suma
    assert res["numero"] == suma
    assert res["formato"] == "dinero"


def test_comparar_con_el_mismo_tramo_del_mes_pasado(egresos_fechados):
    from lib.kpi_dsl import ejecutar
    res = ejecutar({"entidad": "egreso", "agregacion": "sum", "campo": "monto",
                    "ventana_tiempo": "este_mes", "comparar": True})
    assert res["valor"] == 1110.0
    # 1–29 de agosto: 5000 (el 7 del 31 de agosto queda fuera).
    assert res["comparacion"] == {"anterior": 5000.0, "cambio_pct": -77.8,
                                  "desde": "2026-08-01", "hasta": "2026-08-29"}


def test_comparar_sin_base_no_inventa_cero(hoy_fijo, cc):
    from lib.kpi_dsl import ejecutar
    _egreso(cc, 50, HOY)
    res = ejecutar({"entidad": "egreso", "agregacion": "sum", "campo": "monto",
                    "ventana_tiempo": "esta_semana", "comparar": True})
    assert res["valor"] == 50.0
    assert res["comparacion"]["anterior"] == 0.0
    assert res["comparacion"]["cambio_pct"] is None


def test_comparar_pide_ventana():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="ventana"):
        validar({"entidad": "egreso", "comparar": True})


def test_campo_fecha_alterno_cambia_la_ventana(hoy_fijo, cc):
    from lib.kpi_dsl import ejecutar
    # Gastado el mes pasado pero pagado este mes.
    _egreso(cc, 80, date(2026, 8, 10), pagado_en=date(2026, 9, 5))
    _egreso(cc, 20, date(2026, 9, 10))
    base = {"entidad": "egreso", "agregacion": "sum", "campo": "monto", "ventana_tiempo": "este_mes"}
    assert ejecutar(base)["valor"] == 20.0
    assert ejecutar({**base, "campo_fecha": "pagado_en"})["valor"] == 80.0


# ── Filtros nuevos ──────────────────────────────────────────────────────────


@pytest.fixture
def tareas(hoy_fijo, proyecto_factory, usuario_factory):
    """5 tareas de Ana y Beto: 3 cerradas a tiempo, 1 tarde, 1 abierta vencida,
    1 abierta que vence en 5 días y 1 sin fecha."""
    from apps.el_pizarron.models import Tarea

    ana = usuario_factory(rol="dueno", email="ana@lc.mx")
    beto = usuario_factory(rol="disenador", email="beto@lc.mx")
    p = proyecto_factory()
    filas = [
        # (asignada, compromiso, completada)
        (ana, date(2026, 9, 10), _dt(date(2026, 9, 9))),   # a tiempo, −1 día
        (ana, date(2026, 9, 10), _dt(date(2026, 9, 10), 18)),  # a tiempo, el mismo día
        (beto, date(2026, 9, 15), _dt(date(2026, 9, 12))),  # a tiempo, −3 días
        (beto, date(2026, 9, 15), _dt(date(2026, 9, 21))),  # tarde, +6 días
        (beto, date(2026, 9, 20), None),                    # abierta y vencida
        (ana, date(2026, 10, 4), None),                     # vence en 5 días
        (ana, None, None),                                  # sin fecha
    ]
    for i, (quien, compromiso, completada) in enumerate(filas):
        Tarea.objects.create(proyecto=p, titulo=f"t{i}", asignada_a=quien, creado_por=ana,
                             fecha_compromiso=compromiso, completada_en=completada)
    return {"ana": ana, "beto": beto}


def _cuenta(definicion, usuario=None):
    from lib.kpi_dsl import ejecutar
    return ejecutar({"entidad": "tarea", **definicion}, usuario=usuario)["valor"]


def test_filtro_vacio(tareas):
    assert _cuenta({"filtros": [{"campo": "fecha_compromiso", "op": "vacio", "valor": True}]}) == 1
    assert _cuenta({"filtros": [{"campo": "completada_en", "op": "vacio", "valor": False}]}) == 4
    # Sin `valor`, «vacío» es verdadero.
    assert _cuenta({"filtros": [{"campo": "completada_en", "op": "vacio"}]}) == 3


def test_filtro_vacio_en_texto_cuenta_la_cadena_vacia(cc):
    from lib.kpi_dsl import ejecutar
    _egreso(cc, 1, HOY, proveedor_nombre="")
    _egreso(cc, 1, HOY, proveedor_nombre="Uber")
    d = {"entidad": "egreso", "filtros": [{"campo": "proveedor_nombre", "op": "vacio", "valor": True}]}
    assert ejecutar(d)["valor"] == 1
    d["filtros"][0]["valor"] = False
    assert ejecutar(d)["valor"] == 1


def test_filtro_hoy_y_relativos(tareas):
    abiertas = {"campo": "completada_en", "op": "vacio", "valor": True}
    vencidas = [abiertas, {"campo": "fecha_compromiso", "op": "lt", "valor": "hoy"}]
    assert _cuenta({"filtros": vencidas}) == 1
    proximas = [abiertas, {"campo": "fecha_compromiso", "op": "gte", "valor": "hoy"},
                {"campo": "fecha_compromiso", "op": "lte", "valor": "en_7_dias"}]
    assert _cuenta({"filtros": proximas}) == 1
    # Sobre un DateTimeField: completadas desde hace 10 días (19-sep en adelante).
    assert _cuenta({"filtros": [{"campo": "completada_en", "op": "gte", "valor": "hace_10_dias"}]}) == 1
    # Fecha ISO.
    assert _cuenta({"filtros": [{"campo": "fecha_compromiso", "op": "eq", "valor": "2026-09-15"}]}) == 2


def test_filtro_in_con_lista_de_relaciones(tareas):
    t = tareas
    assert _cuenta({"filtros": [{"campo": "asignada_a", "op": "in", "valor": [t["beto"].pk]}]}) == 3
    assert _cuenta({"filtros": [{"campo": "asignada_a", "op": "in",
                                 "valor": [t["beto"].pk, str(t["ana"].pk)]}]}) == 7


def test_filtro_contra_otro_campo_fecha_contra_momento(tareas):
    a_tiempo = {"campo": "completada_en", "op": "lte", "campo_ref": "fecha_compromiso"}
    assert _cuenta({"filtros": [a_tiempo]}) == 3


def test_filtro_numerico_con_mayor_que(cc):
    from lib.kpi_dsl import ejecutar
    for m in (50, 150, 999):
        _egreso(cc, m, HOY)
    d = {"entidad": "egreso", "agregacion": "sum", "campo": "monto",
         "filtros": [{"campo": "monto", "op": "gt", "valor": "100"}]}
    assert ejecutar(d)["valor"] == 1149.0


# ── Porcentajes ─────────────────────────────────────────────────────────────


PCT_A_TIEMPO = {
    "entidad": "tarea", "tipo": "porcentaje",
    "filtros": [{"campo": "completada_en", "op": "vacio", "valor": False}],
    "filtros_numerador": [{"campo": "completada_en", "op": "lte", "campo_ref": "fecha_compromiso"}],
}


def test_porcentaje_de_tareas_cerradas_a_tiempo(tareas):
    from lib.kpi_dsl import ejecutar
    res = ejecutar(PCT_A_TIEMPO)
    assert res["valor"] == 75.0
    assert res["formato"] == "pct"


def test_porcentaje_sin_base_es_raya(tareas):
    from lib.kpi_dsl import ejecutar
    d = {**PCT_A_TIEMPO, "filtros": [{"campo": "titulo", "op": "eq", "valor": "no existe"}]}
    res = ejecutar(d)
    assert res["valor"] == "—"
    assert res["numero"] is None


def test_porcentaje_por_persona(tareas):
    from lib.kpi_dsl import ejecutar
    res = ejecutar({**PCT_A_TIEMPO, "agrupar_por": "persona"})
    assert res["valor"] == 75.0
    assert [(g["etiqueta"], g["valor"]) for g in res["grupos"]] == [
        (tareas["ana"].nombre_completo, 100.0), (tareas["beto"].nombre_completo, 50.0),
    ]
    assert res["grupos"][0]["pk"] == tareas["ana"].pk


def test_porcentaje_de_dinero(cc):
    from lib.kpi_dsl import ejecutar
    _egreso(cc, 300, HOY, estado_pago="pagado")
    _egreso(cc, 100, HOY, estado_pago="pendiente")
    res = ejecutar({"entidad": "egreso", "agregacion": "sum", "campo": "monto", "tipo": "porcentaje",
                    "filtros_numerador": [{"campo": "estado_pago", "op": "eq", "valor": "pendiente"}]})
    assert res["valor"] == 25.0


def test_porcentaje_pide_numerador():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="filtros_numerador"):
        validar({"entidad": "tarea", "tipo": "porcentaje"})
    with pytest.raises(ValidacionError, match="porcentaje"):
        validar({"entidad": "tarea",
                 "filtros_numerador": [{"campo": "archivada", "op": "eq", "valor": True}]})


# ── Agrupar ─────────────────────────────────────────────────────────────────


def test_agrupar_ingresos_por_cliente_top(cliente_factory):
    from apps.tesoreria.models import Ingreso

    from lib.kpi_dsl import ejecutar
    a = cliente_factory(razon_social="Heladería")
    b = cliente_factory(razon_social="Cafetería")
    for monto, cli in [(300, a), (200, a), (700, b), (50, None)]:
        Ingreso.objects.create(monto=Decimal(monto), fecha=HOY, descripcion="p", cliente=cli)
    d = {"entidad": "ingreso", "agregacion": "sum", "campo": "monto", "agrupar_por": "cliente"}
    res = ejecutar(d)
    assert res["valor"] == 1250.0
    assert res["grupos"] == [
        {"pk": b.pk, "etiqueta": "Cafetería", "valor": 700.0},
        {"pk": a.pk, "etiqueta": "Heladería", "valor": 500.0},
        {"pk": None, "etiqueta": "Sin cliente", "valor": 50.0},
    ]
    assert len(ejecutar({**d, "top": 2})["grupos"]) == 2


def test_agrupar_por_opcion_y_por_catalogo(cc, cliente_factory):
    from apps.los_proyectos.models import EstadoProyecto, Proyecto

    from lib.kpi_dsl import ejecutar
    _egreso(cc, 10, HOY, estado_pago="pagado")
    _egreso(cc, 10, HOY, estado_pago="pagado")
    _egreso(cc, 10, HOY, estado_pago="pendiente")
    res = ejecutar({"entidad": "egreso", "agrupar_por": "estado_pago"})
    assert [(g["pk"], g["etiqueta"], g["valor"]) for g in res["grupos"]] == [
        ("pagado", "Pagado (saldado)", 2), ("pendiente", "Pendiente de pago", 1),
    ]

    cli = cliente_factory()
    for estado in ("en_proceso_diseno", "en_proceso_diseno", "en_proceso_produccion"):
        Proyecto.objects.create(cliente=cli, nombre="x", estado=estado)
    res = ejecutar({"entidad": "proyecto", "agrupar_por": "estado"})
    esperado = EstadoProyecto.objects.get(slug="en_proceso_diseno").label
    assert res["grupos"][0] == {"pk": "en_proceso_diseno", "etiqueta": esperado, "valor": 2}


def test_agrupar_proyectos_por_persona_via_asignaciones(proyecto_factory, usuario_factory):
    from apps.los_proyectos.models import ProyectoAsignacion

    from lib.kpi_dsl import ejecutar
    ana = usuario_factory(rol="dueno")
    beto = usuario_factory(rol="disenador")
    p1, p2 = proyecto_factory(nombre="1", monto_cotizado=Decimal("100")), proyecto_factory(
        nombre="2", monto_cotizado=Decimal("40"))
    for p, u in [(p1, ana), (p1, beto), (p2, beto)]:
        ProyectoAsignacion.objects.create(proyecto=p, usuario=u)
    res = ejecutar({"entidad": "proyecto", "agregacion": "sum", "campo": "monto_cotizado",
                    "agrupar_por": "persona"})
    assert res["valor"] == 140.0
    assert [(g["pk"], g["valor"]) for g in res["grupos"]] == [(beto.pk, 140.0), (ana.pk, 100.0)]


def test_agrupar_fuera_de_whitelist_rechaza():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="agrupar"):
        validar({"entidad": "ingreso", "agrupar_por": "cliente__rfc"})
    with pytest.raises(ValidacionError, match="top"):
        validar({"entidad": "ingreso", "agrupar_por": "cliente", "top": 500})


# ── Duraciones ──────────────────────────────────────────────────────────────


@pytest.fixture
def cotizaciones(cliente_factory):
    from apps.cotizaciones.models import Cotizacion
    cli = cliente_factory()
    base = _dt(date(2026, 9, 1), 10)
    for aprobada in (timedelta(days=2), timedelta(days=4), timedelta(hours=36), None):
        Cotizacion.objects.create(
            cliente=cli, titulo="c", enviada_en=base,
            aprobada_en=(base + aprobada) if aprobada else None,
            estado="aprobada" if aprobada else "enviada",
        )
    return cli


@pytest.mark.parametrize(("agg", "esperado"), [("avg", 2.5), ("max", 4.0), ("min", 1.5), ("sum", 7.5)])
def test_duracion_dias_para_aprobar(cotizaciones, agg, esperado):
    from lib.kpi_dsl import ejecutar
    res = ejecutar({"entidad": "cotizacion", "agregacion": agg, "duracion": "dias_para_aprobar"})
    assert res["valor"] == esperado
    assert res["formato"] == "dias"


def test_duracion_agrupada_y_sin_datos(cotizaciones):
    from lib.kpi_dsl import ejecutar
    res = ejecutar({"entidad": "cotizacion", "agregacion": "avg", "duracion": "dias_para_aprobar",
                    "agrupar_por": "cliente"})
    assert res["grupos"] == [{"pk": cotizaciones.pk, "etiqueta": cotizaciones.razon_social, "valor": 2.5}]
    vacia = ejecutar({"entidad": "cotizacion", "agregacion": "avg", "duracion": "dias_para_pagar"})
    assert vacia["valor"] == "—"
    assert vacia["numero"] is None


def test_duracion_fecha_contra_momento_cuenta_dias(tareas):
    from lib.kpi_dsl import ejecutar
    # −1, 0, −3, +6 → promedio 0.5; máximo 6.
    d = {"entidad": "tarea", "duracion": "dias_de_retraso"}
    assert ejecutar({**d, "agregacion": "avg"})["valor"] == 0.5
    assert ejecutar({**d, "agregacion": "max"})["valor"] == 6.0


def test_duracion_en_horas_de_jornada(usuario_factory):
    from apps.checador.models import Jornada

    from lib.kpi_dsl import ejecutar
    u = usuario_factory(rol="dueno")
    Jornada.objects.create(usuario=u, fecha=HOY, entrada_en=_dt(HOY, 9), salida_en=_dt(HOY, 17, 30))
    Jornada.objects.create(usuario=u, fecha=HOY - timedelta(days=1),
                           entrada_en=_dt(HOY - timedelta(days=1), 10), salida_en=_dt(HOY - timedelta(days=1), 16))
    Jornada.objects.create(usuario=u, fecha=HOY - timedelta(days=2), entrada_en=_dt(HOY, 9))  # abierta
    res = ejecutar({"entidad": "jornada", "agregacion": "avg", "duracion": "horas_trabajadas",
                    "alcance_usuario": "mio"}, usuario=u)
    assert res["valor"] == 7.25
    assert res["formato"] == "horas"


def test_duracion_valida():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="Duración"):
        validar({"entidad": "cotizacion", "agregacion": "avg", "duracion": "dias_de_mentira"})
    with pytest.raises(ValidacionError, match="duración"):
        validar({"entidad": "cotizacion", "duracion": "dias_para_aprobar"})  # count
    with pytest.raises(ValidacionError, match="no los dos"):
        validar({"entidad": "cotizacion", "agregacion": "avg", "duracion": "dias_para_aprobar",
                 "campo": "version"})


# ── Entidades nuevas ────────────────────────────────────────────────────────


def test_entidades_nuevas_cuentan_y_suman(usuario_factory, cliente_factory, proyecto_factory, cc):
    from apps.checador.models import SesionProyecto, Visita
    from apps.contaduria.models import ConciliacionBancaria, CuentaContable, LineaBancaria
    from apps.el_pizarron.models import Mandado, Tarea
    from apps.facturacion.models import CfdiEntrante, Factura

    from lib.kpi_dsl import ejecutar
    u = usuario_factory(rol="dueno")
    otro = usuario_factory(rol="dueno")
    cli = cliente_factory()
    p = proyecto_factory(cliente=cli)

    Factura.objects.create(cliente=cli, titulo="f1", estado="emitida", monto_cobrado=Decimal("10"))
    Factura.objects.create(cliente=cli, titulo="f2", estado="cobrada_total", monto_cobrado=Decimal("990"))
    assert ejecutar({"entidad": "factura", "filtros": [
        {"campo": "estado", "op": "eq", "valor": "emitida"}]})["valor"] == 1
    assert ejecutar({"entidad": "factura", "agregacion": "sum", "campo": "monto_cobrado"})["valor"] == 1000.0

    CfdiEntrante.objects.create(uuid="A-1", total=Decimal("116"), estado="pendiente")
    CfdiEntrante.objects.create(uuid="A-2", total=Decimal("232"), estado="ligado")
    assert ejecutar({"entidad": "cfdi_entrante", "agregacion": "sum", "campo": "total",
                     "filtros": [{"campo": "egreso", "op": "vacio", "valor": True}]})["valor"] == 348.0

    cuenta = CuentaContable.objects.first() or CuentaContable.objects.create(
        codigo="102-01", nombre="Banco", tipo="activo", naturaleza="deudora")
    conc = ConciliacionBancaria.objects.create(cuenta=cuenta, desde=HOY, hasta=HOY,
                                               saldo_estado_cuenta=Decimal("0"))
    LineaBancaria.objects.create(conciliacion=conc, fecha=HOY, descripcion="a", monto=Decimal("5"))
    LineaBancaria.objects.create(conciliacion=conc, fecha=HOY, descripcion="b", monto=Decimal("7"),
                                 conciliada=True)
    assert ejecutar({"entidad": "linea_bancaria", "filtros": [
        {"campo": "conciliada", "op": "eq", "valor": False}]})["valor"] == 1

    SesionProyecto.objects.create(usuario=u, proyecto=p, inicio=_dt(HOY, 9), fin=_dt(HOY, 10),
                                  duracion_min=60, estado="cerrada")
    SesionProyecto.objects.create(usuario=otro, proyecto=p, inicio=_dt(HOY, 9), duracion_min=30)
    assert ejecutar({"entidad": "sesion_proyecto", "agregacion": "sum", "campo": "duracion_min"})["valor"] == 90.0
    assert ejecutar({"entidad": "sesion_proyecto", "agregacion": "sum", "duracion": "horas"})["valor"] == 1.0

    Visita.objects.create(usuario=u, registrado_en=_dt(HOY), tipo="cliente", cliente=cli)
    Visita.objects.create(usuario=otro, registrado_en=_dt(HOY), tipo="proveedor")
    assert ejecutar({"entidad": "visita", "alcance_usuario": "mio"}, usuario=u)["valor"] == 1

    t1 = Tarea.objects.create(proyecto=p, titulo="m1", tipo="entrega", runner=u)
    t2 = Tarea.objects.create(proyecto=p, titulo="m2", tipo="entrega", runner=otro)
    # Una tarea de entrega nace con su mandado (signal): se completa ése.
    for t, llegada in [(t1, _dt(HOY, 10, 40)), (t2, _dt(HOY, 11))]:
        Mandado.objects.update_or_create(tarea=t, defaults={
            "estado": "entregado", "en_camino_en": _dt(HOY, 10), "entregado_en": llegada})
    res = ejecutar({"entidad": "mandado", "agregacion": "avg", "duracion": "minutos_en_camino"})
    assert res["valor"] == 50.0
    assert res["formato"] == "minutos"
    assert ejecutar({"entidad": "mandado", "alcance_usuario": "mio"}, usuario=u)["valor"] == 1
    assert ejecutar({"entidad": "mandado", "filtros": [
        {"campo": "runner", "op": "eq", "valor": otro.pk}]})["valor"] == 1


# ── Metadatos ───────────────────────────────────────────────────────────────


def test_metadatos_con_defaults_sensatos():
    from lib.kpi_dsl import metadatos_de, validar

    def meta(d):
        return metadatos_de(validar(d))

    assert meta({"entidad": "tarea"}) == {"formato": "numero", "direccion": "neutro"}
    assert meta({"entidad": "egreso", "agregacion": "sum", "campo": "monto"})["formato"] == "dinero"
    assert meta({"entidad": "jornada", "agregacion": "sum", "campo": "retardo_min"})["formato"] == "minutos"
    assert meta({**PCT_A_TIEMPO})["formato"] == "pct"
    assert meta({"entidad": "mandado", "agregacion": "avg",
                 "duracion": "horas_para_asignar"})["formato"] == "horas"
    assert meta({"entidad": "tarea", "formato": "dias", "direccion": "baja"}) == {
        "formato": "dias", "direccion": "baja"}


def test_metadatos_invalidos_rechazan():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="formato"):
        validar({"entidad": "tarea", "formato": "euros"})
    with pytest.raises(ValidacionError, match="direccion"):
        validar({"entidad": "tarea", "direccion": "arriba"})


def test_la_normalizacion_v2_es_estable():
    from lib.kpi_dsl import validar
    d = {**PCT_A_TIEMPO, "agrupar_por": "persona", "top": 3, "ventana_tiempo": "este_mes",
         "comparar": True, "formato": "pct", "direccion": "sube", "campo_fecha": "completada_en"}
    n = validar(d)
    assert validar(n) == n
    assert json.loads(json.dumps(n)) == n
    # Lo que es default no se guarda.
    assert "top" not in validar({"entidad": "tarea", "agrupar_por": "persona", "top": 10})
    assert "campo_fecha" not in validar({"entidad": "tarea", "campo_fecha": "creado_en"})


# ── Seguridad ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("definicion", [
    {"entidad": "usuario"},
    {"entidad": "tarea", "filtros": [{"campo": "creado_por__password", "op": "eq", "valor": "x"}]},
    {"entidad": "tarea", "filtros": [{"campo": "proyecto__cliente__rfc", "op": "contiene", "valor": "x"}]},
    {"entidad": "tarea", "filtros": [{"campo": "titulo", "op": "regex", "valor": ".*"}]},
    {"entidad": "tarea", "filtros": [{"campo": "archivada", "op": "contiene", "valor": "x"}]},
    {"entidad": "tarea", "filtros": [{"campo": "fecha_compromiso", "op": "lt", "valor": "mañana"}]},
    {"entidad": "tarea", "filtros": [{"campo": "fecha_compromiso", "op": "lt", "valor": "hace_99999_dias"}]},
    {"entidad": "tarea", "filtros": [{"campo": "asignada_a", "op": "eq", "valor": "yo"}]},
    {"entidad": "tarea", "filtros": [{"campo": "titulo", "op": "eq", "valor": {"$ne": 1}}]},
    {"entidad": "tarea", "filtros": [{"campo": "completada_en", "op": "lte", "campo_ref": "asignada_a"}]},
    {"entidad": "tarea", "filtros": [{"campo": "completada_en", "op": "lte", "campo_ref": "creado_por"}]},
    {"entidad": "tarea", "filtros": [{"campo": "completada_en", "op": "vacio", "campo_ref": "creado_en"}]},
    {"entidad": "egreso", "agregacion": "sum", "campo": "proveedor__razon_social"},
    {"entidad": "egreso", "agregacion": "sum", "campo": "descripcion"},
    {"entidad": "egreso", "campo_fecha": "monto", "ventana_tiempo": "este_mes"},
    {"entidad": "egreso", "tipo": "division"},
    {"entidad": "egreso", "comparar": "si", "ventana_tiempo": "este_mes"},
    {"entidad": "cfdi_entrante", "alcance_usuario": "mio"},
])
def test_todo_lo_que_no_esta_en_la_whitelist_se_rechaza(definicion):
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError):
        validar(definicion)


def test_permisos_de():
    from lib.kpi_dsl import permisos_de
    assert permisos_de({"entidad": "egreso"}) == ("tesoreria.ver",)
    assert permisos_de({"entidad": "proyecto"}) == ("proyectos.ver_todos",)
    assert permisos_de({"entidad": "proyecto", "alcance_usuario": "mio"}) == ("proyectos.ver",)
    assert permisos_de({"entidad": "proyecto", "alcance_usuario": "mio", "agregacion": "sum",
                        "campo": "monto_cotizado"}) == ("proyectos.ver", "tesoreria.ver")
    # Un filtro por dinero también enseña dinero.
    assert permisos_de({"entidad": "proyecto", "filtros": [
        {"campo": "monto_estimado", "op": "gt", "valor": 1}]}) == ("proyectos.ver_todos", "tesoreria.ver")
    assert permisos_de({"entidad": "tarea"}) == ("pizarron.ver", "proyectos.ver_todos")
    assert permisos_de({"entidad": "jornada", "alcance_usuario": "mio"}) == ("checador.checar",)


def test_sin_permiso_no_ve_el_dato(cc, usuario_factory, proyecto_factory):
    from lib.kpi_dsl import ejecutar
    disenador = usuario_factory(rol="disenador")
    admin = usuario_factory(rol="super_admin")
    _egreso(cc, 100, HOY, creado_por=disenador)
    proyecto_factory(monto_cotizado=Decimal("500"))

    gasto = {"entidad": "egreso", "agregacion": "sum", "campo": "monto"}
    negado = ejecutar(gasto, usuario=disenador)
    assert negado["valor"] == "—" and negado["numero"] is None
    assert negado["nota"] == "sin permiso"
    assert ejecutar(gasto, usuario=admin)["valor"] == 100.0  # failsafe super_admin

    monto = {"entidad": "proyecto", "agregacion": "sum", "campo": "monto_cotizado",
             "alcance_usuario": "mio"}
    assert ejecutar(monto, usuario=disenador)["nota"] == "sin permiso"
    # «Mis proyectos» sin dinero sí lo ve; todos los proyectos no.
    assert ejecutar({"entidad": "proyecto", "alcance_usuario": "mio"}, usuario=disenador)["valor"] == 0
    assert ejecutar({"entidad": "proyecto"}, usuario=disenador)["nota"] == "sin permiso"
    # Un porcentaje o una agrupación tampoco lo deja pasar.
    assert "grupos" not in ejecutar({**gasto, "agrupar_por": "proveedor"}, usuario=disenador)


def test_alcance_mio_en_entidades_nuevas(usuario_factory, cliente_factory):
    from apps.cotizaciones.models import Cotizacion

    from lib.kpi_dsl import ejecutar
    u1, u2 = usuario_factory(rol="dueno"), usuario_factory(rol="dueno")
    cli = cliente_factory()
    Cotizacion.objects.create(cliente=cli, titulo="a", creado_por=u1)
    Cotizacion.objects.create(cliente=cli, titulo="b", creado_por=u2)
    Cotizacion.objects.create(cliente=cli, titulo="c", creado_por=u2)
    assert ejecutar({"entidad": "cotizacion", "alcance_usuario": "mio"}, usuario=u2)["valor"] == 2
    assert ejecutar({"entidad": "cotizacion"}, usuario=u2)["valor"] == 3


# ── UI: esquema y frase ─────────────────────────────────────────────────────


def test_esquema_para_ui_es_json_y_completo():
    from lib.kpi_dsl import ENTIDADES, esquema_para_ui
    esquema = esquema_para_ui()
    json.dumps(esquema)
    claves = [e["clave"] for e in esquema["entidades"]]
    assert set(claves) == set(ENTIDADES)  # en las pruebas están instaladas todas
    tarea = next(e for e in esquema["entidades"] if e["clave"] == "tarea")
    campos = {c["clave"]: c for c in tarea["campos"]}
    assert campos["prioridad"]["opciones"] == [
        {"valor": "baja", "etiqueta": "Baja"}, {"valor": "media", "etiqueta": "Media"},
        {"valor": "alta", "etiqueta": "Alta"},
    ]
    from apps.el_pizarron.models import EstadoTarea
    assert [o["valor"] for o in campos["estado"]["opciones"]] == list(
        EstadoTarea.objects.order_by("orden", "label").values_list("slug", flat=True))
    assert campos["estado"]["opciones"]  # el catálogo sembrado por migración
    assert campos["fecha_compromiso"]["ops"] == ["eq", "gt", "gte", "lt", "lte", "vacio"]
    assert {d["clave"] for d in tarea["duraciones"]} == {"dias_para_cerrar", "dias_de_retraso"}
    assert "persona" in {g["clave"] for g in tarea["agrupaciones"]}
    assert {v["clave"] for v in esquema["ventanas"]} >= {"esta_semana", "este_trimestre", "ultimos_12m"}


def test_esquema_para_ui_respeta_permisos(usuario_factory):
    from lib.kpi_dsl import esquema_para_ui
    disenador = usuario_factory(rol="disenador")
    esquema = esquema_para_ui(disenador)
    por_clave = {e["clave"]: e for e in esquema["entidades"]}
    assert "egreso" not in por_clave and "factura" not in por_clave
    assert por_clave["proyecto"]["solo_mio"] is True
    assert not {"monto_cotizado", "monto_estimado"} & {c["clave"] for c in por_clave["proyecto"]["campos"]}
    assert por_clave["jornada"]["solo_mio"] is True


@pytest.mark.parametrize(("definicion", "frase"), [
    ({"entidad": "ingreso", "agregacion": "sum", "campo": "monto", "ventana_tiempo": "este_mes",
      "agrupar_por": "cliente"},
     "Suma del monto de los ingresos de este mes, agrupado por cliente."),
    ({"entidad": "tarea", "alcance_usuario": "mio",
      "filtros": [{"campo": "completada_en", "op": "vacio", "valor": True},
                  {"campo": "fecha_compromiso", "op": "lt", "valor": "hoy"}]},
     "Número de tareas sin fecha en que se completó y con fecha de compromiso que es antes de hoy, "
     "sólo lo mío."),
    (PCT_A_TIEMPO,
     "Porcentaje de tareas cuya fecha en que se completó es hasta la fecha de compromiso, sobre "
     "todas las tareas con fecha en que se completó."),
    ({"entidad": "cotizacion", "agregacion": "avg", "duracion": "dias_para_aprobar",
      "ventana_tiempo": "este_trimestre", "comparar": True},
     "Promedio de días para que la aprueben de las cotizaciones de este trimestre, comparado con "
     "el periodo anterior."),
    ({"entidad": "tarea", "filtros": [{"campo": "archivada", "op": "eq", "valor": False}]},
     "Número de tareas no marcadas como «archivada»."),
    ({"entidad": "egreso", "filtros": [{"campo": "estado_pago", "op": "in", "valor": ["pendiente", "por_reembolsar"]}]},
     "Número de egresos con estado de pago que es alguno de «pendiente», «por_reembolsar»."),
])
def test_describir(definicion, frase):
    from lib.kpi_dsl import describir
    assert describir(definicion) == frase


def test_el_prompt_del_chalan_sale_del_esquema():
    from apps.taller_home.services_kpi_chalan import _system_prompt

    from lib.kpi_dsl import ENTIDADES
    prompt = _system_prompt()
    for entidad, cfg in ENTIDADES.items():
        assert f"- {entidad} (" in prompt
        for d in cfg["duraciones"]:
            assert d in prompt
    for clave in ("filtros_numerador", "agrupar_por", "duracion", "comparar", "campo_ref", "hace_N_dias"):
        assert clave in prompt


def test_app_sin_el_modelo_no_lo_ofrece_ni_truena(monkeypatch):
    """La Gerencia no instala `recados`: el constructor no ofrece la entidad y
    un KPI viejo de recados sale «—» con nota de error, no un 500."""
    from lib.kpi_dsl import ejecutar, esquema_para_ui, resumen_para_prompt
    from lib.kpi_dsl import ejecutor as ej

    original = ej._modelo_django

    def sin_recados(entidad):
        if entidad == "recado":
            raise LookupError("No installed app with label 'recados'.")
        return original(entidad)

    monkeypatch.setattr(ej, "_modelo_django", sin_recados)
    assert "recado" not in {e["clave"] for e in esquema_para_ui()["entidades"]}
    assert "- recado (" not in resumen_para_prompt()
    res = ejecutar({"entidad": "recado"})
    assert (res["valor"], res["nota"]) == ("—", "error")


def test_ejecutar_acepta_usuario_posicional(usuario_factory):
    from lib.kpi_dsl import ejecutar
    u = usuario_factory(rol="disenador")
    assert ejecutar({"entidad": "egreso"}, u)["nota"] == "sin permiso"
