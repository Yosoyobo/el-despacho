"""El botón «Generar» del campo Descripción (ticket 13 de Oscar, 2026-10-14).

Tres cosas que importan:

1. **La plantilla sólo escribe lo que se sabe.** Nada de medidas ni colores
   inventados: lo que falta se dice en `faltantes`, no se rellena.
2. **Nunca pisa lo escrito.** La vista PROPONE (no guarda) y `completar` conserva
   el texto de la persona.
3. **La IA es opcional y no manda.** Si falla, no hay permiso o mete una cifra
   que no está en los datos, se vuelve a la plantilla.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# ── La plantilla (pura) ──────────────────────────────────────────────────────

def _srv(desc=""):
    return SimpleNamespace(descripcion_default=desc, nombre="Gorra")


def test_el_formato_de_siempre_con_lo_que_se_sabe():
    from apps.cotizaciones import descripcion_sugerida as ds

    texto = ds.sugerir(
        cantidad=105, nombre="Gorra", servicio=_srv("Gorras de gabardina 100% algodón deslavado"),
        variacion=SimpleNamespace(nombre="Beige", descripcion="", impresion_activa=False,
                                  impresion_descripcion=""),
        impresion_proveedor=SimpleNamespace(
            subcategorias=SimpleNamespace(all=lambda: [SimpleNamespace(nombre="Bordado")])))

    assert texto.splitlines() == [
        "105 pz",
        "Gorras de gabardina 100% algodón deslavado",
        "Beige",
        "Color: Beige",
        "Con bordado",
    ]


def test_sin_catalogo_ni_variacion_usa_el_nombre_y_no_inventa_nada():
    from apps.cotizaciones import descripcion_sugerida as ds

    texto = ds.sugerir(cantidad=3, nombre="Taza mágica")

    assert texto == "3 pz\nTaza mágica"
    # Lo que no sabe, lo dice; no lo escribe.
    assert ds.faltantes(texto) == ["color", "medidas"]
    assert "Color" not in texto and "cm" not in texto


def test_la_cantidad_del_catalogo_no_manda_sobre_la_de_la_linea():
    from apps.cotizaciones import descripcion_sugerida as ds

    texto = ds.sugerir(cantidad=40, nombre="x", servicio=_srv("100 pz\nPlayera de algodón"))
    assert texto.splitlines() == ["40 pz", "Playera de algodón"]


def test_impresion_sin_tecnica_conocida_dice_impresion_y_trae_el_detalle():
    from apps.cotizaciones import descripcion_sugerida as ds

    texto = ds.sugerir(
        cantidad=25, nombre="Playera",
        variacion=SimpleNamespace(nombre="Talla M", descripcion="", impresion_activa=True,
                                  impresion_descripcion="serigrafía 7 x 4 con tintas de descarga"),
        impresion_proveedor=SimpleNamespace(subcategorias=SimpleNamespace(all=lambda: [])))

    assert "Con impresión" in texto.splitlines()
    assert "Serigrafía 7 x 4 con tintas de descarga" in texto.splitlines()
    assert ds.faltantes(texto) == ["color"]  # ya trae una medida (7 x 4)


def test_no_repite_renglones():
    from apps.cotizaciones import descripcion_sugerida as ds

    texto = ds.sugerir(
        cantidad=5, nombre="Gorra", servicio=_srv("Gorra roja"),
        variacion=SimpleNamespace(nombre="Gorra roja", descripcion="gorra  ROJA",
                                  impresion_activa=False, impresion_descripcion=""))
    assert texto.lower().count("gorra roja") == 1


def test_colores_con_acento_y_frases_largas():
    from apps.cotizaciones import descripcion_sugerida as ds

    assert ds._colores_en("Playera Azul Marino y café") == ["Azul Marino", "café"]
    assert ds._colores_en("Carroza de lujo") == []  # «rosa» no está en «carroza»


# ── No pisar lo escrito ──────────────────────────────────────────────────────

def test_completar_conserva_lo_escrito_y_suma_lo_que_falta():
    from apps.cotizaciones import descripcion_sugerida as ds

    mio = "105 pz (3 colores, 35 pz c/u)\nFrontal: Mantarraya - 4.5 cm"
    sugerida = "110 pz\nGorras de gabardina\nCon bordado\nFrontal: Mantarraya - 4.5 cm"

    resultado = ds.completar(mio, sugerida).splitlines()

    assert resultado[0] == "110 pz (3 colores, 35 pz c/u)"  # el número al día, lo demás intacto
    assert "Frontal: Mantarraya - 4.5 cm" in resultado
    assert resultado.count("Frontal: Mantarraya - 4.5 cm") == 1
    assert "Gorras de gabardina" in resultado and "Con bordado" in resultado


def test_completar_sin_renglon_de_piezas_lo_antepone():
    from apps.cotizaciones import descripcion_sugerida as ds

    assert ds.completar("Con bordado frontal", "8 pz\nCon bordado").splitlines() == [
        "8 pz", "Con bordado frontal"]


def test_las_cifras_inventadas_se_cazan():
    from apps.cotizaciones import descripcion_sugerida as ds

    datos = "105 pz\nGorra"
    assert ds.sin_cifras_inventadas("105 pz\nGorra de algodón", datos)
    assert not ds.sin_cifras_inventadas("105 pz\nGorra\nBordado de 5 cm", datos)
    assert ds.sin_cifras_inventadas("4,5 cm", "mide 4.5 cm")


# ── La vista ─────────────────────────────────────────────────────────────────

@pytest.fixture
def entorno(usuario_factory):
    from apps.el_catalogo.models import (
        CategoriaServicio,
        Proveedor,
        Servicio,
        SubcategoriaProveedor,
        Variacion,
    )

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(
        nombre="Gorra", precio_base="100", costo="30", categoria=cat,
        descripcion_default="Gorras de gabardina 100% algodón deslavado")
    var = Variacion.objects.create(servicio=srv, nombre="Beige · ajustable")
    prov = Proveedor.objects.create(razon_social="Bordados Mx")
    prov.subcategorias.add(SubcategoriaProveedor.objects.get(slug="bordado"))
    return {"admin": admin, "srv": srv, "var": var, "prov": prov}


def _post(client, entorno, **extra):
    datos = {"servicio": entorno["srv"].pk, "cantidad": 105, **extra}
    return client.post(reverse("proyectos-descripcion-sugerida"), datos)


def test_la_vista_propone_y_no_guarda_nada(client, entorno):
    from apps.los_proyectos.models import ProyectoProducto

    client.force_login(entorno["admin"])
    resp = _post(client, entorno, variacion=entorno["var"].pk,
                 impresion_proveedor=entorno["prov"].pk)

    d = resp.json()
    assert d["ok"] is True and d["origen"] == "plantilla"
    assert d["texto"].splitlines()[:2] == ["105 pz", "Gorras de gabardina 100% algodón deslavado"]
    assert "Color: Beige" in d["texto"]
    assert "Con bordado" in d["texto"]
    assert d["completado"] == ""  # no había nada escrito
    assert d["faltan"] == ["medidas"]
    assert ProyectoProducto.objects.count() == 0


def test_con_texto_previo_ofrece_completar_sin_tocarlo(client, entorno):
    client.force_login(entorno["admin"])
    previo = "105 pz (3 colores)\nFrontal: Mantarraya - 4.5 cm"

    d = _post(client, entorno, texto=previo, impresion_proveedor=entorno["prov"].pk).json()

    assert d["completado"].splitlines()[0] == "105 pz (3 colores)"
    assert "Frontal: Mantarraya - 4.5 cm" in d["completado"]
    assert "Con bordado" in d["completado"]
    assert "Frontal: Mantarraya" not in d["texto"]  # la propuesta pura no lo sabe


def test_sin_producto_dice_que_elija_uno(client, entorno):
    client.force_login(entorno["admin"])
    d = client.post(reverse("proyectos-descripcion-sugerida"), {"cantidad": 3}).json()
    assert d["ok"] is False and "producto" in d["error"].lower()


def test_ids_basura_no_tumban_la_vista(client, entorno):
    client.force_login(entorno["admin"])
    for malo in ("abc", "-1", "99999", "1;DROP"):
        resp = client.post(reverse("proyectos-descripcion-sugerida"), {
            "servicio": entorno["srv"].pk, "variacion": malo, "impresion_proveedor": malo,
            "cantidad": malo})
        assert resp.status_code == 200, malo
        assert resp.json()["ok"] is True, malo


def test_una_variacion_de_otro_producto_se_ignora(client, entorno):
    from apps.el_catalogo.models import Servicio, Variacion

    otro = Servicio.objects.create(nombre="Taza", precio_base="1", categoria=entorno["srv"].categoria)
    ajena = Variacion.objects.create(servicio=otro, nombre="Verde limón")
    client.force_login(entorno["admin"])

    d = _post(client, entorno, variacion=ajena.pk).json()

    assert "Verde" not in d["texto"]


def test_sin_permiso_de_proyectos_es_403(client, usuario_factory, entorno):
    from cuentas.models import PermisoUsuario

    u = usuario_factory(rol="disenador")
    for accion in ("editar", "crear"):
        PermisoUsuario.objects.update_or_create(
            usuario=u, modulo="proyectos", permiso=accion, defaults={"activo": False})
    client.force_login(u)

    assert _post(client, entorno).status_code == 403


def test_solo_post(client, entorno):
    client.force_login(entorno["admin"])
    assert client.get(reverse("proyectos-descripcion-sugerida")).status_code == 405


# ── El camino con IA (Los Analistas) ─────────────────────────────────────────

def _ia(monkeypatch, resultado):
    import lib.redactor_ia as r

    llamadas = []

    def falso(**kw):
        llamadas.append(kw)
        return resultado
    monkeypatch.setattr(r, "redactar", falso)
    return llamadas


def test_con_ia_se_usa_la_redaccion_si_no_inventa_cifras(client, entorno, monkeypatch):
    llamadas = _ia(monkeypatch, {"ok": True, "error": "",
                                 "texto": "105 pz\nGorras de gabardina 100% algodón deslavado"})
    client.force_login(entorno["admin"])

    d = _post(client, entorno, ia="1").json()

    assert d["origen"] == "chalan"
    assert d["texto"].startswith("105 pz")
    assert llamadas and llamadas[0]["estacion"] == "cotizaciones"
    # La plantilla viaja como contexto: la IA redacta sobre datos, no de memoria.
    assert "105 pz" in str(llamadas[0]["contexto"])


def test_con_ia_una_cifra_inventada_vuelve_a_la_plantilla(client, entorno, monkeypatch):
    _ia(monkeypatch, {"ok": True, "error": "",
                      "texto": "105 pz\nGorras\nBordado frontal de 9 cm de ancho"})
    client.force_login(entorno["admin"])

    d = _post(client, entorno, ia="1").json()

    assert d["origen"] == "plantilla"
    assert "9 cm" not in d["texto"]
    assert "no están en el sistema" in d["aviso"]


def test_con_ia_sin_credenciales_degrada_a_la_plantilla(client, entorno, monkeypatch):
    _ia(monkeypatch, {"ok": False, "texto": "", "error": "El Chalán no respondió: sin credenciales"})
    client.force_login(entorno["admin"])

    d = _post(client, entorno, ia="1").json()

    assert d["ok"] is True and d["origen"] == "plantilla"
    assert "sin credenciales" in d["aviso"]
    assert d["texto"].startswith("105 pz")


def test_sin_permiso_de_chalan_no_se_llama_a_la_ia(client, entorno, usuario_factory, monkeypatch):
    from cuentas.models import PermisoUsuario

    llamadas = _ia(monkeypatch, {"ok": True, "texto": "x", "error": ""})
    u = usuario_factory(rol="dueno")
    PermisoUsuario.objects.update_or_create(
        usuario=u, modulo="chalan", permiso="usar", defaults={"activo": False})
    client.force_login(u)

    d = _post(client, entorno, ia="1").json()

    assert llamadas == []
    assert d["origen"] == "plantilla"


# ── La tarjeta ───────────────────────────────────────────────────────────────

def test_la_tarjeta_del_proyecto_trae_el_boton_generar(client, entorno, proyecto_factory):
    client.force_login(entorno["admin"])
    p = proyecto_factory(nombre="Con tarjeta", creado_por=entorno["admin"])

    html = client.get(reverse("proyectos-detalle", args=[p.pk])).content.decode()

    assert "data-desc-generar" in html
    assert "✨ Generar" in html
    assert reverse("proyectos-descripcion-sugerida") in html
