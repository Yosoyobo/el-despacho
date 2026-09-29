"""El pin del proveedor al dar de alta (deuda Sep28, segunda parte).

La primera parte (`test_proveedor_pin_sigue_direccion.py`) movía el pin al
CAMBIAR la dirección. Faltaban dos cosas:

1. **El alta.** Un proveedor nuevo con dirección nacía sin pin: pantalla de
   alta, alta rápida (ficha de producto, gasto desde un CFDI) y El Chalán. Ahora
   se ubica solo, con la misma pieza (en el fondo, no pisa un pin que el alta ya
   traiga, avisa si no encuentra la dirección).
2. **La ficha abierta.** El dato quedaba bien, pero el marcador no se movía
   hasta recargar. Ahora la ficha pregunta (sondeo corto que se apaga solo) y,
   al terminar, recibe el pin nuevo y el testigo con la huella del pin al día:
   arrastrar el pin después no sale como «choque» con alguien más.

El buscador está simulado (Nominatim no existe en las pruebas).
"""

from __future__ import annotations

import pytest
from django.test import Client

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

DIRECCION = "Calle Durango 250, Roma Norte, CDMX"
PUNTO = (19.4180, -99.1650)
VIEJA = "Av. Insurgentes Sur 100, CDMX"
PUNTO_VIEJO = (19.4200, -99.1600)


@pytest.fixture
def buscador(monkeypatch):
    """Nominatim de mentiras. `caido=True` no contesta nada."""
    from lib import geocoding

    estado = {"caido": False, "pedidas": [], "puntos": {DIRECCION: PUNTO, VIEJA: PUNTO_VIEJO}}

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


def _ultimo():
    from apps.el_catalogo.models import Proveedor

    return Proveedor.objects.order_by("-pk").first()


def _pin(prov):
    prov.refresh_from_db()
    return (prov.lat, prov.lng)


def _ficha(prov):
    return f"/catalogo/proveedores/{prov.pk}/"


def _url_pin(prov):
    return f"/catalogo/proveedores/{prov.pk}/pin/"


# ── 1. El alta ────────────────────────────────────────────────────────────


def _alta(navegador, **mas):
    datos = {"razon_social": "Bordados del Centro", "direccion": DIRECCION,
             "direccion_fiscal": "", "lat": "", "lng": "", "activo": "on"}
    datos.update(mas)
    return navegador.post("/catalogo/proveedores/nuevo", datos)


def test_alta_con_direccion_ubica_el_pin(navegador, buscador):
    r = _alta(navegador)
    assert r.status_code == 302
    prov = _ultimo()
    assert _pin(prov) == PUNTO
    assert buscador["pedidas"] == [DIRECCION], "sin pin previo no hay nada que cuidar"
    html = navegador.get(_ficha(prov)).content.decode()
    assert "se ubica solo con su dirección" in html


def test_alta_con_pin_explicito_no_se_pisa(navegador, buscador):
    """Eligió una sugerencia del buscador en la pantalla de alta: manda ése."""
    _alta(navegador, lat="19.5", lng="-99.2")
    assert _pin(_ultimo()) == (19.5, -99.2)
    assert buscador["pedidas"] == []


def test_alta_sin_direccion_no_pregunta(navegador, buscador):
    _alta(navegador, direccion="")
    prov = _ultimo()
    assert _pin(prov) == (None, None)
    assert buscador["pedidas"] == []


def test_alta_con_buscador_caido_guarda_y_avisa(navegador, buscador):
    buscador["caido"] = True
    assert _alta(navegador).status_code == 302, "el alta no depende del buscador"
    prov = _ultimo()
    assert prov.direccion == DIRECCION and prov.lat is None
    assert "No se pudo ubicar la dirección nueva" in navegador.get(_ficha(prov)).content.decode()


def test_alta_rapida_con_direccion_ubica_el_pin(navegador, buscador):
    """Ficha de producto «+ Nuevo proveedor» y gasto desde un CFDI: el mismo endpoint."""
    r = navegador.post("/catalogo/proveedores/quick-create/", {
        "razon_social": "Telas del Norte", "rfc": "TNO010101AAA", "direccion": DIRECCION})
    assert r.status_code == 200
    datos = r.json()
    assert datos["ok"] and datos["pin_programado"] is True
    prov = _ultimo()
    assert prov.direccion == DIRECCION
    assert _pin(prov) == PUNTO


def test_alta_rapida_sin_direccion_no_pregunta(navegador, buscador):
    r = navegador.post("/catalogo/proveedores/quick-create/", {"razon_social": "Telas del Norte"})
    assert r.json()["pin_programado"] is False
    assert buscador["pedidas"] == []


def test_alta_rapida_buscador_caido_crea_igual(navegador, buscador):
    buscador["caido"] = True
    r = navegador.post("/catalogo/proveedores/quick-create/", {
        "razon_social": "Telas del Norte", "direccion": DIRECCION})
    assert r.status_code == 200 and r.json()["ok"]
    prov = _ultimo()
    assert prov.direccion == DIRECCION and prov.lat is None


@pytest.mark.parametrize("plantilla", [
    "catalogo/form.html", "catalogo/_modal_nuevo_producto.html",
    "tesoreria/_modal_nuevo_egreso.html", "tesoreria/egreso_form.html",
])
def test_las_altas_rapidas_mandan_la_direccion(plantilla):
    """Las cuatro altas rápidas piden la dirección y la mandan al endpoint."""
    from pathlib import Path

    texto = (Path(__file__).resolve().parents[2] / "el-taller" / "templates" / plantilla).read_text()
    assert 'id="prov-direccion"' in texto
    # El valor viaja en el cuerpo del POST (FormData o URLSearchParams).
    assert ("body.append('direccion'" in texto) or ('direccion: (' in texto), plantilla


def _chalan_crear(usuario, payload):
    from types import SimpleNamespace

    from apps.el_dictado.ejecutores import EJECUTORES

    accion = SimpleNamespace(payload=payload)
    EJECUTORES["crear_proveedor"](accion, usuario, {})
    return accion


def test_el_chalan_da_de_alta_con_pin(jefe, buscador):  # noqa: ARG001
    accion = _chalan_crear(jefe, {"razon_social": "Maracas Don José", "direccion": DIRECCION})
    from apps.el_catalogo.models import Proveedor

    prov = Proveedor.objects.get(pk=accion.entidad_id)
    assert _pin(prov) == PUNTO


def test_el_chalan_con_buscador_caido_da_de_alta_igual(jefe, buscador):
    buscador["caido"] = True
    accion = _chalan_crear(jefe, {"razon_social": "Maracas Don José", "direccion": DIRECCION})
    from apps.el_catalogo.models import Proveedor

    prov = Proveedor.objects.get(pk=accion.entidad_id)
    assert prov.direccion == DIRECCION and prov.lat is None
