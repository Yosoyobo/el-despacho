"""Hotfix Pre-S2b.2: ver tests/taller/test_no_renderiza_comentarios.py.

Espejo en Gerencia. Cubre tanto `/` como sweep estático de templates.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_no_renderiza_comentarios_django_en_sidebar_gerencia(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "{#" not in body, "Comentario Django sin cerrar renderizado como texto (Gerencia /)"
    assert "#}" not in body, "Cierre de comentario Django renderizado como texto (Gerencia /)"


def test_no_hay_comentarios_django_multilinea_en_templates_gerencia():
    """Sweep estático del filesystem para los templates de La Gerencia."""
    roots = [
        REPO_ROOT / "la-gerencia" / "templates",
        REPO_ROOT / "la-gerencia" / "apps",
    ]
    patron_abre = re.compile(r"\{#[^\n]*$", re.MULTILINE)
    fallas: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for ruta in root.rglob("*.html"):
            texto = ruta.read_text(encoding="utf-8", errors="ignore")
            limpio = re.sub(r"\{#[^\n]*?#\}", "", texto)
            if patron_abre.search(limpio):
                fallas.append(str(ruta.relative_to(REPO_ROOT)))
    assert not fallas, (
        "Comentarios Django {# ... #} multilínea encontrados (usar {% comment %}):\n"
        + "\n".join(f"  - {f}" for f in fallas)
    )
