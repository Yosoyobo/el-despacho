"""El pin del mapa de un proveedor sigue a su dirección (deuda Sep28).

Cambiar la dirección —en la ficha o por El Chalán— sin mover el pin lo dejaba en
el lugar viejo. Ahora se reubica en el fondo, tras el commit, con el buscador
simulado aquí (Nominatim no existe en las pruebas). Lo que se fija:

- se mueve cuando el pin venía del buscador;
- NO se pisa un pin puesto a mano (no coincide con la dirección anterior);
- si el buscador no contesta, el pin se queda y la ficha lo dice;
- si en el mismo guardado la persona movió el pin, manda lo suyo;
- la ficha que quedó abierta no choca con el pin que se movió en el fondo.
"""

from __future__ import annotations

import pytest
from django.test import Client

from tests.taller.test_edicion_pisada_sep28 import _abrir, _con

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

VIEJA = "Av. Insurgentes Sur 100, CDMX"
NUEVA = "Calle Durango 250, Roma Norte, CDMX"
PUNTO_VIEJO = (19.4200, -99.1600)
PUNTO_NUEVO = (19.4180, -99.1650)


@pytest.fixture
def buscador(monkeypatch):
    """Nominatim de mentiras: dirección → punto. `caido=True` no contesta nada."""
    from lib import geocoding

    estado = {"caido": False, "pedidas": [], "puntos": {VIEJA: PUNTO_VIEJO, NUEVA: PUNTO_NUEVO}}

    def _primer(texto):
        estado["pedidas"].append(texto)
        if estado["caido"]:
            return None
        p = estado["puntos"].get(texto)
        return {"nombre": texto, "direccion": texto, "lat": p[0], "lng": p[1]} if p else None

    monkeypatch.setattr(geocoding, "primer_resultado", _primer)
    return estado


@pytest.fixture(autouse=True)
def _commit_inmediato(monkeypatch):
    """§14 Bug E: con el fixture `db` el commit no llega; aquí corre en el acto."""
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def jefe(usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.fixture
def navegador(jefe):
    c = Client()
    c.force_login(jefe)
    return c


def _proveedor(*, direccion=VIEJA, pin=PUNTO_VIEJO):
    from apps.el_catalogo.models import Proveedor

    lat, lng = pin if pin else (None, None)
    return Proveedor.objects.create(razon_social="Bordados del Centro", direccion=direccion,
                                    lat=lat, lng=lng, activo=True)


def _pin(prov):
    prov.refresh_from_db()
    return (prov.lat, prov.lng)


def _ficha(prov):
    return f"/catalogo/proveedores/{prov.pk}/"


def _guardar_direccion(navegador, prov, direccion=NUEVA, **mas):
    datos = _abrir(navegador, _ficha(prov))
    return navegador.post(_ficha(prov), _con(datos, direccion=direccion, **mas))


# ── Desde la ficha ─────────────────────────────────────────────────────────


def test_el_pin_del_buscador_se_mueve_con_la_direccion(navegador, buscador):
    prov = _proveedor()
    r = _guardar_direccion(navegador, prov)
    assert r.status_code == 302
    assert _pin(prov) == PUNTO_NUEVO
    assert buscador["pedidas"] == [VIEJA, NUEVA]


def test_sin_pin_previo_se_ubica_la_nueva(navegador, buscador):
    prov = _proveedor(pin=None)
    _guardar_direccion(navegador, prov)
    assert _pin(prov) == PUNTO_NUEVO


def test_un_pin_puesto_a_mano_no_se_pisa_y_se_dice(navegador, buscador):
    """El pin está a ~1 km de donde el buscador pone la dirección vieja: alguien
    lo arrastró a la puerta de la bodega. No se toca, y la ficha lo avisa."""
    prov = _proveedor(pin=(19.4290, -99.1600))
    _guardar_direccion(navegador, prov)
    assert _pin(prov) == (19.4290, -99.1600)
    html = navegador.get(_ficha(prov)).content.decode()
    assert "parece puesto a mano" in html


def test_buscador_caido_deja_el_pin_y_lo_avisa(navegador, buscador):
    buscador["caido"] = True
    prov = _proveedor(pin=None)
    r = _guardar_direccion(navegador, prov)
    assert r.status_code == 302, "el guardado no depende del buscador"
    prov.refresh_from_db()
    assert prov.direccion == NUEVA and prov.lat is None
    html = navegador.get(_ficha(prov)).content.decode()
    assert "No se pudo ubicar la dirección nueva" in html
    # El aviso se dice una vez, no para siempre.
    assert "No se pudo ubicar" not in navegador.get(_ficha(prov)).content.decode()


def test_si_la_persona_movio_el_pin_manda_lo_suyo(navegador, buscador):
    prov = _proveedor()
    _guardar_direccion(navegador, prov, lat="19.5", lng="-99.2")
    assert _pin(prov) == (19.5, -99.2)
    assert buscador["pedidas"] == [], "no se pregunta al buscador si ya hay pin nuevo"


def test_sin_cambiar_la_direccion_no_se_pregunta_nada(navegador, buscador):
    prov = _proveedor()
    datos = _abrir(navegador, _ficha(prov))
    navegador.post(_ficha(prov), _con(datos, telefono="555 000 1111"))
    assert buscador["pedidas"] == []
    assert _pin(prov) == PUNTO_VIEJO


def test_el_autoguardado_dice_que_el_pin_se_acomoda(navegador, buscador):  # noqa: ARG001
    prov = _proveedor()
    datos = _abrir(navegador, _ficha(prov))
    r = navegador.post(_ficha(prov), _con(datos, direccion=NUEVA), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "el pin del mapa se acomoda" in r.content.decode()


def test_la_ficha_abierta_no_choca_con_el_pin_que_se_movio(navegador, buscador):  # noqa: ARG001
    """Autoguardado 1 cambia la dirección y el pin se mueve en el fondo. La misma
    pantalla (con el pin viejo en sus campos ocultos) guarda otra cosa: no hay
    aviso de choque y el pin nuevo NO se regresa al viejo."""
    prov = _proveedor()
    datos = _abrir(navegador, _ficha(prov))
    r1 = navegador.post(_ficha(prov), _con(datos, direccion=NUEVA), HTTP_HX_REQUEST="true")
    assert r1.status_code == 200
    assert _pin(prov) == PUNTO_NUEVO

    # El testigo nuevo llega por OOB; los ocultos del pin se quedaron como estaban.
    from tests.taller.test_edicion_pisada_sep28 import _sueltos
    testigo = _sueltos(r1.content.decode())["_edicion_testigo"]
    r2 = navegador.post(_ficha(prov), _con(datos, direccion=NUEVA, telefono="555 222 3333",
                                           _edicion_testigo=testigo[0]),
                        HTTP_HX_REQUEST="true")
    assert r2.status_code == 200, r2.content.decode()[:300]
    prov.refresh_from_db()
    assert prov.telefono == "555 222 3333"
    assert (prov.lat, prov.lng) == PUNTO_NUEVO


def test_lo_que_cambio_despues_no_se_pisa(buscador):  # noqa: ARG001
    """Si mientras el buscador contestaba alguien fijó el pin, gana ese."""
    from apps.el_catalogo import ubicacion

    prov = _proveedor(direccion=NUEVA)
    prov.lat, prov.lng = 19.6, -99.3
    prov.save(update_fields=["lat", "lng"])
    assert ubicacion.recalcular(prov.pk, VIEJA, NUEVA, *PUNTO_VIEJO) == "cambio_despues"
    assert _pin(prov) == (19.6, -99.3)


# ── Desde El Chalán ────────────────────────────────────────────────────────


def _chalan(usuario, payload):
    from types import SimpleNamespace

    from apps.el_dictado.ejecutores import EJECUTORES

    accion = SimpleNamespace(payload=payload)
    EJECUTORES["actualizar_proveedor"](accion, usuario, {})
    return accion


def test_el_chalan_tambien_mueve_el_pin(jefe, buscador):  # noqa: ARG001
    prov = _proveedor()
    _chalan(jefe, {"proveedor": "Bordados del Centro", "direccion": NUEVA})
    prov.refresh_from_db()
    assert prov.direccion == NUEVA
    assert (prov.lat, prov.lng) == PUNTO_NUEVO


def test_el_chalan_con_buscador_caido_guarda_igual(jefe, buscador):
    buscador["caido"] = True
    prov = _proveedor()
    _chalan(jefe, {"proveedor": "Bordados del Centro", "direccion": NUEVA})
    prov.refresh_from_db()
    assert prov.direccion == NUEVA
    assert (prov.lat, prov.lng) == PUNTO_VIEJO


def test_el_chalan_no_pisa_un_pin_a_mano(jefe, buscador):  # noqa: ARG001
    prov = _proveedor(pin=(19.4290, -99.1600))
    _chalan(jefe, {"proveedor": "Bordados del Centro", "direccion": NUEVA})
    assert _pin(prov) == (19.4290, -99.1600)


def test_un_buscador_que_revienta_no_tumba_el_guardado(navegador, monkeypatch):
    from lib import geocoding

    def _revienta(texto):
        raise RuntimeError("Nominatim devolvió basura")

    monkeypatch.setattr(geocoding, "primer_resultado", _revienta)
    prov = _proveedor(pin=None)
    assert _guardar_direccion(navegador, prov).status_code == 302
    prov.refresh_from_db()
    assert prov.direccion == NUEVA and prov.lat is None
