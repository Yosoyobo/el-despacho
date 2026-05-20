"""Smoke test del Wave 4 (S-TailAdmin-Sweep): _info_card.html y _action_bar.html
renderizan correctamente y no fugan comentarios literales.
"""

import pytest
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

pytestmark = [pytest.mark.taller]


def _assert_sin_comentarios(html: str):
    assert "{#" not in html
    assert "#}" not in html
    assert "{% comment" not in html
    assert "{% endcomment" not in html


def test_info_card_renderiza_titulo_y_items():
    h = render_to_string(
        "_componentes_tailadmin/_info_card.html",
        {
            "titulo": "Identificación",
            "items": [
                {"label": "RFC", "value": "XAXX010101000", "mono": True},
                {"label": "Creado", "value": "21 May 2026"},
            ],
        },
    )
    assert "Identificación" in h
    assert "RFC" in h and "XAXX010101000" in h
    assert "Creado" in h and "21 May 2026" in h
    assert "font-mono" in h
    _assert_sin_comentarios(h)


def test_info_card_item_value_html_se_renderiza_como_safe():
    h = render_to_string(
        "_componentes_tailadmin/_info_card.html",
        {
            "titulo": "Pago",
            "items": [
                {"label": "Estado", "value_html": mark_safe(
                    '<span class="badge badge-success">Pagado</span>'
                )},
            ],
        },
    )
    assert '<span class="badge badge-success">Pagado</span>' in h
    _assert_sin_comentarios(h)


def test_info_card_value_vacio_muestra_dash():
    h = render_to_string(
        "_componentes_tailadmin/_info_card.html",
        {"titulo": "Contacto", "items": [{"label": "Email"}]},
    )
    assert "—" in h
    _assert_sin_comentarios(h)


def test_action_bar_sticky_por_default_con_acciones():
    h = render_to_string(
        "_componentes_tailadmin/_action_bar.html",
        {
            "meta": mark_safe("<span>Actualizado <time>hoy</time></span>"),
            "acciones": mark_safe('<button class="btn-primario">Guardar</button>'),
        },
    )
    assert "sticky" in h
    assert "Actualizado" in h
    assert "Guardar" in h
    _assert_sin_comentarios(h)


def test_action_bar_no_sticky_cuando_sticky_false():
    h = render_to_string(
        "_componentes_tailadmin/_action_bar.html",
        {
            "sticky": False,
            "acciones": mark_safe('<button class="btn-secundario">Cerrar</button>'),
        },
    )
    assert "sticky" not in h
    assert "Cerrar" in h
    _assert_sin_comentarios(h)
