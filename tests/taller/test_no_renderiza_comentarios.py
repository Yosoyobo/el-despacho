"""Hotfix Pre-S2b.2: comentarios Django multilínea no deben renderizar como texto.

Django `{# ... #}` es single-line only. Bloques multilínea con esa sintaxis
hacen que la primera línea desaparezca y el resto aparezca como texto literal
en la UI. Para multilínea va `{% comment %}...{% endcomment %}`. Este test
atrapa la regresión antes de que llegue a producción.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_no_renderiza_comentarios_django_en_sala_juntas(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "{#" not in body, "Comentario Django sin cerrar renderizado como texto (Taller /)"
    assert "#}" not in body, "Cierre de comentario Django renderizado como texto (Taller /)"


def _templates_con_comentario_multilinea(roots: list[Path]) -> list[str]:
    """Devuelve lista de paths con `{# … #}` que cruzan saltos de línea."""
    fallas: list[str] = []
    # Regex: abre {# y NO cierra #} antes del primer \n.
    patron = re.compile(r"\{#[^\n]*$", re.MULTILINE)
    for root in roots:
        if not root.exists():
            continue
        for ruta in root.rglob("*.html"):
            texto = ruta.read_text(encoding="utf-8", errors="ignore")
            # Quitamos primero los cerrados en una línea para no falsear.
            limpio = re.sub(r"\{#[^\n]*?#\}", "", texto)
            if patron.search(limpio):
                fallas.append(str(ruta.relative_to(REPO_ROOT)))
    return fallas


def test_no_hay_comentarios_django_multilinea_en_templates_taller():
    """Sweep estático del filesystem: ningún `{# … #}` puede cruzar líneas.

    Cubre TODOS los templates del Taller + apps shared del raíz. Atrapa el
    bug antes de que se renderice en cualquier ruta (la versión por-ruta
    sólo cubre `/`).
    """
    roots = [
        REPO_ROOT / "el-taller" / "templates",
        REPO_ROOT / "el-taller" / "apps",  # templates app-locales
        # Apps shared raíz
        REPO_ROOT / "referencias",
        REPO_ROOT / "chalanes",
        REPO_ROOT / "buzon",
        REPO_ROOT / "interfono",
        REPO_ROOT / "auth_google",
        REPO_ROOT / "proximamente",
    ]
    fallas = _templates_con_comentario_multilinea(roots)
    assert not fallas, (
        "Comentarios Django {# ... #} multilínea encontrados (usar {% comment %}):\n"
        + "\n".join(f"  - {f}" for f in fallas)
    )
