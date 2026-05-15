"""lib.site.registry — el dispatcher de chequeos."""

from __future__ import annotations


def test_plataformas_registradas():
    from lib.site.registry import PLATAFORMAS
    assert "anthropic" in PLATAFORMAS
    assert "openai" in PLATAFORMAS
    assert "do_api" in PLATAFORMAS
    assert "postgres" in PLATAFORMAS
    assert "redis" in PLATAFORMAS
    assert "docker" in PLATAFORMAS
    assert "tailscale" in PLATAFORMAS
    assert "n8n_tailscale" in PLATAFORMAS
    assert len(PLATAFORMAS) >= 8


def test_chequear_desconocida():
    from lib.site.registry import chequear
    r = chequear("plataforma_inexistente_xyz")
    assert r["estado"] == "error"
    assert "desconocida" in r["mensaje_error"]


def test_chequear_envuelve_excepciones(monkeypatch):
    from lib.site import registry

    def boom():
        raise RuntimeError("explotó")

    monkeypatch.setitem(registry.PLATAFORMAS, "rota", boom)
    r = registry.chequear("rota")
    assert r["estado"] == "error"
    assert "explotó" in r["mensaje_error"]
    assert r["latencia_ms"] is None


def test_chequear_normaliza_dict(monkeypatch):
    from lib.site import registry

    monkeypatch.setitem(registry.PLATAFORMAS, "fake_ok", lambda: {"estado": "ok"})
    r = registry.chequear("fake_ok")
    assert r["estado"] == "ok"
    # Normaliza: presencia de keys
    assert "latencia_ms" in r
    assert "mensaje_error" in r


def test_chequear_todas_estructura(monkeypatch):
    from lib.site import registry
    # Reemplazar todas con stubs rápidos
    nuevas = {p: (lambda p=p: {"estado": "no_configurada"}) for p in registry.PLATAFORMAS}
    monkeypatch.setattr(registry, "PLATAFORMAS", nuevas)
    r = registry.chequear_todas()
    assert set(r.keys()) == set(nuevas.keys())
    assert all(v["estado"] == "no_configurada" for v in r.values())
