"""Hotfix Pre-S2b.2: comentarios Django multilínea no deben renderizar como texto.

Django `{# ... #}` es single-line only. Bloques multilínea con esa sintaxis
hacen que la primera línea desaparezca y el resto aparezca como texto literal
en la UI. Para multilínea va `{% comment %}...{% endcomment %}`. Este test
atrapa la regresión antes de que llegue a producción.
"""

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_no_renderiza_comentarios_django_en_sala_juntas(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "{#" not in body, "Comentario Django sin cerrar renderizado como texto (Taller /)"
    assert "#}" not in body, "Cierre de comentario Django renderizado como texto (Taller /)"
