"""lib.site.contenedores — fallback cuando no hay docker.sock."""

from __future__ import annotations


def test_disponible_falso(monkeypatch):
    monkeypatch.setenv("SITE_DOCKER_SOCK", "/no/existe/docker.sock")
    import importlib

    from lib.site import contenedores
    importlib.reload(contenedores)
    assert contenedores.disponible() is False
    assert contenedores.info() == {"disponible": False}
    assert contenedores.listar() == []


def test_snapshot_estructura(monkeypatch):
    monkeypatch.setenv("SITE_DOCKER_SOCK", "/no/existe/docker.sock")
    import importlib

    from lib.site import contenedores
    importlib.reload(contenedores)
    r = contenedores.snapshot()
    assert "info" in r
    assert "containers" in r
    assert r["info"] == {"disponible": False}
