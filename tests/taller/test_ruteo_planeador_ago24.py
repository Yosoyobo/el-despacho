"""El planeador deja de preguntar de un par a la vez (2026-08-24).

Medido en producción ANTES de tocar nada, con paradas al azar en la ciudad:

    10 paradas, 1 runner  →  1,451 consultas  ·  1.9 s
    12 paradas, 3 runners →  3,508 consultas  ·  4.2 s

`ruteo.matriz` resuelve 25×25 en 178 ms, de una. La prueba que más importa aquí
es la que CUENTA: si alguien vuelve a meter un `_d(a, b)` sin tabla dentro de un
bucle de optimización, el número se dispara y esto lo caza.

La segunda: las HORAS. OSRM devuelve la duración por tramo —sabe de tipos de
calle y límites de velocidad— y el planeador la tiraba para dividir los metros
entre una velocidad plana. Zócalo→Satélite: el mapa dice 24 minutos, la
velocidad plana decía 49.
"""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

HOY = dt.date(2026, 8, 25)

CENTRO = (19.4326, -99.1332)
CERCA = (19.4340, -99.1400)
LEJOS = (19.3600, -99.2700)
MEDIO = (19.4000, -99.1800)


def _hacer_runner(*usuarios):
    from cuentas.models.rol import Rol
    r = Rol.objects.get(nombre="Runner")
    for u in usuarios:
        u.roles_extra.add(r)


def _mandado(proyecto, punto, *, titulo="Entrega", fecha=HOY, hora=None):
    from apps.el_pizarron.models import Mandado, Tarea
    t = Tarea.objects.create(
        proyecto=proyecto, titulo=titulo, tipo="entrega", estado="pendiente",
        fecha_compromiso=fecha, hora=hora,
        destino_lat=punto[0], destino_lng=punto[1], destino_etiqueta=titulo,
    )
    return Mandado.objects.get(tarea=t)


@pytest.fixture
def _contador(monkeypatch):
    """Cuenta consultas al mapa por tipo, sin salir a la red."""
    from lib import ruteo

    cuenta = {"route": 0, "table": 0}

    def _matriz(puntos, *, opciones=None):
        cuenta["table"] += 1
        n = len(puntos)
        # Distancias creíbles: |i-j| km, para que ordenar tenga sentido.
        dist = [[abs(i - j) * 1000.0 for j in range(n)] for i in range(n)]
        dur = [[abs(i - j) * 120.0 for j in range(n)] for i in range(n)]
        return {"distancias": dist, "duraciones": dur, "fuente": ruteo.FUENTE_CALLES}

    def _distancia(a, b, *, opciones=None):
        cuenta["route"] += 1
        return 1000.0

    monkeypatch.setattr(ruteo, "matriz", _matriz)
    monkeypatch.setattr(ruteo, "distancia", _distancia)
    monkeypatch.setattr(ruteo, "disponible", lambda **k: True)
    return cuenta


# ── 1. Una matriz por reparto ─────────────────────────────────────────────────

def test_planear_pide_una_matriz_y_ninguna_ruta_suelta(
        proyecto_factory, usuario_factory, _contador):
    """El corazón del sprint: 3,508 → 1."""
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="r1@lc.mx")
    b = usuario_factory(rol="disenador", email="r2@lc.mx")
    _hacer_runner(a, b)
    for i, punto in enumerate((CENTRO, CERCA, LEJOS, MEDIO)):
        _mandado(p, punto, titulo=f"Entrega {i}")

    planear_dia(HOY, origen_modo="runner_abierta")

    assert _contador["table"] == 1, _contador
    assert _contador["route"] == 0, _contador


def test_el_numero_de_consultas_no_crece_con_las_paradas(
        proyecto_factory, usuario_factory, _contador):
    """Ocho paradas cuestan lo mismo que cuatro: una consulta."""
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="r3@lc.mx")
    _hacer_runner(a)
    for i in range(8):
        _mandado(p, (19.40 + i * 0.01, -99.20 - i * 0.01), titulo=f"E{i}")

    planear_dia(HOY, origen_modo="runner_abierta")

    assert _contador["table"] == 1, _contador
    assert _contador["route"] == 0, _contador


# ── 2. Las horas salen de la duración del mapa ────────────────────────────────

def test_las_horas_usan_la_duracion_del_mapa_no_la_velocidad_plana():
    """Con duración disponible, la velocidad promedio del GUI no se usa."""
    from apps.el_pizarron import planeador

    class _TablaFalsa:
        def metros(self, a, b):
            return 20356.0

        def segundos(self, a, b):
            return 1431.0  # 23.85 min según el mapa

    minutos = planeador._minutos_viaje(CENTRO, LEJOS, 20356.0, _TablaFalsa())
    assert minutos == 24
    # La cuenta vieja (20.356 km / 25 km/h) daba 49: el doble.
    assert planeador._minutos_de(20356.0) == 49


def test_sin_duracion_se_cae_a_la_velocidad_configurada():
    from apps.el_pizarron import planeador

    class _SinDuracion:
        def metros(self, a, b):
            return 20356.0

        def segundos(self, a, b):
            return None

    assert (planeador._minutos_viaje(CENTRO, LEJOS, 20356.0, _SinDuracion())
            == planeador._minutos_de(20356.0))


def test_estimar_horas_respeta_la_duracion_de_la_tabla():
    from datetime import time

    from apps.el_pizarron import planeador

    class _Tabla:
        def metros(self, a, b):
            return 6000.0

        def segundos(self, a, b):
            return 600.0  # 10 minutos exactos

    paradas = [{"lat": 19.44, "lng": -99.20, "hora": None}]
    estimadas = planeador.estimar_horas(
        CENTRO, paradas, inicio=time(9, 0), tabla=_Tabla())
    assert estimadas[0][1] == time(9, 10)


# ── 3. Las citas siguen mandando (regresión del planeador) ───────────────────

def test_la_cita_sigue_siendo_ancla_con_la_tabla(proyecto_factory, usuario_factory,
                                                 _contador):
    """La regla de Oscar no se toca: la hora es cita fija."""
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="cita@lc.mx")
    _hacer_runner(a)
    _mandado(p, LEJOS, titulo="Cita 9", hora=dt.time(9, 0))
    _mandado(p, CERCA, titulo="Cita 11", hora=dt.time(11, 0))
    _mandado(p, MEDIO, titulo="Libre")

    planear_dia(HOY, origen_modo="runner_abierta")

    ruta = Ruta.objects.get(fecha=HOY)
    con_cita = [pa.etiqueta for pa in ruta.paradas.all() if pa.hora_cita]
    assert con_cita == ["Cita 9", "Cita 11"]


# ── 4. El mapa del planeador dibuja por calles ────────────────────────────────

def test_el_mapa_pide_el_trazo_por_calles(monkeypatch):
    from apps.el_pizarron import views

    llamadas = []

    def _trazo(puntos, *, opciones=None):
        llamadas.append(list(puntos))
        return [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]]

    from lib import ruteo
    monkeypatch.setattr(ruteo, "trazo", _trazo)

    salida = views._trazo_por_calles([[19.43, -99.13], [19.51, -99.24]])
    assert salida == [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]]
    assert llamadas == [[(19.43, -99.13), (19.51, -99.24)]]


def test_sin_mapa_el_dibujo_cae_a_las_lineas_rectas(monkeypatch):
    from apps.el_pizarron import views

    from lib import ruteo

    monkeypatch.setattr(ruteo, "trazo", lambda *a, **k: None)
    coords = [[19.43, -99.13], [19.51, -99.24]]
    assert views._trazo_por_calles(coords) == coords


# ── 5. Indicaciones giro a giro ───────────────────────────────────────────────

def _ruta_con_parada(proyecto_factory, usuario_factory, email):
    from apps.el_pizarron.models.ruta import ParadaRuta, Ruta

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email=email)
    _hacer_runner(a)
    m = _mandado(p, CERCA, titulo="Parada")
    ruta = Ruta.objects.create(fecha=HOY, runner=a, estado="borrador",
                               origen_modo="runner_abierta",
                               origen_lat=CENTRO[0], origen_lng=CENTRO[1],
                               origen_etiqueta="La oficina")
    parada = ParadaRuta.objects.create(ruta=ruta, mandado=m, orden=1,
                                       lat=CERCA[0], lng=CERCA[1],
                                       etiqueta="Parada")
    return a, ruta, parada


def test_las_indicaciones_abren_en_un_modal(client, proyecto_factory,
                                            usuario_factory, monkeypatch):
    from lib import ruteo

    a, _, parada = _ruta_con_parada(proyecto_factory, usuario_factory, "ind@lc.mx")
    monkeypatch.setattr(ruteo, "indicaciones", lambda *args, **kw: {
        "metros": 1200, "segundos": 300,
        "pasos": [{"texto": "Da vuelta a la derecha a Reforma", "metros": 120,
                   "calle": "Reforma"}],
    })

    client.force_login(a)
    r = client.get(f"/rutas/paradas/{parada.pk}/indicaciones", HTTP_HX_REQUEST="true")
    cuerpo = r.content.decode()
    assert r.status_code == 200
    assert "Da vuelta a la derecha a Reforma" in cuerpo
    assert "La oficina" in cuerpo  # de dónde sale


def test_sin_mapa_las_indicaciones_lo_dicen(client, proyecto_factory,
                                            usuario_factory, monkeypatch):
    from lib import ruteo

    a, _, parada = _ruta_con_parada(proyecto_factory, usuario_factory, "ind2@lc.mx")
    monkeypatch.setattr(ruteo, "indicaciones", lambda *args, **kw: None)

    client.force_login(a)
    r = client.get(f"/rutas/paradas/{parada.pk}/indicaciones", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "No se pudieron armar las indicaciones" in r.content.decode()


def test_un_runner_no_ve_las_indicaciones_de_otro(client, proyecto_factory,
                                                  usuario_factory):
    _, _, parada = _ruta_con_parada(proyecto_factory, usuario_factory, "duenio@lc.mx")
    otro = usuario_factory(rol="disenador", email="intruso@lc.mx")
    _hacer_runner(otro)

    client.force_login(otro)
    r = client.get(f"/rutas/paradas/{parada.pk}/indicaciones", HTTP_HX_REQUEST="true")
    assert r.status_code == 403


# ── 6. El pin que quedó lejos de la calle ─────────────────────────────────────

def test_avisa_si_el_pin_cayo_lejos_de_una_calle(client, proyecto_factory,
                                                 usuario_factory, monkeypatch):
    """Avisa, NUNCA bloquea: la ubicación no detiene una acción en este repo."""
    from lib import ruteo

    p = proyecto_factory(estado="en_proceso_diseno")
    jefe = usuario_factory(rol="super_admin", email="pin@lc.mx")
    m = _mandado(p, CENTRO, titulo="Con pin")
    monkeypatch.setattr(ruteo, "cerca_de_calle",
                        lambda *a, **k: {"metros": 480.0, "calle": "Eje Central"})

    client.force_login(jefe)
    r = client.post(f"/mandados/{m.pk}/destino",
                    {"lat": "19.44", "lng": "-99.20", "etiqueta": "Bodega"},
                    HTTP_HX_REQUEST="true", follow=False)
    assert r.status_code == 204  # se guardó igual
    m.tarea.refresh_from_db()
    assert m.tarea.destino_etiqueta == "Bodega"


def test_un_pin_sobre_la_calle_no_molesta(client, proyecto_factory,
                                          usuario_factory, monkeypatch):
    from lib import ruteo

    p = proyecto_factory(estado="en_proceso_diseno")
    jefe = usuario_factory(rol="super_admin", email="pin2@lc.mx")
    m = _mandado(p, CENTRO, titulo="Con pin")
    monkeypatch.setattr(ruteo, "cerca_de_calle",
                        lambda *a, **k: {"metros": 12.0, "calle": "Reforma"})

    client.force_login(jefe)
    r = client.post(f"/mandados/{m.pk}/destino",
                    {"lat": "19.44", "lng": "-99.20", "etiqueta": "Bodega"},
                    HTTP_HX_REQUEST="true")
    assert r.status_code == 204
