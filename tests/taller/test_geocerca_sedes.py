"""S-LC-Feedback-V12 — directorio de Sedes/POI, geocerca global, horas de semana.

Cubre el modelo SedeLC, la evaluación de ubicación contra el directorio
(modo Libre/Restringido, no-bloqueante), el balance semanal y el render del
tablero (mapa de verificación + tarjetas de horas).
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

# Centro de prueba (CDMX) y un punto ~90 m al lado.
LAT, LNG = 19.4326, -99.1332
LAT_CERCA, LNG_CERCA = 19.4334, -99.1332   # ~89 m al norte
LAT_LEJOS, LNG_LEJOS = 19.4600, -99.1332   # ~3 km al norte


def _sede(**kw):
    from apps.checador.models import SedeLC
    base = {"nombre": "Oficina 1", "lat": LAT, "lng": LNG, "radio_m": 150, "activa": True}
    base.update(kw)
    return SedeLC.objects.create(**base)


# ── Modelo ────────────────────────────────────────────────────────────────

def test_sede_contiene_y_distancia():
    s = _sede(radio_m=150)
    assert s.contiene(LAT_CERCA, LNG_CERCA) is True
    assert s.contiene(LAT_LEJOS, LNG_LEJOS) is False
    d = s.distancia_a_m(LAT_LEJOS, LNG_LEJOS)
    assert d > 2000


def test_sede_sin_pin_no_evalua():
    s = _sede(lat=None, lng=None)
    assert s.tiene_pin is False
    assert s.contiene(LAT, LNG) is None


def test_config_geocerca_singleton_default_libre():
    from apps.checador.models import ConfiguracionGeocerca
    c = ConfiguracionGeocerca.obtener()
    assert c.pk == 1
    assert c.modo == "libre"
    # Segunda llamada no crea otra fila.
    assert ConfiguracionGeocerca.obtener().pk == 1
    assert ConfiguracionGeocerca.objects.count() == 1


# ── Servicios ───────────────────────────────────────────────────────────────

def test_evaluar_ubicacion_dentro_y_fuera():
    from apps.checador import services
    _sede(radio_m=150)
    dentro = services.evaluar_ubicacion(LAT_CERCA, LNG_CERCA)
    assert dentro and dentro["dentro"] is True
    fuera = services.evaluar_ubicacion(LAT_LEJOS, LNG_LEJOS)
    assert fuera and fuera["dentro"] is False


def test_evaluar_ubicacion_sin_sedes_es_none():
    from apps.checador import services
    assert services.evaluar_ubicacion(LAT, LNG) is None


def test_geocerca_restringido_anota_fuera(usuario_factory):
    from apps.checador import services
    from apps.checador.models import ConfiguracionGeocerca, Jornada
    ConfiguracionGeocerca.objects.update_or_create(pk=1, defaults={"modo": "restringido"})
    _sede(radio_m=150)
    u = usuario_factory(rol="disenador")
    j = Jornada.objects.create(
        usuario=u, fecha=datetime.date(2026, 6, 15),
        entrada_en=timezone.now(), entrada_lat=LAT_LEJOS, entrada_lng=LNG_LEJOS,
    )
    services._evaluar_geocerca(u, j)
    j.refresh_from_db()
    assert "fuera de las sedes" in j.notas.lower()


def test_geocerca_libre_no_anota(usuario_factory):
    from apps.checador import services
    from apps.checador.models import ConfiguracionGeocerca, Jornada
    ConfiguracionGeocerca.objects.update_or_create(pk=1, defaults={"modo": "libre"})
    _sede(radio_m=150)
    u = usuario_factory(rol="disenador")
    j = Jornada.objects.create(
        usuario=u, fecha=datetime.date(2026, 6, 15),
        entrada_en=timezone.now(), entrada_lat=LAT_LEJOS, entrada_lng=LNG_LEJOS,
    )
    services._evaluar_geocerca(u, j)
    j.refresh_from_db()
    assert j.notas == ""


def test_geocerca_dentro_nunca_anota(usuario_factory):
    from apps.checador import services
    from apps.checador.models import ConfiguracionGeocerca, Jornada
    ConfiguracionGeocerca.objects.update_or_create(pk=1, defaults={"modo": "restringido"})
    _sede(radio_m=150)
    u = usuario_factory(rol="disenador")
    j = Jornada.objects.create(
        usuario=u, fecha=datetime.date(2026, 6, 15),
        entrada_en=timezone.now(), entrada_lat=LAT_CERCA, entrada_lng=LNG_CERCA,
    )
    services._evaluar_geocerca(u, j)
    j.refresh_from_db()
    assert j.notas == ""


# ── Balance semanal (item 7) ─────────────────────────────────────────────────

def test_balance_semana_devuelve_estructura(usuario_factory):
    from apps.checador import services
    u = usuario_factory(rol="disenador")
    ahora = timezone.make_aware(datetime.datetime(2026, 6, 15, 13, 0))  # lunes
    b = services.balance_semana(u, ahora=ahora)
    assert set(["trabajadas_horas", "esperadas_horas", "balance_horas", "a_favor", "lunes", "hoy"]) <= set(b)
    assert b["lunes"] == datetime.date(2026, 6, 15)


# ── Tablero (items 6 + 7) ─────────────────────────────────────────────────────

def test_tablero_muestra_mapa_y_horas(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    _sede()
    client.force_login(u)
    resp = client.get("/checador/")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert 'id="mapa-checar"' in cuerpo          # mapa de verificación (item 6)
    assert "Esta semana" in cuerpo               # tarjeta de horas (item 7)
    assert "Este mes" in cuerpo
    assert "Modo Libre" in cuerpo                # etiqueta de geocerca
