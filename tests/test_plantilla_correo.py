"""PlantillaCorreo (cuerpo/asunto editables) + IA de redacción (El Chalán)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.django_db


def test_obtener_seedea_default():
    from ajustes.models import PlantillaCorreo
    pl = PlantillaCorreo.obtener("cotizacion")
    assert pl.slug == "cotizacion"
    assert "{{ codigo }}" in pl.cuerpo_html


def test_render_rellena_variables():
    from ajustes.models import PlantillaCorreo
    pl = PlantillaCorreo.obtener("factura")
    asunto, cuerpo = pl.render({
        "codigo": "FAC-2026-0001", "titulo": "Servicios", "cliente": "ACME",
        "total": "$1,160.00", "moneda": "MXN", "vencimiento": "30/06/2026",
        "fecha_emision": "01/06/2026", "notas": "",
    })
    assert "FAC-2026-0001" in asunto
    assert "ACME" in cuerpo
    assert "$1,160.00" in cuerpo
    assert "{{" not in cuerpo  # todas las variables resueltas


def test_render_plantilla_vacia_usa_default():
    from ajustes.models import PlantillaCorreo
    pl = PlantillaCorreo.obtener("cotizacion")
    pl.cuerpo_html = ""  # vacía → cae al default
    pl.asunto = ""
    asunto, cuerpo = pl.render({"codigo": "COT-1", "titulo": "x", "cliente": "C",
                                "total": "$0", "moneda": "MXN", "fecha_validez": "",
                                "notas": ""})
    assert "COT-1" in asunto
    assert "C" in cuerpo


def test_render_plantilla_rota_no_lanza():
    from ajustes.models import PlantillaCorreo
    pl = PlantillaCorreo.obtener("generico")
    pl.cuerpo_html = "{% if %}roto"  # sintaxis inválida
    asunto, cuerpo = pl.render({"cliente": "C", "asunto": "Hola", "mensaje": "Hi"})
    # No revienta: cae al default del slot.
    assert isinstance(cuerpo, str)


# ── IA de redacción ───────────────────────────────────────────────────────

def _fake_analizar(texto):
    return lambda estacion, prompt, **kw: SimpleNamespace(
        texto=texto, provider="anthropic", modelo="claude-haiku-4-5",
        prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1)


def test_redactar_intencion_vacia_falla():
    from lib import cartero_ia
    res = cartero_ia.redactar(intencion="", html_actual="", variables=[])
    assert res["ok"] is False


def test_redactar_limpia_fences_y_scripts(monkeypatch):
    import lib.analistas as la
    from lib import cartero_ia
    sucio = "```html\n<p>Hola {{ codigo }}</p><script>alert(1)</script>\n```"
    monkeypatch.setattr(la, "analizar", _fake_analizar(sucio))
    res = cartero_ia.redactar(intencion="mejóralo", html_actual="<p>x</p>",
                              variables=["codigo"])
    assert res["ok"]
    assert "<script>" not in res["html"]
    assert "```" not in res["html"]
    assert "{{ codigo }}" in res["html"]


def test_redactar_llm_caido_no_lanza(monkeypatch):
    import lib.analistas as la
    from lib import cartero_ia
    monkeypatch.setattr(la, "analizar",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("caído")))
    res = cartero_ia.redactar(intencion="x", html_actual="", variables=[])
    assert res["ok"] is False
    assert "Chalán" in res["error"]
