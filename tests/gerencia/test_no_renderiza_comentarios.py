"""Hotfix Pre-S2b.2: ver tests/taller/test_no_renderiza_comentarios.py.

Espejo en Gerencia: el sidebar usa partial compartido (`_componentes_tailadmin/sidebar.html`,
patrón "dos copias sincronizadas"). Si la copia de Gerencia regresa al patrón
multilínea `{# ... \\n ... #}`, este test la atrapa.
"""

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_no_renderiza_comentarios_django_en_sidebar_gerencia(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "{#" not in body, "Comentario Django sin cerrar renderizado como texto (Gerencia /)"
    assert "#}" not in body, "Cierre de comentario Django renderizado como texto (Gerencia /)"
