"""Ronda del 2026-07-28 (Oscar) — documento, tarjeta de producto y móvil.

Cotización (PDF):
  1. La descripción + foto no se separan de su tabla de montos: el envoltorio
     de tabla se refuerza con `preventOverflow` por la API de Documentos.
  2. Un renglón de aire menos entre el título y el primer elemento.
  3. Las fotos van centradas en su celda.
  4. La foto que se subió al ALIAS de un producto gana sobre la del catálogo.
  5. Interlineado más apretado.
  6. En móvil el PDF se puede guardar/compartir con su nombre.
  7. Los bloques que arrancan hoja nueva llevan dos renglones de aire.

Página del proyecto: borrado de foto DIFERIDO, tarjeta rediseñada y recuadro
de tareas compacto. Móvil: calendario legible. Y los extras de la misma ronda
(calendario sin proyectos cancelados, contador en Novedades, listas de
Tesorería y adjunto en el mini Chalán del Dashboard).
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


@pytest.fixture
def _drive_falso(monkeypatch):
    """Neutraliza la bajada de imágenes: el PDF se arma sin pegarle a Drive."""
    monkeypatch.setattr("lib.imagen_publica.precalentar", lambda fid: True)
    monkeypatch.setattr("lib.imagen_publica.proporcion", lambda fid: 1.0)
    monkeypatch.setattr("lib.imagen_publica.url_absoluta",
                        lambda fid: f"https://taller/img/{fid}" if fid else "")


def _servicio(nombre="Taza metálica", **kwargs):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Promocionales")
    return Servicio.objects.create(
        nombre=nombre, categoria=cat,
        precio_base=kwargs.pop("precio_base", Decimal("230.00")),
        costo=kwargs.pop("costo", Decimal("121.39")), **kwargs)


def _cot(proyecto, autor, *, codigo="COT-2026-9400"):
    from apps.cotizaciones.models import Cotizacion
    return Cotizacion.objects.create(
        codigo=codigo, cliente=proyecto.cliente, proyecto=proyecto,
        titulo=proyecto.nombre, estado="generada", version=1, creado_por=autor,
        fecha_emision=dt.date(2026, 7, 28))


def _item(cot, servicio=None, **kwargs):
    from apps.cotizaciones.models import CotizacionItem
    datos = {
        "concepto": kwargs.pop("concepto", "Branded Stainless Mug"),
        "descripcion": kwargs.pop("descripcion", "80 pz"),
        "cantidad": kwargs.pop("cantidad", 80),
        "precio_unitario": kwargs.pop("precio_unitario", Decimal("230.00")),
    }
    datos.update(kwargs)
    return CotizacionItem.objects.create(cotizacion=cot, servicio=servicio, **datos)


# ── (1) Paginación reforzada por la API de Documentos ───────────────────────

def test_prevent_overflow_una_peticion_por_tabla_con_todas_sus_filas():
    """El envoltorio de tabla no basta: una fila más alta que lo que resta de
    hoja se desborda igual. Se prende `preventOverflow` en todas."""
    from lib.google_drive import _peticiones_prevent_overflow

    peticiones = _peticiones_prevent_overflow([
        {"startIndex": 10, "table": {"rows": 3}},
        {"startIndex": 90, "paragraph": {}},          # no es tabla
        {"startIndex": 120, "table": {"rows": 1}},
    ])
    assert len(peticiones) == 2
    primera = peticiones[0]["updateTableRowStyle"]
    assert primera["tableStartLocation"] == {"index": 10}
    assert primera["rowIndices"] == [0, 1, 2]
    assert primera["tableRowStyle"] == {"preventOverflow": True}
    assert primera["fields"] == "preventOverflow"


def test_prevent_overflow_tolera_basura():
    from lib.google_drive import _peticiones_prevent_overflow
    assert _peticiones_prevent_overflow([]) == []
    assert _peticiones_prevent_overflow([
        "no soy dict", {"table": {"rows": 2}},              # sin startIndex
        {"startIndex": 1, "table": {}},                     # sin filas
        {"startIndex": 2, "table": {"rows": 0}},
    ]) == []


def test_html_a_pdf_endurece_la_paginacion_antes_de_exportar(monkeypatch):
    """El seguro se prende sobre el Doc temporal, ANTES del export."""
    from lib.google_drive import GoogleDriveWrapper

    pasos: list[str] = []
    wrapper = GoogleDriveWrapper()
    monkeypatch.setattr(wrapper, "_subir_html_como_gdoc",
                        lambda html, nombre, carpeta: pasos.append("doc") or "doc-1")
    monkeypatch.setattr(wrapper, "_endurecer_paginacion",
                        lambda doc_id: pasos.append("endurece") or True)
    monkeypatch.setattr(wrapper, "exportar",
                        lambda doc_id, mime: pasos.append("export") or b"%PDF")
    monkeypatch.setattr(wrapper, "borrar", lambda doc_id: pasos.append("borra"))
    monkeypatch.setattr(wrapper, "_subir_contenido",
                        lambda *a, **k: {"id": "pdf-1", "webViewLink": "u"})

    meta = wrapper.html_a_pdf(html="<p>x</p>", nombre="Cotización")
    assert pasos == ["doc", "endurece", "export", "borra"]
    assert meta["pdf_bytes"] == b"%PDF"


def test_endurecer_paginacion_nunca_tumba_el_pdf(monkeypatch):
    """Sin API de Documentos (o con error), el PDF se exporta igual."""
    from lib.google_drive import GoogleDriveWrapper

    wrapper = GoogleDriveWrapper()
    monkeypatch.setattr(wrapper, "_headers", lambda: (_ for _ in ()).throw(RuntimeError("sin token")))
    assert wrapper._endurecer_paginacion("doc-1") is False


# ── (2)(3)(5) Aire, imágenes centradas e interlineado ───────────────────────

def test_menos_aire_entre_titulo_y_primer_elemento(proyecto_factory, usuario_factory,
                                                   _drive_falso):
    from apps.cotizaciones import services
    admin = usuario_factory(rol="super_admin")
    cot = _cot(proyecto_factory(nombre="Jeep Parte 1"), admin)
    _item(cot)

    html = services.construir_html_pdf(cot)
    # 28pt → 14pt (2026-07-28) → 8pt (2026-08-04, «apretar aún más todo»).
    assert "margin:0 0 8pt 0" in html
    assert "margin:0 0 28pt 0" not in html
    assert "margin:0 0 14pt 0" not in html


def test_la_foto_va_centrada_en_su_celda(proyecto_factory, usuario_factory, _drive_falso):
    from apps.cotizaciones import services
    admin = usuario_factory(rol="super_admin")
    cot = _cot(proyecto_factory(nombre="Jeep Parte 1"), admin)
    _item(cot, imagen_file_id="foto-1")

    html = services.construir_html_pdf(cot)
    assert 'vertical-align:middle; text-align:center;' in html
    assert '<p align="center" style="margin:0; text-align:center;"><img src="https://taller/img/foto-1"' in html
    assert 'align="right"' not in html


def test_interlineado_apretado(proyecto_factory, usuario_factory, _drive_falso):
    from apps.cotizaciones import services
    admin = usuario_factory(rol="super_admin")
    cot = _cot(proyecto_factory(nombre="Jeep Parte 1"), admin)
    _item(cot)

    html = services.construir_html_pdf(cot)
    # LC 2026-08-04 (Oscar: «apretar aún más el interlineado de todo»): el cuerpo
    # bajó de 1.15 a 1.02 y las celdas de concepto de 2pt a 1pt de padding.
    assert "line-height: 1.02" in html
    assert "padding:3pt 5pt" not in html
    assert "#cccccc; padding:1pt 5pt" in html


# ── (4) La foto del alias gana sobre la del catálogo ────────────────────────

def test_la_foto_del_alias_gana_sobre_la_congelada(proyecto_factory, usuario_factory,
                                                   _drive_falso):
    """Oscar: «la imagen que subí al alias no sirve, se incrusta la principal».
    La versión congeló la del catálogo porque se generó antes de subirla."""
    from apps.cotizaciones import services
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    proyecto = proyecto_factory(nombre="Jeep Parte 1")
    srv = _servicio()
    srv.imagen_file_id = "foto-catalogo"
    srv.save()
    ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=srv, cantidad=80,
        nombre_proyecto="Branded Stainless Mug", imagen_file_id="foto-del-alias")

    cot = _cot(proyecto, admin)
    _item(cot, servicio=srv, imagen_file_id="foto-catalogo")

    html = services.construir_html_pdf(cot)
    assert "https://taller/img/foto-del-alias" in html
    assert "foto-catalogo" not in html


def test_sin_foto_propia_se_respeta_la_congelada(proyecto_factory, usuario_factory,
                                                 _drive_falso):
    """El congelado sigue vivo: si el uso no tiene foto propia, manda la que se
    guardó con la versión (aunque después le cambien la del catálogo)."""
    from apps.cotizaciones import services
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    proyecto = proyecto_factory(nombre="Jeep Parte 1")
    srv = _servicio()
    srv.imagen_file_id = "foto-nueva-del-catalogo"
    srv.save()
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=80)

    cot = _cot(proyecto, admin)
    _item(cot, servicio=srv, imagen_file_id="foto-congelada")

    html = services.construir_html_pdf(cot)
    assert "https://taller/img/foto-congelada" in html


# ── (6) Guardar / compartir en móvil ────────────────────────────────────────

def test_la_vista_previa_ofrece_compartir_con_el_nombre_correcto(
        client, proyecto_factory, usuario_factory, _drive_falso):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    cot = _cot(proyecto_factory(nombre="Jeep Parte 1"), admin)
    _item(cot)

    html = client.get(reverse("cotizaciones:ver", args=[cot.pk])).content.decode()
    assert f'download="{cot.nombre_pdf}.pdf"' in html
    assert "navigator.canShare" in html and "navigator.share" in html
    # Y al imprimir, sin el encabezado/pie que estampa el navegador.
    assert "@page { margin: 0; }" in html


# ── La simulación de la paginación (sin aire calculado a mano) ──────────────

def test_paginar_reporta_lo_que_queda_libre_en_la_ultima_hoja():
    """LC 2026-07-29: el aire de dos `<br>` en los bloques que arrancaban hoja se
    RETIRÓ — al salir de una estimación caía a media hoja y producía los «espacios
    extraños» que reportó Oscar. `_paginar` sólo informa lo que queda libre, y eso
    únicamente gradúa el hueco de las notas (con tope)."""
    from apps.cotizaciones.services import _ALTO_UTIL_PT, _paginar

    class _Cot:
        incluir_desglose = False

    def _bloques(n):
        return [{"it": None, "imagen": "u", "img_alto": 200, "extras": []} for _ in range(n)]

    # `libre` es lo que queda en la ÚLTIMA hoja (no acumulado): cada bloque que
    # cabe en la hoja en curso se lo come, y al pasar de hoja vuelve a sobrar.
    libre_vacio = _paginar(_Cot(), [], [])["libre"]
    libre_uno = _paginar(_Cot(), _bloques(1), [])["libre"]
    assert libre_vacio > libre_uno >= 0
    for n in (1, 2, 6, 12):
        assert 0 <= _paginar(_Cot(), _bloques(n), [])["libre"] <= _ALTO_UTIL_PT
    assert "aire_bloques" not in _paginar(_Cot(), _bloques(1), [])


def test_un_documento_corto_no_lleva_aire_extra(proyecto_factory, usuario_factory,
                                                _drive_falso):
    from apps.cotizaciones import services
    admin = usuario_factory(rol="super_admin")
    cot = _cot(proyecto_factory(nombre="Jeep Parte 1"), admin)
    _item(cot)

    html = services.construir_html_pdf(cot)
    # El único `<br><br>` posible sería el aire de página; en una hoja no aplica.
    assert "<br><br>" not in html


# ── Proyecto: borrado de foto DIFERIDO ──────────────────────────────────────

def _datos_form_producto(pp, **extra):
    datos = {
        "servicio": str(pp.servicio_id),
        "cantidad": str(pp.cantidad),
        "merma": "0",
        "orden": "0",
        "incluir_en_calculo": "on",
        "nombre_proyecto": pp.nombre_proyecto,
        "nota": "",
        "procesos_json": "[]",
        "ventas_json": "[]",
    }
    datos.update(extra)
    return datos


def test_quitar_la_foto_solo_se_aplica_al_guardar(proyecto_factory):
    """Oscar: «si salgo del proyecto sin guardar, igual se queda eliminada»."""
    from apps.los_proyectos.forms import ProyectoProductoForm
    from apps.los_proyectos.models import ProyectoProducto

    srv = _servicio()
    pp = ProyectoProducto.objects.create(
        proyecto=proyecto_factory(), servicio=srv, cantidad=5,
        nombre_proyecto="Taza Janet", imagen_file_id="foto-del-uso")

    # Sin la marca, la foto sigue.
    form = ProyectoProductoForm(_datos_form_producto(pp), instance=pp)
    assert form.is_valid(), form.errors
    form.save()
    pp.refresh_from_db()
    assert pp.imagen_file_id == "foto-del-uso"

    # Con la marca (lo que escribe el recuadro en modo diferido), se desliga.
    form = ProyectoProductoForm(_datos_form_producto(pp, imagen_quitar="1"), instance=pp)
    assert form.is_valid(), form.errors
    form.save()
    pp.refresh_from_db()
    assert pp.imagen_file_id == ""


def test_quitar_la_foto_heredada_toca_el_catalogo(proyecto_factory):
    """Sin foto propia, la que se ve es la del catálogo y es ésa la que se
    quita (el front lo confirma antes de pedirlo)."""
    from apps.los_proyectos.forms import ProyectoProductoForm
    from apps.los_proyectos.models import ProyectoProducto

    srv = _servicio()
    srv.imagen_file_id = "foto-catalogo"
    srv.save()
    pp = ProyectoProducto.objects.create(proyecto=proyecto_factory(), servicio=srv, cantidad=5)

    form = ProyectoProductoForm(_datos_form_producto(pp, imagen_quitar="1"), instance=pp)
    assert form.is_valid(), form.errors
    form.save()
    srv.refresh_from_db()
    assert srv.imagen_file_id == ""


def test_la_tarjeta_de_producto_sigue_el_render(client, proyecto_factory, usuario_factory):
    """Foto en la esquina (diferida), resumen que se queda, sin «usa: …»,
    utilidad por pieza y del producto, y el «+ Proceso» de venta en verde."""
    from apps.los_proyectos.models import ProyectoProducto
    from django.urls import reverse

    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    proyecto = proyecto_factory(nombre="Jeep Parte 1")
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=_servicio(), cantidad=80)

    html = client.get(reverse("proyectos-detalle", args=[proyecto.pk])).content.decode()
    assert 'data-img-diferido="1"' in html          # (a) borrado pendiente
    assert 'name="productos-0-imagen_quitar"' in html
    assert "data-alias-origen" not in html          # (c)
    assert "data-utilidad-pp" in html               # (f)
    assert "data-utilidad" in html                  # (g)
    assert "venta-add" in html and "bg-success-500" in html   # (h)
    # (b) el resumen ya no nace oculto ni se esconde al expandir.
    assert "data-resumen" in html
    assert 'class="truncate text-sm font-medium' in html


def test_el_recuadro_de_tareas_vacio_es_compacto(client, proyecto_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    proyecto = proyecto_factory(nombre="Jeep Parte 1")

    html = client.get(reverse("proyectos-detalle", args=[proyecto.pk])).content.decode()
    assert "Sin tareas todavía." in html
    assert "min-w-[560px]" not in html      # tampoco fuerza scroll en móvil


# ── Calendario: nada de proyectos cancelados ────────────────────────────────

def test_el_calendario_ignora_los_proyectos_cancelados(proyecto_factory, usuario_factory):
    from datetime import date, timedelta

    from apps.calendario.services import eventos_por_dia

    admin = usuario_factory(rol="super_admin")
    manana = date.today() + timedelta(days=1)
    vivo = proyecto_factory(nombre="Va", fecha_compromiso=manana)
    proyecto_factory(nombre="No va", fecha_compromiso=manana, estado="cancelado")

    eventos = eventos_por_dia(admin, date.today(), manana + timedelta(days=1))
    titulos = [e["titulo"] for lista in eventos.values() for e in lista]
    assert any(vivo.nombre in t for t in titulos)
    assert not any("No va" in t for t in titulos)


def test_las_tareas_de_un_proyecto_cancelado_tampoco_salen(proyecto_factory, usuario_factory):
    from datetime import date, timedelta

    from apps.calendario.services import eventos_por_dia
    from apps.el_pizarron.models import Tarea

    admin = usuario_factory(rol="super_admin")
    manana = date.today() + timedelta(days=1)
    cancelado = proyecto_factory(nombre="Cancelado", estado="cancelado")
    Tarea.objects.create(proyecto=cancelado, titulo="Entregar lonas",
                         creado_por=admin, asignada_a=admin, fecha_compromiso=manana)

    eventos = eventos_por_dia(admin, date.today(), manana + timedelta(days=1))
    titulos = [e["titulo"] for lista in eventos.values() for e in lista]
    assert not any("Entregar lonas" in t for t in titulos)


# ── Novedades: contador por fila ────────────────────────────────────────────

def test_novedades_numera_las_entregas_desde_abajo(client, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)

    html = client.get(reverse("ayuda-novedades")).content.decode()
    assert "tabular-nums text-[10px]" in html
    # La más vieja lleva el 1 y la más reciente el número más alto.
    assert ">1</span>" in html


# ── Tesorería: listas sin código ni menú, abriendo en editable ──────────────

@pytest.mark.parametrize("tipo", ["ingresos", "egresos"])
def test_las_listas_de_tesoreria_abren_en_editable(client, usuario_factory,
                                                   proyecto_factory, tipo):
    from datetime import date

    from apps.tesoreria.models import CentroDeCosto, Egreso, Ingreso
    from django.urls import reverse

    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    proyecto = proyecto_factory(nombre="Jeep Parte 1")
    if tipo == "ingresos":
        obj = Ingreso.objects.create(
            fecha=date.today(), monto=Decimal("100.00"), descripcion="Anticipo Jeep",
            cliente=proyecto.cliente, proyecto=proyecto, creado_por=admin)
        url_lista, ruta_editar = "tesoreria:ingresos-lista", "tesoreria:ingreso-editar"
    else:
        centro, _ = CentroDeCosto.objects.get_or_create(
            slug="insumos-de-proyecto", defaults={"nombre": "Insumos de proyecto"})
        obj = Egreso.objects.create(
            fecha=date.today(), monto=Decimal("100.00"), descripcion="Tazas",
            centro_de_costo=centro, proyecto=proyecto, creado_por=admin)
        url_lista, ruta_editar = "tesoreria:egresos-lista", "tesoreria:egreso-editar"

    html = client.get(reverse(url_lista)).content.decode()
    assert reverse(ruta_editar, args=[obj.pk]) in html    # la fila abre editando
    assert obj.codigo not in html                          # sin columna de código
    assert "Descripción" in html                           # columna nueva
    assert "data-dropdown-trigger" not in html             # sin menú de 3 puntos


# ── Mini Chalán del Dashboard: adjunto ──────────────────────────────────────

def test_el_mini_chalan_acepta_una_foto(client, usuario_factory, monkeypatch):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse

    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)

    vistos = {}

    def _falso_conversar(**kwargs):
        vistos.update(kwargs)
        return {"mensajes": []}

    monkeypatch.setattr("apps.el_dictado.views_chat.conversar", _falso_conversar)
    monkeypatch.setattr("apps.el_dictado.views_chat._imagenes_de_request",
                        lambda request: [{"base64": "x", "media_type": "image/png"}])

    foto = SimpleUploadedFile("recibo.png", b"\x89PNG", content_type="image/png")
    resp = client.post(reverse("chalan-nuevo"), {"mensaje": "", "imagen": foto})

    assert resp.status_code == 302
    assert vistos.get("imagenes"), "la imagen no llegó al Chalán"
    assert vistos.get("archivo_adjunto") is not None
