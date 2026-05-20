"""Smoke test del Wave 6 (S-TailAdmin-Sweep): empty state, skeleton,
tooltip y spinner.
"""

import pytest
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

pytestmark = [pytest.mark.taller]


def _no_fugas(html: str):
    assert "{#" not in html
    assert "#}" not in html
    assert "{% comment" not in html
    assert "{% endcomment" not in html


def test_empty_state_basico():
    h = render_to_string(
        "_componentes_tailadmin/_empty_state.html",
        {"titulo": "Sin nada", "descripcion": "Aún no hay datos."},
    )
    assert "Sin nada" in h
    assert "Aún no hay datos." in h
    assert "<svg" in h  # icono default
    assert "border-dashed" in h
    _no_fugas(h)


def test_empty_state_con_cta():
    h = render_to_string(
        "_componentes_tailadmin/_empty_state.html",
        {
            "titulo": "Sin clientes",
            "icono": "folder",
            "cta_url": "/cartera/nuevo/",
            "cta_label": "Crear primer cliente",
        },
    )
    assert "Sin clientes" in h
    assert 'href="/cartera/nuevo/"' in h
    assert "Crear primer cliente" in h
    _no_fugas(h)


def test_empty_state_iconos_disponibles():
    for icono in ("inbox", "search", "tasks", "folder", "chat", "alert", "sparkles"):
        h = render_to_string(
            "_componentes_tailadmin/_empty_state.html",
            {"titulo": "Test", "icono": icono},
        )
        assert "<svg" in h
        _no_fugas(h)


def test_skeleton_text_por_default():
    h = render_to_string("_componentes_tailadmin/_skeleton.html", {})
    assert "animate-pulse" in h
    _no_fugas(h)


def test_skeleton_card():
    h = render_to_string("_componentes_tailadmin/_skeleton.html", {"tipo": "card"})
    assert "animate-pulse" in h
    assert "rounded-2xl" in h
    _no_fugas(h)


def test_skeleton_avatar():
    h = render_to_string("_componentes_tailadmin/_skeleton.html", {"tipo": "avatar"})
    assert "rounded-full" in h
    assert "animate-pulse" in h
    _no_fugas(h)


def test_skeleton_filas_multiple():
    h = render_to_string(
        "_componentes_tailadmin/_skeleton.html",
        {"tipo": "fila", "filas": 4},
    )
    # 4 filas: contar las divisiones internas que representan filas
    assert h.count("animate-pulse") >= 4
    _no_fugas(h)


def test_tooltip_envuelve_ancla_y_muestra_texto():
    h = render_to_string(
        "_componentes_tailadmin/_tooltip.html",
        {"texto": "Acción destructiva", "ancla": mark_safe('<button>Anular</button>')},
    )
    assert "<button>Anular</button>" in h
    assert "Acción destructiva" in h
    assert "group" in h
    assert "group-hover:opacity-100" in h
    _no_fugas(h)


def test_tooltip_posiciones():
    for pos in ("top", "bottom", "left", "right"):
        h = render_to_string(
            "_componentes_tailadmin/_tooltip.html",
            {"texto": "X", "ancla": mark_safe("<span>Y</span>"), "posicion": pos},
        )
        assert "Y" in h
        _no_fugas(h)


def test_spinner_default_brand_sm():
    h = render_to_string("_componentes_tailadmin/_spinner.html", {})
    assert "animate-spin" in h
    assert "text-brand-500" in h
    assert "h-4 w-4" in h
    _no_fugas(h)


def test_spinner_con_etiqueta_y_tamano():
    h = render_to_string(
        "_componentes_tailadmin/_spinner.html",
        {"tamano": "lg", "color": "gray", "etiqueta": "Cargando…"},
    )
    assert "h-8 w-8" in h
    assert "text-gray-400" in h
    assert "Cargando…" in h
    _no_fugas(h)
