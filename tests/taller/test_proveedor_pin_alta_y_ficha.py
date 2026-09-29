"""El pin del proveedor: el alta y la ficha abierta (deuda Sep28, segunda parte).

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

import json

import pytest
from django.test import Client

from tests.taller.test_edicion_pisada_sep28 import _abrir, _con, _sueltos

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

DIRECCION = "Calle Durango 250, Roma Norte, CDMX"
PUNTO = (19.4180, -99.1650)
VIEJA = "Av. Insurgentes Sur 100, CDMX"
PUNTO_VIEJO = (19.4200, -99.1600)
HTMX = {"HTTP_HX_REQUEST": "true"}
AVISO_CHOQUE = "alguien más"


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
def fondo_despues(monkeypatch):
    """Como en producción: el fondo termina DESPUÉS de que la respuesta del
    autoguardado salió (con su testigo aún con el pin viejo). `correr()` lo suelta."""
    from lib import tareas_fondo

    cola = []
    monkeypatch.setattr(tareas_fondo, "ejecutar_en_fondo",
                        lambda fn, *a, **kw: cola.append((fn, a, kw)))

    def correr():
        while cola:
            fn, a, kw = cola.pop(0)
            fn(*a, **kw)

    return correr


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
    """Las altas rápidas piden la dirección y la mandan al endpoint."""
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


# ── 2. La ficha abierta se entera ─────────────────────────────────────────


def _proveedor(*, direccion=VIEJA, pin=PUNTO_VIEJO):
    from apps.el_catalogo.models import Proveedor

    lat, lng = pin if pin else (None, None)
    return Proveedor.objects.create(razon_social="Bordados del Centro", direccion=direccion,
                                    lat=lat, lng=lng, activo=True)


def _sondeo_activo(html: str, prov) -> bool:
    import re

    etiqueta = re.search(r'<div id="prov-pin-vigia"[^>]*>', html)
    return bool(etiqueta) and 'hx-trigger="every' in etiqueta.group(0) \
        and _url_pin(prov) in etiqueta.group(0)


def test_la_ficha_pregunta_mientras_el_pin_esta_pendiente(navegador):
    from apps.el_catalogo import ubicacion

    prov = _proveedor()
    assert not _sondeo_activo(navegador.get(_ficha(prov)).content.decode(), prov)
    ubicacion._poner_estado(prov.pk, {"estado": ubicacion.PENDIENTE}, 60)
    assert _sondeo_activo(navegador.get(_ficha(prov)).content.decode(), prov)


def test_el_sondeo_sigue_con_204_y_para_con_286(navegador, buscador):  # noqa: ARG001
    from apps.el_catalogo import ubicacion

    prov = _proveedor()
    ubicacion._poner_estado(prov.pk, {"estado": ubicacion.PENDIENTE}, 60)
    r = navegador.get(_url_pin(prov), **HTMX)
    assert r.status_code == 204, "pendiente: no pinta nada y htmx vuelve a preguntar"
    ubicacion._poner_estado(prov.pk, {"estado": "cambio_despues"}, 60)
    r = navegador.get(_url_pin(prov), **HTMX)
    assert r.status_code == 286, "terminado: htmx deja de sondear"
    assert 'hx-trigger' not in r.content.decode(), "el reemplazo ya no sondea"
    assert "HX-Trigger" not in r.headers


def test_sin_estado_el_sondeo_se_apaga(navegador):
    """Si el estado venció (el hilo murió sin avisar), el sondeo no sigue para siempre."""
    prov = _proveedor()
    assert navegador.get(_url_pin(prov), **HTMX).status_code == 286


def test_el_autoguardado_que_cambia_la_direccion_prende_el_sondeo(navegador, buscador):  # noqa: ARG001
    prov = _proveedor()
    datos = _abrir(navegador, _ficha(prov))
    r = navegador.post(_ficha(prov), _con(datos, direccion=DIRECCION), **HTMX)
    assert r.status_code == 200
    assert _sondeo_activo(r.content.decode(), prov)
    assert 'id="prov-pin-vigia" class="text-xs empty:hidden" hx-swap-oob="true"' in r.content.decode()


def test_otro_autoguardado_no_prende_el_sondeo(navegador, buscador):  # noqa: ARG001
    prov = _proveedor()
    datos = _abrir(navegador, _ficha(prov))
    r = navegador.post(_ficha(prov), _con(datos, telefono="555 000 1111"), **HTMX)
    assert r.status_code == 200
    assert "prov-pin-vigia" not in r.content.decode()


def _evento(resp) -> dict:
    return json.loads(resp.headers["HX-Trigger"])["proveedor-pin"]


def test_la_ficha_recibe_el_pin_nuevo_y_el_testigo_al_dia(navegador, buscador, fondo_despues):  # noqa: ARG001
    """La ventana abierta: guarda la dirección, el pin se mueve en el fondo, el
    sondeo le trae el pin nuevo (para el marcador) y el testigo al día. Si luego
    la persona ARRASTRA el pin, se guarda sin «choque»."""
    prov = _proveedor()
    datos = _abrir(navegador, _ficha(prov))
    r1 = navegador.post(_ficha(prov), _con(datos, direccion=DIRECCION), **HTMX)
    testigo = _sueltos(r1.content.decode())["_edicion_testigo"][0]
    assert _pin(prov) == PUNTO_VIEJO
    assert navegador.get(_url_pin(prov), **HTMX).status_code == 204, "sigue en eso"
    fondo_despues()
    assert _pin(prov) == PUNTO

    r = navegador.get(_url_pin(prov), {"_edicion_testigo": testigo}, **HTMX)
    assert r.status_code == 286
    ev = _evento(r)
    assert ev["de"] == list(PUNTO_VIEJO) and ev["a"] == list(PUNTO)
    assert ev["testigo"], "el testigo tenía el pin viejo: vuelve con la huella nueva"
    assert "se acomodó" in r.content.decode()

    # Sólo cambió la huella del pin; lo demás quedó como llegó.
    viejo, nuevo = json.loads(testigo), json.loads(ev["testigo"])
    assert {k for k in viejo["f"] if viejo["f"][k] != nuevo["f"][k]} == {"lat", "lng"}
    assert viejo["w"] == nuevo["w"] and viejo["t"] == nuevo["t"]

    # Lo que hace el JS: ocultos al pin nuevo y testigo al día. Luego arrastra.
    r2 = navegador.post(_ficha(prov), _con(datos, direccion=DIRECCION, lat="19.43", lng="-99.17",
                                           _edicion_testigo=ev["testigo"]), **HTMX)
    assert r2.status_code == 200, r2.content.decode()[:300]
    assert AVISO_CHOQUE not in r2.content.decode()
    assert _pin(prov) == (19.43, -99.17)


def test_sin_el_testigo_al_dia_arrastrar_chocaria(navegador, buscador, fondo_despues):  # noqa: ARG001
    """El contraste: con el testigo de antes del recálculo, arrastrar el pin se
    toma por pisar a alguien. Por eso el sondeo lo trae al día."""
    prov = _proveedor()
    datos = _abrir(navegador, _ficha(prov))
    r1 = navegador.post(_ficha(prov), _con(datos, direccion=DIRECCION), **HTMX)
    testigo = _sueltos(r1.content.decode())["_edicion_testigo"][0]
    fondo_despues()
    r2 = navegador.post(_ficha(prov), _con(datos, direccion=DIRECCION, lat="19.43", lng="-99.17",
                                           _edicion_testigo=testigo), **HTMX)
    assert r2.status_code == 409


def test_el_testigo_no_se_toca_si_ya_traia_otro_pin(navegador):
    """Una ventana abierta con un pin que NO es el que se reemplazó: su huella
    no se «arregla» — ese cambio sí es de alguien más."""
    from apps.el_catalogo import ubicacion

    prov = _proveedor(pin=(19.5, -99.2))
    datos = _abrir(navegador, _ficha(prov))
    testigo = datos["_edicion_testigo"][0]
    # El recálculo movió el pin de PUNTO_VIEJO (no de 19.5) a PUNTO.
    prov.lat, prov.lng = PUNTO
    prov.save(update_fields=["lat", "lng"])
    assert ubicacion.testigo_al_dia(testigo, prov, list(PUNTO_VIEJO)) == ""
    ubicacion._poner_estado(prov.pk, {"estado": "movido", "de": list(PUNTO_VIEJO),
                                      "a": list(PUNTO)}, 60)
    assert _evento(navegador.get(_url_pin(prov), {"_edicion_testigo": testigo}, **HTMX))[
        "testigo"] == ""


def test_si_el_pin_cambio_despues_no_se_manda_el_evento(navegador):
    from apps.el_catalogo import ubicacion

    prov = _proveedor(pin=(19.6, -99.3))
    ubicacion._poner_estado(prov.pk, {"estado": "movido", "de": list(PUNTO_VIEJO),
                                      "a": list(PUNTO)}, 60)
    r = navegador.get(_url_pin(prov), **HTMX)
    assert r.status_code == 286
    assert "HX-Trigger" not in r.headers, "el pin ya es otro: el marcador no se mueve"


def test_el_sondeo_dice_el_aviso_y_la_ficha_no_lo_repite(navegador, buscador):
    buscador["caido"] = True
    prov = _proveedor(pin=None)
    datos = _abrir(navegador, _ficha(prov))
    navegador.post(_ficha(prov), _con(datos, direccion=DIRECCION), **HTMX)
    r = navegador.get(_url_pin(prov), **HTMX)
    assert r.status_code == 286
    assert "No se pudo ubicar la dirección nueva" in r.content.decode()
    assert "No se pudo ubicar" not in navegador.get(_ficha(prov)).content.decode()


def test_un_buscador_que_revienta_tambien_apaga_el_sondeo_y_avisa(navegador, monkeypatch):
    from lib import geocoding

    def _revienta(texto):
        raise RuntimeError("Nominatim devolvió basura")

    monkeypatch.setattr(geocoding, "primer_resultado", _revienta)
    prov = _proveedor(pin=None)
    datos = _abrir(navegador, _ficha(prov))
    assert navegador.post(_ficha(prov), _con(datos, direccion=DIRECCION), **HTMX).status_code == 200
    r = navegador.get(_url_pin(prov), **HTMX)
    assert r.status_code == 286
    assert "No se pudo ubicar la dirección nueva" in r.content.decode()


def test_el_sondeo_pide_permiso_de_editar(usuario_factory):
    prov = _proveedor()
    c = Client()
    c.force_login(usuario_factory(rol="disenador"))
    assert c.get(_url_pin(prov), **HTMX).status_code == 403
    assert "prov-pin-vigia" not in c.get(_ficha(prov)).content.decode()


def test_el_sondeo_no_cuenta_como_actividad():
    from lib import presencia

    assert "catalogo-proveedor-pin" in presencia.URL_NAMES_SONDEO


def test_geo_picker_fija_sin_autoguardar_en_las_dos_apps():
    """`geo:fijar` mueve el pin sin disparar input/change (no autoguarda).
    Dual-copy §18: idéntico en El Taller y La Gerencia."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    taller = (raiz / "el-taller/static/js/geo_picker.js").read_text()
    gerencia = (raiz / "la-gerencia/static/js/geo_picker.js").read_text()
    assert taller == gerencia
    cuerpo = taller.split("function fijar(lat, lng) {", 1)[1].split("\n    }\n", 1)[0]
    assert "dispatchEvent" not in cuerpo, "fijar no debe avisar al formulario"
    assert 'addEventListener("geo:fijar"' in taller


def test_si_el_buscador_revienta_la_ficha_lo_avisa_al_abrir(navegador, monkeypatch):
    """Sin ficha abierta que pregunte: el aviso queda para la siguiente vez que se abre."""
    from lib import geocoding

    def _revienta(texto):
        raise RuntimeError("Nominatim devolvió basura")

    monkeypatch.setattr(geocoding, "primer_resultado", _revienta)
    assert _alta(navegador).status_code == 302
    assert "No se pudo ubicar la dirección nueva" in navegador.get(
        _ficha(_ultimo())).content.decode()


# ── Las altas rápidas del proyecto (gasto y «Agregar proveedor») ──────────

_MODALES_PROYECTO = {
    # plantilla: (id del campo, cómo lo manda el JS)
    "proyectos/_modal_registrar_gasto.html": (
        "rg-nuevo-direccion",
        "body.append('direccion', ((slot.querySelector('#rg-nuevo-direccion')"),
    "proyectos/_modal_agregar_proveedor.html": (
        "pv-direccion", "body.append('direccion', direccion ? direccion.value"),
}


@pytest.mark.parametrize("plantilla", sorted(_MODALES_PROYECTO))
def test_las_altas_rapidas_del_proyecto_mandan_la_direccion(plantilla):
    from pathlib import Path

    campo, envio = _MODALES_PROYECTO[plantilla]
    texto = (Path(__file__).resolve().parents[2] / "el-taller" / "templates" / plantilla).read_text()
    assert f'id="{campo}"' in texto, "el modal no pide la dirección"
    assert envio in texto, "el modal no manda la dirección al alta rápida"


def _modal_pinta_el_campo(navegador, url, campo):
    r = navegador.get(url, HTTP_HX_REQUEST="true")
    assert r.status_code == 200, (url, r.status_code)
    return f'id="{campo}"' in r.content.decode()


def test_los_modales_del_proyecto_pintan_la_direccion(navegador, proyecto_factory):
    """Renderizados de verdad: los dos modales traen el campo nuevo."""
    from django.template.loader import render_to_string
    from django.test import RequestFactory
    from django.urls import reverse

    p = proyecto_factory()
    assert _modal_pinta_el_campo(navegador, reverse("proyectos-agregar-proveedor", args=[p.pk]),
                                 "pv-direccion")
    # El de gasto sale de una unidad pendiente; se pinta con el contexto real de
    # la vista y un gasto SIN proveedor (el único caso con alta rápida).
    from apps.los_proyectos.views import _ctx_modal_pago

    ctx = _ctx_modal_pago(p, info={"monto": 100, "label": "1 concepto", "proveedor": None},
                          accion_url="/x")
    html = render_to_string("proyectos/_modal_registrar_gasto.html", ctx,
                            request=RequestFactory().get("/"))
    assert 'id="rg-nuevo-direccion"' in html


@pytest.mark.parametrize("origen", ["gasto del proyecto", "agregar proveedor al proyecto"])
def test_el_alta_rapida_del_proyecto_programa_el_pin(navegador, buscador, origen):  # noqa: ARG001
    """Lo que mandan los dos modales del proyecto (mismos campos que su JS)."""
    campos = {"razon_social": "Imprenta Morelos", "nombre_contacto": "Luis",
              "telefono": "555 000 1111", "direccion": DIRECCION}
    if origen == "gasto del proyecto":
        campos["email_contacto"] = "luis@morelos.mx"
    r = navegador.post("/catalogo/proveedores/quick-create/", campos)
    assert r.status_code == 200 and r.json()["pin_programado"] is True
    assert _pin(_ultimo()) == PUNTO
