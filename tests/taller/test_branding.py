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
    """El `<link rel="icon">` apunta al ícono de app (fondo de color de marca)."""
    resp = client.get("/sign-in")
    html = resp.content.decode()
    assert 'rel="icon"' in html
    assert "Icono_LC-32.png" in html
    assert 'rel="apple-touch-icon"' in html


# Color de marca del ícono/PWA por app (debe coincidir con
# infra/scripts/generar_logos.py::COLOR_ICONO y los <meta name="theme-color">).
COLOR_MARCA_POR_APP = {
    "el-taller": "#465fff",    # azul brand
    "la-gerencia": "#3E9E4F",  # verde Learning Center
}


def test_manifest_json_tiene_icono_y_color_por_app():
    """Cada manifest usa Icono_LC y su color de marca propio (Taller azul, Gerencia verde)."""
    for app, color in COLOR_MARCA_POR_APP.items():
        path = RAIZ / app / "static" / "manifest.json"
        data = json.loads(path.read_text())
        assert data["theme_color"] == color, f"{app} manifest theme_color"
        assert data["background_color"] == color, f"{app} manifest background_color"
        assert all(
            "branding/Icono_LC" in icon["src"] for icon in data["icons"]
        ), f"{app} manifest icons"
        sizes = {icon["sizes"] for icon in data["icons"]}
        assert "192x192" in sizes
        assert "512x512" in sizes


def test_iconos_de_app_existen_por_tamano():
    """Los íconos de app coloreados se generaron para favicon + PWA."""
    for app in COLOR_MARCA_POR_APP:
        destino = RAIZ / app / "static" / "branding"
        for size in (32, 64, 192, 512):
            assert (destino / f"Icono_LC-{size}.png").exists(), f"{app} Icono_LC-{size}"


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
