"""Ajustes → Rutas: lo que se le pide al mapa (2026-08-24).

Regla del proyecto: lo configurable vive en un GUI de La Gerencia. Estas
opciones existían en el mapa desde el día uno y nunca habían tenido perilla.

El detalle que se defiende aquí es la **validación en el servidor**: un `<select>`
se puede manipular, y `exclude=toll,motorway` hace que el mapa conteste
«Exclude flag combination is not supported» — o sea que un valor inventado no
degrada la medición, la ROMPE.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def _abrir(client, usuario_factory):
    jefe = usuario_factory(rol="super_admin", email="rutas-mapa@lc.mx")
    client.force_login(jefe)
    return jefe


def test_la_pantalla_ofrece_las_opciones_del_mapa(client, usuario_factory):
    _abrir(client, usuario_factory)
    cuerpo = client.get("/ajustes/rutas/").content.decode()
    assert 'name="evitar"' in cuerpo
    assert 'name="factor_trafico"' in cuerpo
    assert 'name="acera_del_cliente"' in cuerpo
    assert 'name="modo"' in cuerpo
    assert "Evitar casetas" in cuerpo


def test_guarda_lo_que_se_eligio(client, usuario_factory):
    from ajustes.models import ConfiguracionRutas

    _abrir(client, usuario_factory)
    client.post("/ajustes/rutas/", {
        "velocidad_kmh": "25", "minutos_por_parada": "10",
        "hora_inicio": "09:00", "max_paradas_por_ruta": "9",
        "evitar": "toll", "factor_trafico": "1.4",
        "acera_del_cliente": "1", "modo": "bici",
    })
    cfg = ConfiguracionRutas.obtener()
    assert cfg.evitar == "toll"
    assert float(cfg.factor_trafico) == 1.4
    assert cfg.acera_del_cliente is True
    assert cfg.modo == "bici"


def test_una_exclusion_inventada_se_descarta(client, usuario_factory):
    """El mapa sólo trae precocidas toll/motorway/ferry; otra cosa lo rompe."""
    from ajustes.models import ConfiguracionRutas

    _abrir(client, usuario_factory)
    client.post("/ajustes/rutas/", {
        "velocidad_kmh": "25", "minutos_por_parada": "10",
        "hora_inicio": "09:00", "max_paradas_por_ruta": "9",
        "evitar": "toll,motorway",  # combinación NO soportada
    })
    assert ConfiguracionRutas.obtener().evitar == ""


def test_el_factor_de_trafico_no_baja_de_uno(client, usuario_factory):
    """Decir que se llega antes de lo que el mapa cree es al revés de lo que
    pasa en la calle."""
    from ajustes.models import ConfiguracionRutas

    _abrir(client, usuario_factory)
    client.post("/ajustes/rutas/", {
        "velocidad_kmh": "25", "minutos_por_parada": "10",
        "hora_inicio": "09:00", "max_paradas_por_ruta": "9",
        "factor_trafico": "0.5",
    })
    assert float(ConfiguracionRutas.obtener().factor_trafico) == 1.0


def test_desmarcar_la_acera_la_apaga(client, usuario_factory):
    """Una casilla desmarcada no viaja en el POST: su ausencia ES el apagado."""
    from ajustes.models import ConfiguracionRutas

    _abrir(client, usuario_factory)
    cfg = ConfiguracionRutas.obtener()
    cfg.acera_del_cliente = True
    cfg.save()

    client.post("/ajustes/rutas/", {
        "velocidad_kmh": "25", "minutos_por_parada": "10",
        "hora_inicio": "09:00", "max_paradas_por_ruta": "9",
    })
    assert ConfiguracionRutas.obtener().acera_del_cliente is False


def test_sin_mapa_de_bici_la_pantalla_lo_advierte(client, usuario_factory,
                                                  monkeypatch):
    """Ofrecer bicicleta sin su mapa sería medir como coche sin que nadie se
    entere."""
    from lib import ruteo

    monkeypatch.setattr(ruteo, "BASE_URL_BICI", "")
    _abrir(client, usuario_factory)
    cuerpo = client.get("/ajustes/rutas/").content.decode()
    assert "todavía no está cargado" in cuerpo


def test_guardar_tira_el_recuerdo_de_las_opciones(client, usuario_factory):
    """Sin esto el cambio tardaría el minuto de la caché en notarse."""
    from lib import ruteo

    _abrir(client, usuario_factory)
    ruteo.opciones_vigentes()  # calienta la caché
    client.post("/ajustes/rutas/", {
        "velocidad_kmh": "25", "minutos_por_parada": "10",
        "hora_inicio": "09:00", "max_paradas_por_ruta": "9",
        "evitar": "motorway",
    })
    assert ruteo.opciones_vigentes().evitar == "motorway"
