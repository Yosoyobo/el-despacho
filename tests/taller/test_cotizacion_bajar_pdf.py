"""«Generar y bajar PDF» y «Atrás» en la vista previa (tickets 10 y 14 de Oscar,
2026-10-14).

Un solo servicio para los dos puntos: la vista previa y el recuadro del proyecto
mandan el MISMO POST (`proyectos-generar-cotizacion`) con `y_pdf`. La versión se
confirma primero; el detalle del proyecto pide el PDF al cargar (`?bajar_cot=`)
con su estado de carga y su error legible.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def entorno(usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(
        nombre="Taza", precio_base="100", costo="30", categoria=cat)
    p = proyecto_factory(nombre="Branding Optimist", creado_por=admin)
    ProyectoProducto.objects.create(
        proyecto=p, servicio=srv, cantidad=3, incluir_en_calculo=True)
    return {"admin": admin, "p": p}


def test_la_barra_del_preview_ofrece_atras_y_generar_y_bajar_pdf(client, entorno):
    """«Atrás» sale sin generar nada; «Generar y bajar PDF» va junto a «Generar»
    con el mismo POST + la bandera `y_pdf`."""
    from apps.cotizaciones.models import Cotizacion

    client.force_login(entorno["admin"])

    html = client.get(
        reverse("proyectos-previsualizar-cotizacion", args=[entorno["p"].pk]),
    ).content.decode()

    assert "Generar y bajar PDF" in html
    assert 'name="y_pdf" value="1"' in html
    # «Atrás» es un enlace al detalle del proyecto, no un formulario: no genera.
    destino = reverse("proyectos-detalle", args=[entorno["p"].pk])
    assert f'id="lc-atras" href="{destino}"' in html
    # Y verlo no dejó rastro (el preview se deshace).
    assert not Cotizacion.objects.filter(proyecto=entorno["p"]).exists()


def test_generar_y_bajar_pdf_genera_y_lleva_a_la_descarga(client, entorno):
    """Se confirma la versión y se vuelve al detalle con la orden de bajar su
    PDF. Desde el recuadro (htmx) es un 204 + HX-Redirect."""
    from apps.cotizaciones.models import Cotizacion

    client.force_login(entorno["admin"])
    url = reverse("proyectos-generar-cotizacion", args=[entorno["p"].pk])

    resp = client.post(url, {"y_pdf": "1"})
    cot = Cotizacion.objects.get(proyecto=entorno["p"], version=1)
    assert resp.status_code == 302
    assert f"bajar_cot={cot.pk}" in resp["Location"]
    assert "enviar_cot" not in resp["Location"]

    resp = client.post(url, {"y_pdf": "1"}, HTTP_HX_REQUEST="true")
    cot2 = Cotizacion.objects.get(proyecto=entorno["p"], version=2)
    assert resp.status_code == 204
    assert f"bajar_cot={cot2.pk}" in resp["HX-Redirect"]


def test_sin_la_bandera_generar_se_comporta_como_siempre(client, entorno):
    client.force_login(entorno["admin"])
    resp = client.post(
        reverse("proyectos-generar-cotizacion", args=[entorno["p"].pk]))
    assert resp.status_code == 302
    assert "bajar_cot" not in resp["Location"]


def test_bajar_pdf_y_enviar_pueden_ir_juntos(client, entorno):
    from apps.cotizaciones.models import Cotizacion

    client.force_login(entorno["admin"])
    resp = client.post(
        reverse("proyectos-generar-cotizacion", args=[entorno["p"].pk]),
        {"y_pdf": "1", "y_enviar": "1"})
    cot = Cotizacion.objects.get(proyecto=entorno["p"], version=1)
    assert f"enviar_cot={cot.pk}" in resp["Location"]
    assert f"bajar_cot={cot.pk}" in resp["Location"]


def test_el_detalle_arranca_la_descarga_con_el_nombre_del_correo(client, entorno):
    """La descarga se llama IGUAL que el adjunto del correo (#166): el nombre
    sale de `services.nombre_archivo`, la misma función de `enviar_por_correo`."""
    from apps.cotizaciones import services
    from django.utils.html import escape

    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    client.force_login(entorno["admin"])

    html = client.get(
        reverse("proyectos-detalle", args=[entorno["p"].pk]),
        {"bajar_cot": cot.pk},
    ).content.decode()

    assert 'id="cot-descarga-pdf"' in html
    assert reverse("cotizaciones:pdf", args=[cot.pk]) in html
    assert f'data-nombre="{escape(services.nombre_archivo(cot))}.pdf"' in html


def test_un_bajar_cot_basura_o_ajeno_no_arranca_nada(
        client, entorno, proyecto_factory):
    from apps.cotizaciones import services

    otro = proyecto_factory(nombre="Otro", creado_por=entorno["admin"])
    ajena = services.generar_desde_proyecto(otro, entorno["admin"])
    client.force_login(entorno["admin"])
    url = reverse("proyectos-detalle", args=[entorno["p"].pk])

    for valor in ("abc", "", "-5", "99999", str(ajena.pk)):
        resp = client.get(url, {"bajar_cot": valor})
        assert resp.status_code == 200, valor
        assert 'id="cot-descarga-pdf"' not in resp.content.decode(), valor


def test_el_recuadro_pone_generar_y_descargar_pdf_como_boton_principal(
        client, entorno):
    client.force_login(entorno["admin"])
    html = client.get(
        reverse("proyectos-detalle", args=[entorno["p"].pk])).content.decode()

    assert "Generar v1 y descargar PDF" in html
    assert "data-cot-pdf-btn" in html


def test_si_el_pdf_falla_el_fetch_recibe_el_motivo(client, entorno, monkeypatch):
    """Con la cabecera del script, un PDF que no se pudo armar contesta 502 con
    el motivo (un redirect con mensaje se perdería dentro del fetch)."""
    from apps.cotizaciones import services

    from lib.documentos import ResultadoPdf

    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    monkeypatch.setattr(
        services, "generar_pdf",
        lambda c, a: ResultadoPdf(ok=False, error="Drive no está conectado"))
    client.force_login(entorno["admin"])

    resp = client.get(reverse("cotizaciones:pdf", args=[cot.pk]),
                      HTTP_X_LC_DESCARGA="1")

    assert resp.status_code == 502
    assert "Drive no está conectado" in resp.json()["error"]
    # Sin la cabecera, el comportamiento de siempre: redirect al detalle.
    assert client.get(reverse("cotizaciones:pdf", args=[cot.pk])).status_code == 302
