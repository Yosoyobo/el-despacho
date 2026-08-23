"""Los supuestos del planeador, editables desde La Gerencia (Oscar 2026-08-23).

`VELOCIDAD_KMH` y `MINUTOS_POR_PARADA` eran constantes del código. De ellas salen
las HORAS que ve el runner, así que las ajusta quien conoce la ciudad.

El test que importa es el de la conexión: que cambiar el número en la pantalla
CAMBIE la hora que estima el planeador. Sin ése, el resto es una pantalla bonita
que no hace nada.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

LEJOS = (19.3600, -99.2700)   # ~15 km del centro
CENTRO = (19.4326, -99.1332)


@pytest.fixture(autouse=True)
def _sin_cache():
    """El planeador recuerda la configuración un minuto; entre tests hay que
    olvidarla o el segundo lee lo del primero."""
    from apps.el_pizarron.planeador import olvidar_configuracion
    olvidar_configuracion()
    yield
    olvidar_configuracion()


def _cfg(**cambios):
    from ajustes.models import ConfiguracionRutas
    cfg = ConfiguracionRutas.obtener()
    for k, v in cambios.items():
        setattr(cfg, k, v)
    cfg.save()
    from apps.el_pizarron.planeador import olvidar_configuracion
    olvidar_configuracion()
    return cfg


def test_la_fila_unica_nace_con_los_defaults():
    from ajustes.models import ConfiguracionRutas
    cfg = ConfiguracionRutas.obtener()
    assert cfg.pk == 1
    assert cfg.velocidad_kmh == Decimal("25.0")
    assert cfg.minutos_por_parada == 10
    assert cfg.hora_inicio == dt.time(9, 0)
    # Y pedirla dos veces no crea dos.
    assert ConfiguracionRutas.obtener().pk == 1
    assert ConfiguracionRutas.objects.count() == 1


# ── El que importa: la pantalla mueve la estimación ───────────────────────────

def test_subir_la_velocidad_adelanta_la_llegada():
    from apps.el_pizarron.planeador import estimar_horas

    secuencia = [{"lat": LEJOS[0], "lng": LEJOS[1], "hora": None}]

    _cfg(velocidad_kmh=Decimal("25.0"))
    (_, lento, _), = estimar_horas(CENTRO, secuencia, inicio=dt.time(9, 0))

    _cfg(velocidad_kmh=Decimal("80.0"))
    (_, rapido, _), = estimar_horas(CENTRO, secuencia, inicio=dt.time(9, 0))

    assert rapido < lento, f"a 80 km/h debería llegar antes que a 25 ({rapido} vs {lento})"


def test_el_tiempo_por_parada_corre_la_siguiente():
    from apps.el_pizarron.planeador import estimar_horas

    secuencia = [
        {"lat": CENTRO[0], "lng": CENTRO[1], "hora": None},
        {"lat": LEJOS[0], "lng": LEJOS[1], "hora": None},
    ]
    _cfg(minutos_por_parada=0)
    sin_espera = estimar_horas(CENTRO, secuencia, inicio=dt.time(9, 0))[1][1]

    _cfg(minutos_por_parada=45)
    con_espera = estimar_horas(CENTRO, secuencia, inicio=dt.time(9, 0))[1][1]

    assert con_espera > sin_espera


def test_la_hora_de_salida_manda_cuando_no_hay_citas():
    from apps.el_pizarron.planeador import estimar_horas

    _cfg(hora_inicio=dt.time(6, 30))
    secuencia = [{"lat": CENTRO[0], "lng": CENTRO[1], "hora": None}]
    (_, hora, _), = estimar_horas(CENTRO, secuencia)
    assert hora >= dt.time(6, 30)
    assert hora < dt.time(9, 0)


def test_el_tope_de_paradas_sale_de_la_configuracion(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Mandado, Tarea
    from apps.el_pizarron.planeador import planear_dia

    from cuentas.models.rol import Rol

    u = usuario_factory(rol="disenador", email="tope@lc.mx")
    u.roles_extra.add(Rol.objects.get(nombre="Runner"))
    p = proyecto_factory(estado="en_proceso_diseno")
    hoy = dt.date(2026, 8, 25)
    for i in range(4):
        Tarea.objects.create(
            proyecto=p, titulo=f"E{i}", tipo="entrega", estado="pendiente",
            fecha_compromiso=hoy, destino_lat=19.43 + i * 0.01, destino_lng=-99.13,
        )
    assert Mandado.objects.count() == 4

    _cfg(max_paradas_por_ruta=2)
    res = planear_dia(hoy, origen_modo="runner_abierta")
    # Con un solo runner y tope 2, dos entregas se quedan fuera y se DICE.
    assert sum(r.total_paradas for r in res["rutas"]) == 2
    assert len(res["sobrantes"]) == 2


# ── Defensas ──────────────────────────────────────────────────────────────────

def test_una_velocidad_en_cero_no_divide_entre_cero():
    """Guardar 0 se acota; y si alguien la mete a mano en la base, `_cfg` la ignora."""
    from apps.el_pizarron.planeador import _cfg as leer
    _cfg(velocidad_kmh=Decimal("0"))
    assert leer().velocidad_kmh > 0


def test_sin_configuracion_legible_se_planea_con_los_respaldos(monkeypatch):
    from apps.el_pizarron import planeador

    def _explota():
        raise RuntimeError("base caída")

    monkeypatch.setattr("ajustes.models.ConfiguracionRutas.obtener",
                        staticmethod(_explota))
    planeador.olvidar_configuracion()
    cfg = planeador._cfg()
    assert cfg.velocidad_kmh == planeador.VELOCIDAD_KMH
    assert cfg.minutos_por_parada == planeador.MINUTOS_POR_PARADA
