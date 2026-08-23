"""La pantalla de Rutas en La Gerencia (Ajustes)."""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_abre_para_el_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin", email="cfgr1@lc.mx")
    client.force_login(u)
    r = client.get("/ajustes/rutas/")
    assert r.status_code == 200
    assert b"Velocidad promedio" in r.content


def test_guardar_cambia_los_supuestos(client, usuario_factory):
    from ajustes.models import ConfiguracionRutas
    u = usuario_factory(rol="super_admin", email="cfgr2@lc.mx")
    client.force_login(u)
    r = client.post("/ajustes/rutas/", {
        "velocidad_kmh": "42.5", "minutos_por_parada": "15",
        "hora_inicio": "07:30", "max_paradas_por_ruta": "12",
    })
    assert r.status_code == 302
    cfg = ConfiguracionRutas.obtener()
    assert cfg.velocidad_kmh == Decimal("42.5")
    assert cfg.minutos_por_parada == 15
    assert cfg.hora_inicio.strftime("%H:%M") == "07:30"
    assert cfg.max_paradas_por_ruta == 12


def test_una_velocidad_absurda_se_acota(client, usuario_factory):
    from ajustes.models import ConfiguracionRutas
    u = usuario_factory(rol="super_admin", email="cfgr3@lc.mx")
    client.force_login(u)
    client.post("/ajustes/rutas/", {
        "velocidad_kmh": "0", "minutos_por_parada": "10",
        "hora_inicio": "09:00", "max_paradas_por_ruta": "9",
    })
    # Cero dividiría entre cero al estimar tiempos.
    assert ConfiguracionRutas.obtener().velocidad_kmh >= Decimal("1")


def test_basura_en_un_campo_deja_el_valor_anterior(client, usuario_factory):
    from ajustes.models import ConfiguracionRutas
    u = usuario_factory(rol="super_admin", email="cfgr4@lc.mx")
    antes = ConfiguracionRutas.obtener().minutos_por_parada
    client.force_login(u)
    client.post("/ajustes/rutas/", {
        "velocidad_kmh": "25", "minutos_por_parada": "no soy un número",
        "hora_inicio": "09:00", "max_paradas_por_ruta": "9",
    })
    assert ConfiguracionRutas.obtener().minutos_por_parada == antes


def test_un_disenador_no_entra(client, usuario_factory):
    u = usuario_factory(rol="disenador", email="cfgr5@lc.mx")
    client.force_login(u)
    assert client.get("/ajustes/rutas/").status_code in (302, 403)
