"""Smoke test del Wave 2 (S-TailAdmin-Sweep): los 7 partials de form primitives
renderizan sin excepción, no fugan `{# ... #}` literal y respetan params clave.
"""

import pytest
from django.template.loader import render_to_string

pytestmark = [pytest.mark.taller]


def _assert_sin_comentarios(html: str):
    assert "{#" not in html, "Fragmento {# Django sin cerrar en partial"
    assert "#}" not in html, "Fragmento #} Django sin abrir en partial"
    assert "{% comment" not in html
    assert "{% endcomment" not in html


def test_checkbox():
    h = render_to_string(
        "_componentes_tailadmin/_checkbox.html",
        {"name": "archivados", "value": "1", "label": "Incluir archivados", "checked": True, "hint": "Sólo admin"},
    )
    assert 'name="archivados"' in h
    assert 'value="1"' in h
    assert "Incluir archivados" in h
    assert "Sólo admin" in h
    assert "checked" in h
    _assert_sin_comentarios(h)


def test_radio():
    h = render_to_string(
        "_componentes_tailadmin/_radio.html",
        {"name": "tipo", "value": "grupo", "label": "Grupo", "checked": False},
    )
    assert 'type="radio"' in h
    assert 'name="tipo"' in h
    assert 'value="grupo"' in h
    assert "Grupo" in h
    _assert_sin_comentarios(h)


def test_switch():
    h = render_to_string(
        "_componentes_tailadmin/_switch.html",
        {"name": "categoria", "value": "buzon", "label": "El Buzón", "checked": True, "hint": "Avisos del buzón"},
    )
    assert 'type="checkbox"' in h
    assert "peer" in h  # patrón TailAdmin
    assert "peer-checked:" in h
    assert "El Buzón" in h
    assert "Avisos del buzón" in h
    _assert_sin_comentarios(h)


def test_file_upload():
    h = render_to_string(
        "_componentes_tailadmin/_file_upload.html",
        {"name": "archivo", "label": "Comprobante", "accept": "image/*,.pdf", "multiple": True, "hint": "Máx 25 MB", "required": True},
    )
    assert 'type="file"' in h
    assert 'accept="image/*,.pdf"' in h
    assert "multiple" in h
    assert "required" in h
    assert "Comprobante" in h
    assert "data-file-upload" in h
    _assert_sin_comentarios(h)


def test_datepicker():
    h = render_to_string(
        "_componentes_tailadmin/_datepicker.html",
        {"name": "fecha_real_entrega", "label": "Fecha real de entrega", "required": True, "hint": "Cuando se entregó el proyecto"},
    )
    assert 'type="date"' in h
    assert 'name="fecha_real_entrega"' in h
    assert "Fecha real de entrega" in h
    assert "Cuando se entregó" in h
    # icono de calendario decorativo
    assert "pointer-events-none" in h
    _assert_sin_comentarios(h)


def test_tags_input():
    h = render_to_string(
        "_componentes_tailadmin/_tags_input.html",
        {"name": "etiquetas", "label": "Etiquetas", "valor": "urgente,cliente-vip", "placeholder": "Agrega…"},
    )
    assert "data-tags-input" in h
    assert "data-tags-hidden" in h
    assert "data-tags-typer" in h
    assert 'name="etiquetas"' in h
    assert 'value="urgente,cliente-vip"' in h
    assert "Etiquetas" in h
    _assert_sin_comentarios(h)


def test_select_buscable():
    h = render_to_string(
        "_componentes_tailadmin/_select_buscable.html",
        {
            "name": "centro_de_costo",
            "opciones": [("operacion", "Operación"), ("ventas", "Ventas"), ("rh", "RH")],
            "seleccionado": "ventas",
            "label": "Centro de costo",
            "placeholder": "Selecciona…",
        },
    )
    assert "data-select-buscable" in h
    assert 'name="centro_de_costo"' in h
    assert "<option" in h
    assert 'value="ventas" selected' in h
    assert "Operación" in h
    assert "Selecciona…" in h
    _assert_sin_comentarios(h)


def test_partials_no_renderizan_comentarios_django():
    """Bug C §14: ningún partial Wave 2 puede tener `{# ... #}` multilínea."""
    nombres = ["_checkbox", "_radio", "_switch", "_file_upload", "_datepicker", "_tags_input", "_select_buscable"]
    for n in nombres:
        h = render_to_string(
            f"_componentes_tailadmin/{n}.html",
            {"name": "x", "value": "v", "label": "L", "opciones": []},
        )
        _assert_sin_comentarios(h)
