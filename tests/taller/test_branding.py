"""S2b.1.5 — Logo Learning Center en sidebars/login/favicon/manifest/errores."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parents[2]


def test_logo_aparece_en_sidebar_taller(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "branding/Logo_LC" in html, "Logo no aparece en sidebar autenticado"


def test_logo_aparece_en_login_taller(client):
    resp = client.get("/sign-in")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "branding/Logo_LC-128" in html, "Logo prominente no aparece en login"


def test_favicon_referenciado_en_base_html(client):
    """El `<link rel="icon">` apunta al logo en ambos tamaños."""
    resp = client.get("/sign-in")
    html = resp.content.decode()
    assert 'rel="icon"' in html
    assert "Logo_LC-32.png" in html
    assert 'rel="apple-touch-icon"' in html


def test_manifest_json_tiene_logos_y_brand_color():
    """Ambos manifests (Taller + Gerencia) usan Logo_LC y theme_color brand."""
    for app in ("el-taller", "la-gerencia"):
        path = RAIZ / app / "static" / "manifest.json"
        data = json.loads(path.read_text())
        assert data["theme_color"] == "#465fff", f"{app} manifest theme_color"
        assert data["background_color"] == "#465fff", f"{app} manifest background_color"
        assert all(
            "branding/Logo_LC" in icon["src"] for icon in data["icons"]
        ), f"{app} manifest icons"
        sizes = {icon["sizes"] for icon in data["icons"]}
        assert "192x192" in sizes
        assert "512x512" in sizes


def test_errores_incluyen_logo():
    """Los partials `_404_body.html` / `_500_body.html` cargan el logo."""
    for app in ("el-taller", "la-gerencia"):
        for nombre in ("_404_body.html", "_500_body.html"):
            path = RAIZ / app / "templates" / "errores" / nombre
            contenido = path.read_text()
            assert "branding/Logo_LC" in contenido, f"{app}/{nombre} sin logo"
            assert "{% load static %}" in contenido, f"{app}/{nombre} sin load static"


def test_version_aparece_en_footer(client, usuario_factory):
    """Control de versiones discreto en el footer (lib/version.py)."""
    from lib.version import VERSION

    u = usuario_factory(rol="dueno")
    client.force_login(u)
    html = client.get("/").content.decode()
    assert f"v{VERSION}" in html, "La versión no aparece en el footer"
