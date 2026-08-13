"""Tercera ronda del 2026-07-26 (Oscar, sobre el PDF ya desplegado).

- El documento debe ser «watertight»: la foto va con medida FIJA acotada (una
  bata vertical se comía media página) y el título usa el font del cuerpo.
- Bug: el botón «Un solo pago» de Forma de pago no se sentía; ahora el recuadro
  se repinta con el estado real.
- Safeguard: quitar la foto de un producto es un cambio PENDIENTE hasta que se
  aprieta «Guardar producto», y la página avisa si te sales con cambios.
- Sidebar al 100% del alto, repartido entre los botones.
- Ficha del cliente sin la pastilla de slug; títulos de sección del proveedor
  con el mismo estilo (fuera del recuadro).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _servicio(nombre="Bata", **kwargs):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción")
    return Servicio.objects.create(
        nombre=nombre, categoria=cat,
        precio_base=kwargs.pop("precio_base", Decimal("120.00")),
        costo=kwargs.pop("costo", Decimal("70.00")), **kwargs)


def _cot_con_linea(proyecto, autor, *, imagen="", codigo="COT-2026-9300"):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    cot = Cotizacion.objects.create(
        codigo=codigo, cliente=proyecto.cliente, proyecto=proyecto,
        titulo=proyecto.nombre, estado="generada", version=1, creado_por=autor,
        fecha_emision=dt.date(2026, 7, 26))
    CotizacionItem.objects.create(
        cotizacion=cot, concepto="Bordado sobre batas", descripcion="24 pz",
        cantidad=24, precio_unitario=Decimal("85.00"), imagen_file_id=imagen)
    return cot


# ── (1) La foto nunca descuadra el documento ────────────────────────────────

def test_la_foto_se_acota_a_una_caja_fija():
    """Sea cual sea la proporción, la imagen cabe en 150×76pt."""
    from apps.cotizaciones.services import _ALTO_FOTO_PT, _ANCHO_FOTO_PT, _medida_foto

    # Apaisada (banner 4:1): manda el ancho.
    ancho, alto = _medida_foto(0.25)
    assert (ancho, alto) == (_ANCHO_FOTO_PT, 38)

    # Vertical (la bata, 1×2): manda el ALTO — este era el caso roto.
    ancho, alto = _medida_foto(2.0)
    assert alto == _ALTO_FOTO_PT
    assert ancho == 38

    # Cuadrada.
    ancho, alto = _medida_foto(1.0)
    assert (ancho, alto) == (_ALTO_FOTO_PT, _ALTO_FOTO_PT)

    # Sin medir (Drive caído): se asume cuadrada del alto máximo, nunca grande.
    assert _medida_foto(0) == (_ALTO_FOTO_PT, _ALTO_FOTO_PT)
    assert max(_medida_foto(0)) <= _ALTO_FOTO_PT


def test_el_documento_pinta_la_foto_con_ancho_y_alto(proyecto_factory, usuario_factory,
                                                     monkeypatch):
    from apps.cotizaciones import services

    admin = usuario_factory(rol="super_admin")
    srv = _servicio()
    srv.imagen_file_id = "foto-bata"
    srv.save()
    cot = _cot_con_linea(proyecto_factory(nombre="Jeep Parte 1"), admin)
    cot.items.update(servicio=srv)

    # Foto vertical 1×2 (la que se salía de la hoja).
    monkeypatch.setattr("lib.imagen_publica.precalentar", lambda fid: True)
    monkeypatch.setattr("lib.imagen_publica.proporcion", lambda fid: 2.0)
    monkeypatch.setattr("lib.imagen_publica.url_absoluta",
                        lambda fid: "https://taller/img/x" if fid else "")

    html = services.construir_html_pdf(cot)
    assert 'height="76"' in html and 'width="38"' in html
    assert "height:76pt" in html
    # Nada de anchos sueltos sin alto: era lo que dejaba crecer la imagen.
    assert 'style="width:150pt;"' not in html


def test_el_titulo_del_documento_usa_el_font_del_cuerpo(proyecto_factory, usuario_factory):
    from apps.cotizaciones.services import construir_html_pdf
    admin = usuario_factory(rol="super_admin")
    cot = _cot_con_linea(proyecto_factory(nombre="Jeep Parte 1"), admin)

    html = construir_html_pdf(cot)
    assert "font-size:13pt" not in html          # ya no tiene escala propia
    assert "font-size: 11pt" in html             # la del <body>
    # LC 2026-08-12: con UN solo producto el título es «Producción de
    # [Producto]»; la envoltura del proyecto sólo sale con 2 o más.
    assert cot.titulo_documento in html


# ── (2) Forma de pago ───────────────────────────────────────────────────────

def test_el_boton_de_un_solo_pago_repinta_el_recuadro(client, proyecto_factory,
                                                      usuario_factory):
    """Oscar: «el botón de un solo pago no sirve». Guardaba, pero la respuesta
    era un 204 y la pastilla seguía marcando Anticipo."""
    from apps.cotizaciones import services
    admin = usuario_factory(rol="super_admin")
    cot = _cot_con_linea(proyecto_factory(nombre="Jeep"), admin, codigo="COT-2026-9301")
    client.force_login(admin)

    r = client.post(f"/cotizaciones/{cot.pk}/documento/",
                    {"campo": "forma_pago", "valor_forma_pago": "contado"})
    assert r.status_code == 200
    cot.refresh_from_db()
    assert cot.forma_pago == "contado"
    html = r.content.decode()
    # El recuadro que vuelve trae la pastilla marcada y la nota nueva.
    assert "pill-filtro-on" in html
    assert "Un sólo pago" in html
    assert services  # (import usado arriba)


def test_las_pastillas_mandan_su_valor_sin_depender_del_radio(client, proyecto_factory,
                                                              usuario_factory):
    """Cada pastilla lleva su valor en `hx-vals`: no depende de que htmx incluya
    el `value` de un radio escondido."""
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cot = _cot_con_linea(proyecto_factory(nombre="Jeep"), admin, codigo="COT-2026-9302")
    client.force_login(admin)

    html = client.get(reverse("cotizaciones:detalle", args=[cot.pk])).content.decode()
    assert '"valor_forma_pago": "contado"' in html
    assert '"valor_forma_pago": "anticipo"' in html
    assert 'hx-target="#documento-opciones"' in html


# ── (3) Safeguard de la foto del producto ───────────────────────────────────

def test_quitar_la_foto_no_se_guarda_hasta_apretar_guardar(client, usuario_factory):
    """El recuadro de la ficha del producto es DIFERIDO: sin `imagen_quitar`, la
    foto sigue ahí aunque se guarde el resto."""
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    srv = _servicio(nombre="Playera")
    srv.imagen_file_id = "foto-1"
    srv.imagen_url = "https://drive/1"
    srv.save()
    client.force_login(admin)

    datos = {"nombre": "Playera", "categoria": srv.categoria_id,
             "precio_base": "120.00", "costo": "70.00", "unidad": "pz"}
    r = client.post(reverse("catalogo-editar", args=[srv.pk]), datos)
    assert r.status_code in (200, 302)
    srv.refresh_from_db()
    assert srv.imagen_file_id == "foto-1"  # nadie la quitó

    # Con la marca del campo oculto sí se desliga.
    r = client.post(reverse("catalogo-editar", args=[srv.pk]), {**datos, "imagen_quitar": "1"})
    assert r.status_code in (200, 302)
    srv.refresh_from_db()
    assert srv.imagen_file_id == ""
    assert srv.imagen_url == ""


def test_la_ficha_del_producto_marca_el_borrado_como_diferido(client, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    srv = _servicio(nombre="Playera")
    client.force_login(admin)

    html = client.get(reverse("catalogo-editar", args=[srv.pk])).content.decode()
    assert 'data-img-diferido="1"' in html
    assert 'name="imagen_quitar"' in html
    # …y la página avisa si te sales con cambios sin guardar.
    assert "data-avisar-cambios" in html


def test_en_el_proyecto_el_borrado_sigue_siendo_inmediato(client, proyecto_factory,
                                                          usuario_factory):
    """Ahí no hay botón de guardar: la tarjeta se sigue comportando igual."""
    from apps.los_proyectos.models import ProyectoProducto
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(creado_por=admin)
    srv = _servicio(nombre="Playera")
    srv.imagen_file_id = "foto-cat"
    srv.save()
    linea = ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=1)
    client.force_login(admin)

    r = client.post(reverse("proyectos-producto-imagen", args=[linea.pk]), {"quitar": "1"})
    assert r.status_code == 200
    srv.refresh_from_db()
    assert srv.imagen_file_id == ""


# ── (4) Sidebar ─────────────────────────────────────────────────────────────

def test_el_sidebar_reparte_el_alto_entre_los_botones(client, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get(reverse("cartera-lista")).content.decode()
    # El <nav> crece con la ventana y reparte el sobrante entre los items.
    assert 'class="flex flex-1 flex-col justify-between gap-1 text-sm"' in html
    assert "h-screen" in html  # el <aside> sigue ocupando la ventana completa


def test_los_dos_sidebars_reparten_igual():
    """Regla §18: el sidebar es dual-copy, los dos deben quedar igual."""
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    marca = 'class="flex flex-1 flex-col justify-between gap-1 text-sm"'
    for app in ("el-taller", "la-gerencia"):
        ruta = raiz / app / "templates" / "_componentes_tailadmin" / "sidebar.html"
        assert marca in ruta.read_text(encoding="utf-8"), app


# ── (5) Estilo de las fichas ────────────────────────────────────────────────

def test_la_ficha_del_cliente_ya_no_trae_la_pastilla_de_slug(client, cliente_factory,
                                                             usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(razon_social="OPTIMIST")
    client.force_login(admin)

    html = client.get(reverse("cartera-detalle", args=[cli.pk])).content.decode()
    encabezado = html.split("Proyectos activos")[0]
    assert f"${cli.slug}" not in encabezado      # ya no está arriba…
    assert f"${cli.slug}" in html                # …pero sigue en Identificación


def test_el_proveedor_usa_los_titulos_de_seccion_del_cliente(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social="Telas del Norte")
    client.force_login(admin)

    html = client.get(reverse("catalogo-proveedor-detalle", args=[prov.pk])).content.decode()
    titulo = 'class="mb-3 text-theme-xl font-medium text-gray-900 dark:text-gray-100"'
    assert titulo in html
    assert "¿Qué surte?" in html and "Productos que surte" in html
