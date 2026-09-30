"""Los Antojos — easter egg de los campos de texto (no se documenta en Novedades)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parents[2]


def test_el_taller_carga_los_antojos(client, usuario_factory):
    # El archivo tiene que existir: un {% static %} a un archivo ausente es 500 en prod.
    assert (RAIZ / "el-taller/static/js/antojos.js").is_file()
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "js/antojos.js" in resp.content.decode()
