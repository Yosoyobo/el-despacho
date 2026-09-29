"""Los KPIs de desempeño (2026-09-29): que todos calculen, que declaren cómo
se juzgan y que sus números sean exactos.

Oscar pidió medir ventas y cobranza, entregas y equipo, rentabilidad, control
y papeleo, «y lo que sea que me falte y no esté viendo». Cada familia tiene
aquí al menos una prueba con datos que fija el número exacto.

Los KPIs de `kpis_desempeno.py` se protegen solos: si el cálculo truena, sale
«—» y queda una advertencia en el log. Por eso la prueba de la base vacía
vigila ese log: un campo mal escrito no debe esconderse detrás del «—».
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db

LOGGER = "apps.taller_home.kpis_desempeno"


def _desempeno():
    from apps.taller_home.kpis_desempeno import catalogo_desempeno
    return catalogo_desempeno()


def _kpi(slug):
    from apps.taller_home.kpis import kpi_por_slug
    k = kpi_por_slug(slug)
    assert k is not None, slug
    return k


def _hoy():
    from django.utils import timezone
    return timezone.localdate()


def _ahora():
    from django.utils import timezone
    return timezone.now()


def _local(dia, hora, minuto=0):
    from django.utils import timezone
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


def _advertencias(caplog):
    return [r.getMessage() for r in caplog.records
            if r.name == LOGGER and r.levelno >= logging.WARNING]


# ═════════════════════════════════════════════════════════════════════════
# El catálogo
# ═════════════════════════════════════════════════════════════════════════

def test_hay_al_menos_35_kpis_nuevos_y_todos_llegan_al_catalogo():
    from apps.taller_home.kpis import KPIS

    nuevos = {k.slug for k in _desempeno()}
    assert len(nuevos) >= 35
    assert nuevos <= {k.slug for k in KPIS}


def test_los_slugs_son_unicos_en_todo_el_catalogo():
    from apps.taller_home.kpis import KPIS

    slugs = [k.slug for k in KPIS]
    repetidos = {s for s in slugs if slugs.count(s) > 1}
    assert not repetidos, repetidos


def test_metadatos_validos():
    from apps.taller_home.kpi_meta import DIRECCIONES, FORMATOS, PERIODOS_ACUMULA
    from apps.taller_home.kpis import CATEGORIAS

    direcciones = {d for d, _ in DIRECCIONES}
    periodos = {p for p, _ in PERIODOS_ACUMULA}
    categorias = {c for c, _ in CATEGORIAS}
    for k in _desempeno():
        assert k.titulo and k.descripcion, k.slug
        assert k.direccion in direcciones, k.slug
        assert k.acumula in periodos, k.slug
        assert k.formato in FORMATOS, k.slug
        assert k.categoria in categorias, k.slug
        assert k.origen == "manual" and k.estado_kpi == "activo", k.slug
        # Un porcentaje de ventana móvil no se prorratea por el avance del mes.
        if k.formato == "pct":
            assert k.acumula == "", k.slug
        assert not k.personal, k.slug  # todos son números del despacho


def test_los_permisos_existen_en_el_catalogo_de_permisos():
    from lib.permisos_defaults import CATALOGO_PERMISOS

    for k in _desempeno():
        assert k.permisos, f"{k.slug} sin permiso: lo vería todo mundo"
        for p in k.permisos:
            modulo, accion = p.split(".", 1)
            assert accion in CATALOGO_PERMISOS.get(modulo, ()), f"{k.slug}: {p}"


def test_desglose_solo_si_declara_desgloses():
    for k in _desempeno():
        assert (k.desglose is None) == (not k.desgloses), k.slug
        assert set(k.desgloses) <= {"persona", "cliente"}, k.slug


def test_hay_desgloses_por_persona_y_por_cliente():
    ambitos = {a for k in _desempeno() for a in k.desgloses}
    assert ambitos == {"persona", "cliente"}


# ═════════════════════════════════════════════════════════════════════════
# Base vacía: todos calculan, nadie inventa ceros
# ═════════════════════════════════════════════════════════════════════════

def test_todos_calculan_en_base_vacia_sin_esconder_errores(usuario_factory, caplog):
    admin = usuario_factory(rol="super_admin")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    for k in _desempeno():
        r = k.calcular(admin)
        assert set(r) >= {"valor", "nota", "link"}, k.slug
        v = r["valor"]
        assert v == "—" or (isinstance(v, int | float) and not isinstance(v, bool)), (k.slug, v)
        assert r["link"].startswith("/"), k.slug
    assert _advertencias(caplog) == []


def test_los_promedios_y_porcentajes_vacios_dicen_sin_datos(usuario_factory):
    """Vacío no es cero: sin nada que promediar no hay número."""
    admin = usuario_factory(rol="super_admin")
    for k in _desempeno():
        if k.formato in ("pct", "dias", "minutos"):
            r = k.calcular(admin)
            assert r["valor"] == "—", k.slug


def test_los_desgloses_responden_en_base_vacia(caplog):
    caplog.set_level(logging.WARNING, logger=LOGGER)
    for k in _desempeno():
        if not k.desglose:
            continue
        for ambito in ("persona", "cliente", "otro"):
            d = k.desglose(ambito)
            assert isinstance(d, dict), k.slug
            if ambito not in k.desgloses:
                assert d == {}, k.slug
    assert _advertencias(caplog) == []


def test_un_kpi_que_truena_dice_sin_datos(usuario_factory, monkeypatch, caplog):
    from apps.taller_home import kpis_desempeno as kd

    def _truena():
        raise RuntimeError("campo que no existe")

    monkeypatch.setattr(kd, "_vendido_por_persona", _truena)
    caplog.set_level(logging.WARNING, logger=LOGGER)
    r = _kpi("vendido-mes").calcular(usuario_factory(rol="super_admin"))
    assert r["valor"] == "—" and r["nota"] == "sin datos"
    assert _kpi("vendido-mes").desglose("persona") == {}
    assert len(_advertencias(caplog)) == 2


# ═════════════════════════════════════════════════════════════════════════
# 1. Ventas y cobranza
# ═════════════════════════════════════════════════════════════════════════

def _cotizacion(cliente, n, *, creado_por=None, precio=None, **kwargs):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem

    cot = Cotizacion.objects.create(
        codigo=f"COT-T-{n:04d}", cliente=cliente, titulo=f"Cot {n}",
        regimen_fiscal="exento", creado_por=creado_por, **kwargs,
    )
    if precio is not None:
        CotizacionItem.objects.create(cotizacion=cot, concepto="Taza",
                                      cantidad=Decimal("1"), precio_unitario=Decimal(precio))
    return cot


def test_dias_para_aprobar_promedia_envio_a_aprobacion(cliente_factory, usuario_factory):
    c = cliente_factory()
    ahora = _ahora()
    _cotizacion(c, 1, estado="aprobada",
                enviada_en=ahora - timedelta(days=10), aprobada_en=ahora - timedelta(days=8))
    _cotizacion(c, 2, estado="aprobada",
                enviada_en=ahora - timedelta(days=6), aprobada_en=ahora - timedelta(days=2))
    # Fuera de la ventana de 90 días: no cuenta.
    _cotizacion(c, 3, estado="aprobada",
                enviada_en=ahora - timedelta(days=200), aprobada_en=ahora - timedelta(days=100))
    r = _kpi("cotizacion-dias-para-aprobar").calcular(usuario_factory(rol="super_admin"))
    assert r["valor"] == 3.0
    assert r["nota"].startswith("2 aprobadas")


def test_vendido_del_mes_se_reparte_por_quien_cotizo(cliente_factory, usuario_factory):
    c = cliente_factory()
    ana = usuario_factory(rol="dueno")
    beto = usuario_factory(rol="dueno")
    ahora = _ahora()
    _cotizacion(c, 1, creado_por=ana, precio="1000", estado="aprobada", aprobada_en=ahora)
    _cotizacion(c, 2, creado_por=beto, precio="500", estado="aprobada", aprobada_en=ahora)
    _cotizacion(c, 3, creado_por=beto, precio="700", estado="rechazada", aprobada_en=ahora)
    _cotizacion(c, 4, creado_por=beto, precio="900", estado="anulada", aprobada_en=ahora)
    k = _kpi("vendido-mes")
    assert k.calcular(ana)["valor"] == 1500.0
    reparto = k.desglose("persona")
    assert reparto == {ana.pk: 1000.0, beto.pk: 500.0}
    assert sum(reparto.values()) == k.calcular(ana)["valor"]
    assert k.admite_meta("persona") and not k.admite_meta("cliente")


def test_dias_de_cobro_de_emitida_a_ultimo_cobro(cliente_factory, usuario_factory):
    from apps.facturacion.models import Factura
    from apps.tesoreria.models import Ingreso

    c = cliente_factory()
    fac = Factura.objects.create(codigo="FAC-T-1", cliente=c, estado="cobrada_total",
                                 emitida_en=_ahora() - timedelta(days=10))
    Ingreso.objects.create(codigo="ING-T-1", monto=Decimal("50"), fecha=_hoy() - timedelta(days=4),
                           descripcion="anticipo", factura=fac, cliente=c)
    Ingreso.objects.create(codigo="ING-T-2", monto=Decimal("50"), fecha=_hoy(),
                           descripcion="resto", factura=fac, cliente=c)
    # Un cobro anulado posterior no alarga la cuenta.
    Ingreso.objects.create(codigo="ING-T-3", monto=Decimal("50"), fecha=_hoy() + timedelta(days=5),
                           descripcion="anulado", factura=fac, cliente=c, anulado=True)
    r = _kpi("facturas-dias-de-cobro").calcular(usuario_factory(rol="super_admin"))
    assert r["valor"] == 10.0


def test_facturado_por_cliente_se_reparte_por_cliente(cliente_factory, usuario_factory):
    from apps.facturacion.models import Factura, FacturaItem

    c1, c2 = cliente_factory(), cliente_factory()
    for n, (cliente, precio, estado) in enumerate(
        [(c1, "100", "emitida"), (c1, "50", "cobrada_total"), (c2, "300", "emitida"),
         (c2, "999", "cancelada")], start=1,
    ):
        f = Factura.objects.create(codigo=f"FAC-T-{n}", cliente=cliente, estado=estado,
                                   regimen_fiscal="exento", emitida_en=_ahora())
        FacturaItem.objects.create(factura=f, descripcion="x", precio_unitario=Decimal(precio))
    k = _kpi("facturado-por-cliente-mes")
    assert k.calcular(None)["valor"] == 450.0
    assert k.desglose("cliente") == {c1.pk: 150.0, c2.pk: 300.0}
    assert k.desglose("persona") == {}


# ═════════════════════════════════════════════════════════════════════════
# 2. Entregas y equipo
# ═════════════════════════════════════════════════════════════════════════

def test_proyectos_a_tiempo_y_acotado_a_lo_suyo(proyecto_factory, usuario_factory, monkeypatch):
    from apps.los_proyectos.models import ProyectoAsignacion

    hoy = _hoy()
    admin = usuario_factory(rol="super_admin")
    # Entregado justo el día prometido: eso es a tiempo.
    a_tiempo = proyecto_factory(estado="entregado", fecha_real_entrega=hoy - timedelta(days=5),
                                fecha_compromiso=hoy - timedelta(days=5))
    tarde = proyecto_factory(estado="entregado", fecha_real_entrega=hoy - timedelta(days=5),
                             fecha_compromiso=hoy - timedelta(days=10))
    # Sin fecha prometida no se puede juzgar; entregado hace medio año, fuera.
    proyecto_factory(estado="entregado", fecha_real_entrega=hoy - timedelta(days=5))
    proyecto_factory(estado="entregado", fecha_real_entrega=hoy - timedelta(days=180),
                     fecha_compromiso=hoy - timedelta(days=200))
    k = _kpi("proyectos-a-tiempo-pct")
    assert k.acotado
    assert k.calcular(admin)["valor"] == 50.0

    diseñador = usuario_factory(rol="disenador")
    ProyectoAsignacion.objects.create(proyecto=tarde, usuario=diseñador)
    monkeypatch.setattr("lib.permisos.solo_proyectos_asignados", lambda u: u == diseñador)
    assert k.calcular(diseñador)["valor"] == 0.0
    assert k.calcular(admin)["valor"] == 50.0
    assert a_tiempo.pk  # (el que llegó a tiempo no es suyo)


def test_tareas_a_tiempo_por_persona(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea

    hoy = _hoy()
    p = proyecto_factory()
    ana, beto = usuario_factory(), usuario_factory()
    for persona, compromiso in ((ana, hoy), (ana, hoy - timedelta(days=2)), (beto, hoy)):
        Tarea.objects.create(proyecto=p, titulo="t", estado="completada", asignada_a=persona,
                             fecha_compromiso=compromiso, completada_en=_ahora())
    # Abierta: no entra al porcentaje.
    Tarea.objects.create(proyecto=p, titulo="t", estado="pendiente", asignada_a=beto,
                         fecha_compromiso=hoy - timedelta(days=1))
    k = _kpi("tareas-a-tiempo-pct")
    assert k.calcular(ana)["valor"] == 66.7
    assert k.desglose("persona") == {ana.pk: 50.0, beto.pk: 100.0}
    assert _kpi("tareas-abiertas-por-persona").desglose("persona") == {beto.pk: 1.0}


def test_horas_extra_contra_el_horario(usuario_factory):
    from apps.checador.models import HorarioLaboral, Jornada

    hoy = _hoy()
    HorarioLaboral.objects.all().delete()  # las migraciones siembran un horario global
    HorarioLaboral.objects.create(usuario=None, dia_semana=hoy.weekday(),
                                  hora_entrada=time(9), hora_salida=time(17))
    ana, beto = usuario_factory(), usuario_factory()
    Jornada.objects.create(usuario=ana, fecha=hoy, estado="cerrada",
                           entrada_en=_local(hoy, 9), salida_en=_local(hoy, 19))
    Jornada.objects.create(usuario=beto, fecha=hoy, estado="cerrada",
                           entrada_en=_local(hoy, 9), salida_en=_local(hoy, 16))
    k = _kpi("horas-extra-mes")
    assert k.calcular(ana)["valor"] == 2.0
    assert k.desglose("persona") == {ana.pk: 2.0, beto.pk: 0.0}
    horas = _kpi("horas-equipo-mes")
    assert horas.calcular(ana)["valor"] == 17.0
    assert horas.desglose("persona") == {ana.pk: 10.0, beto.pk: 7.0}


def test_horas_extra_sin_horarios_no_es_cero(usuario_factory):
    from apps.checador.models import HorarioLaboral, Jornada

    HorarioLaboral.objects.all().delete()  # las migraciones siembran un horario global
    hoy = _hoy()
    ana = usuario_factory()
    Jornada.objects.create(usuario=ana, fecha=hoy, estado="cerrada",
                           entrada_en=_local(hoy, 9), salida_en=_local(hoy, 19))
    assert _kpi("horas-extra-mes").calcular(ana)["valor"] == "—"


# ═════════════════════════════════════════════════════════════════════════
# 3. Rentabilidad
# ═════════════════════════════════════════════════════════════════════════

def _centro():
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.get_or_create(nombre="Operación", defaults={"slug": "operacion"})[0]


def test_cobrado_por_cliente_suma_y_reparte(cliente_factory):
    from apps.tesoreria.models import Ingreso

    c1, c2 = cliente_factory(), cliente_factory()
    hoy = _hoy()
    filas = [(c1, "100", hoy), (c1, "50", hoy - timedelta(days=30)), (c2, "300", hoy),
             (None, "999", hoy), (c2, "777", hoy - timedelta(days=400))]
    for n, (cliente, monto, fecha) in enumerate(filas, start=1):
        Ingreso.objects.create(codigo=f"ING-T-{n}", monto=Decimal(monto), fecha=fecha,
                               descripcion="cobro", cliente=cliente)
    Ingreso.objects.create(codigo="ING-T-99", monto=Decimal("5000"), fecha=hoy,
                           descripcion="anulado", cliente=c1, anulado=True)
    k = _kpi("cobrado-por-cliente-12m")
    assert k.calcular(None)["valor"] == 450.0
    assert k.desglose("cliente") == {c1.pk: 150.0, c2.pk: 300.0}
    assert k.admite_meta("cliente")


def test_gasto_ligado_a_proyecto(proyecto_factory):
    from apps.tesoreria.models import Egreso

    p = proyecto_factory()
    hoy = _hoy()
    for n, (monto, proyecto) in enumerate([("300", p), ("100", None)], start=1):
        Egreso.objects.create(codigo=f"EGR-T-{n}", monto=Decimal(monto), fecha=hoy,
                              descripcion="gasto", centro_de_costo=_centro(), proyecto=proyecto)
    assert _kpi("gasto-ligado-a-proyecto-pct").calcular(None)["valor"] == 75.0
    gasto = _kpi("gasto-por-cliente-mes")
    assert gasto.calcular(None)["valor"] == 300.0
    assert gasto.desglose("cliente") == {p.cliente_id: 300.0}


# ═════════════════════════════════════════════════════════════════════════
# 4. Control y papeleo
# ═════════════════════════════════════════════════════════════════════════

def test_gastos_sin_comprobante_del_mes():
    from apps.tesoreria.models import Egreso

    hoy = _hoy()
    for n, comprobante in enumerate([True, False, False], start=1):
        Egreso.objects.create(codigo=f"EGR-T-{n}", monto=Decimal("10"), fecha=hoy,
                              descripcion="gasto", centro_de_costo=_centro(),
                              tiene_comprobante=comprobante)
    Egreso.objects.create(codigo="EGR-T-9", monto=Decimal("10"), fecha=hoy, descripcion="x",
                          centro_de_costo=_centro(), anulado=True)
    assert _kpi("egresos-sin-comprobante-mes").calcular(None)["valor"] == 2


def test_clientes_sin_rfc_cuenta_las_razones_sociales(cliente_factory):
    from apps.la_cartera.models import ClienteRazonSocial

    cliente_factory(rfc="")
    con_razon = cliente_factory(rfc="")
    ClienteRazonSocial.objects.create(cliente=con_razon, razon_social="Grupo S.A.",
                                      rfc="GRU010101AAA")
    cliente_factory(rfc="ABC010101AAA")
    cliente_factory(rfc="", estado="prospecto")
    assert _kpi("clientes-sin-rfc").calcular(None)["valor"] == 1
    assert _kpi("prospectos-cartera").calcular(None)["valor"] == 1


def test_meses_sin_cerrar_sin_asientos_no_es_cero():
    assert _kpi("meses-sin-cerrar").calcular(None)["valor"] == "—"


# ═════════════════════════════════════════════════════════════════════════
# 5. Lo que faltaba
# ═════════════════════════════════════════════════════════════════════════

def test_mandados_cancelados(proyecto_factory):
    from apps.el_pizarron.models import Mandado, Tarea

    p = proyecto_factory()
    ahora = _ahora()
    for estado in ("entregado", "entregado", "entregado", "cancelado", "por_asignar"):
        t = Tarea.objects.create(proyecto=p, titulo="llevar", fecha_compromiso=_hoy())
        Mandado.objects.create(
            tarea=t, estado=estado,
            entregado_en=ahora if estado == "entregado" else None,
            cancelado_en=ahora if estado == "cancelado" else None,
        )
    assert _kpi("mandados-cancelados-pct").calcular(None)["valor"] == 25.0


def test_paradas_puntuales_con_tolerancia(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Mandado, ParadaRuta, Ruta, Tarea

    hoy = _hoy()
    runner = usuario_factory()
    p = proyecto_factory()
    ruta = Ruta.objects.create(fecha=hoy, runner=runner, estado="despachada")
    for n, llegada in enumerate([_local(hoy, 10, 10), _local(hoy, 10, 30)]):
        t = Tarea.objects.create(proyecto=p, titulo="llevar", fecha_compromiso=hoy)
        m = Mandado.objects.create(tarea=t, estado="entregado", entregado_en=llegada)
        ParadaRuta.objects.create(ruta=ruta, mandado=m, orden=n, hora_cita=time(10))
    assert _kpi("paradas-puntuales-pct").calcular(None)["valor"] == 50.0


def test_campanas_que_fallan():
    from campanas.models import CampanaCorreo, CampanaEnvio

    camp = CampanaCorreo.objects.create(plantilla_slug="novedades")
    for estado in ("enviado", "enviado", "enviado", "fallido"):
        CampanaEnvio.objects.create(campana=camp, email="a@ejemplo.com", estado=estado)
    assert _kpi("campanas-fallos-pct").calcular(None)["valor"] == 25.0
