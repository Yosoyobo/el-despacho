"""Smoke test del Wave 3 (S-TailAdmin-Sweep): _tabla_datos.html y _tabla_acciones.html
renderizan, soportan sort link toggle y no fugan `{# ... #}` literal.
"""

import pytest
from django.template.loader import render_to_string

pytestmark = [pytest.mark.taller]


def _assert_sin_comentarios(html: str):
    assert "{#" not in html
    assert "#}" not in html
    assert "{% comment" not in html
    assert "{% endcomment" not in html


CABECERAS_BASE = [
    {"label": "Código", "sort_key": "codigo"},
    {"label": "Nombre"},
    {"label": "Monto", "sort_key": "monto", "align": "right"},
]


def test_tabla_datos_estructura_basica_y_empty_state():
    h = render_to_string(
        "_componentes_tailadmin/_tabla_datos.html",
        {"cabeceras": CABECERAS_BASE, "filas_html": "", "vacia_mensaje": "Sin nada."},
    )
    assert "<table" in h
    assert "sticky" in h
    assert "Código" in h and "Nombre" in h and "Monto" in h
    assert "Sin nada." in h
    assert "text-right" in h  # cabecera Monto alineada
    _assert_sin_comentarios(h)


def test_tabla_datos_columna_no_sortable_es_texto_plano():
    h = render_to_string(
        "_componentes_tailadmin/_tabla_datos.html",
        {"cabeceras": [{"label": "Sólo etiqueta"}], "filas_html": ""},
    )
    # No hay link en la cabecera no-sortable.
    assert "Sólo etiqueta" in h
    assert "<a href=\"?" not in h.split("Sólo etiqueta")[0][-200:]
    _assert_sin_comentarios(h)


def test_tabla_datos_sort_toggle_asc_to_desc():
    # Ordenando ASC por 'codigo' → el link de la cabecera debe ir a '-codigo'.
    h = render_to_string(
        "_componentes_tailadmin/_tabla_datos.html",
        {
            "cabeceras": CABECERAS_BASE,
            "filas_html": "",
            "orden_actual": "codigo",
            "querystring_base": "q=foo&estado=activo",
        },
    )
    assert "orden=-codigo" in h
    assert "q=foo&amp;estado=activo&amp;orden=-codigo" in h or "q=foo&estado=activo&orden=-codigo" in h
    # Indicador de orden ascendente.
    assert "&uarr;" in h or "↑" in h
    _assert_sin_comentarios(h)


def test_tabla_datos_sort_toggle_desc_to_asc():
    h = render_to_string(
        "_componentes_tailadmin/_tabla_datos.html",
        {"cabeceras": CABECERAS_BASE, "filas_html": "", "orden_actual": "-codigo"},
    )
    # Link debe limpiar el guion.
    assert "orden=codigo" in h
    assert "&darr;" in h or "↓" in h
    _assert_sin_comentarios(h)


def test_tabla_datos_columna_no_activa_muestra_indicador_neutral():
    h = render_to_string(
        "_componentes_tailadmin/_tabla_datos.html",
        {"cabeceras": CABECERAS_BASE, "filas_html": "", "orden_actual": "monto"},
    )
    # 'codigo' es sortable pero no activo → indicador neutro y link a 'codigo'.
    assert "&#8597;" in h or "↕" in h
    assert "orden=codigo" in h
    # 'monto' está activo asc.
    assert "orden=-monto" in h
    _assert_sin_comentarios(h)


def test_tabla_datos_filas_html_se_inserta_safe():
    filas = '<tr><td colspan="3">Hola <b>mundo</b></td></tr>'
    h = render_to_string(
        "_componentes_tailadmin/_tabla_datos.html",
        {"cabeceras": CABECERAS_BASE, "filas_html": filas},
    )
    assert "<b>mundo</b>" in h  # render como safe
    _assert_sin_comentarios(h)


def test_tabla_acciones_dropdown_render():
    items = [
        {"url": "/x/", "label": "Ver"},
        {"url": "/x/editar/", "label": "Editar"},
        {"divider": True},
        {"url": "/x/anular/", "label": "Anular", "peligroso": True},
    ]
    h = render_to_string(
        "_componentes_tailadmin/_tabla_acciones.html",
        {"id": "acc-1", "items": items},
    )
    assert "data-dropdown-trigger" in h
    assert 'id="acc-1"' in h
    assert "/x/editar/" in h
    assert "text-error-600" in h  # acción peligrosa
    assert "border-t" in h  # divider
    _assert_sin_comentarios(h)
