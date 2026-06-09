"""Widget AI 🤖 — lib.redactor_ia + endpoint /chalan/redactar (S-Chalanes-UX #2).

Mockean `lib.analistas.analizar` para no pegarle a un LLM real.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _ns(texto: str):
    return SimpleNamespace(
        texto=texto, provider="anthropic", modelo="claude-haiku-4-5",
        prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1,
    )


def test_redactar_sin_instruccion_falla():
    from lib.redactor_ia import redactar
    r = redactar(instruccion="", texto_actual="hola")
    assert r["ok"] is False
    assert "Escribe" in r["error"]


def test_redactar_limpia_fences_y_html(monkeypatch):
    import lib.analistas as la
    monkeypatch.setattr(la, "analizar",
                        lambda **kw: _ns("```\n<b>Hola</b> @oscar, listo.\n```"))
    from lib.redactor_ia import redactar
    r = redactar(instruccion="saluda a @oscar")
    assert r["ok"] is True
    assert "```" not in r["texto"]
    assert "<b>" not in r["texto"]
    assert "@oscar" in r["texto"]  # preserva la referencia


def test_redactar_llm_caido_es_gracioso(monkeypatch):
    import lib.analistas as la

    def _boom(**kw):
        raise RuntimeError("sin red")
    monkeypatch.setattr(la, "analizar", _boom)
    from lib.redactor_ia import redactar
    r = redactar(instruccion="algo")
    assert r["ok"] is False
    assert "no respondió" in r["error"]


def test_bloque_referencias_resuelve_proyecto(usuario_factory, proyecto_factory):
    from lib.redactor_ia import bloque_referencias
    p = proyecto_factory()
    bloque = bloque_referencias(f"avance de #{p.slug}")
    assert "REFERENCIAS RESUELTAS" in bloque
    assert p.codigo in bloque


def test_endpoint_redactar_ok(client, monkeypatch, usuario_factory, proyecto_factory):
    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", lambda **kw: _ns("Avance del proyecto, todo en orden."))
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    client.force_login(admin)
    resp = client.post("/chalan/redactar", {
        "instruccion": "redacta el avance",
        "texto_actual": f"#{p.slug}",
        "contexto_modelo": "comentario_proyecto",
        "contexto_id": str(p.pk),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "Avance" in data["texto"]


def test_endpoint_redactar_requiere_chalan(client, monkeypatch, usuario_factory):
    """Si el usuario no tiene permiso (chalan, usar) → 403."""
    from apps.el_dictado import views_redactor
    monkeypatch.setattr(views_redactor, "puede", lambda u, m, a: False)
    user = usuario_factory(rol="disenador")
    client.force_login(user)
    resp = client.post("/chalan/redactar", {"instruccion": "x"})
    assert resp.status_code == 403


def test_endpoint_redactar_solo_post(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/chalan/redactar")
    assert resp.status_code == 405
