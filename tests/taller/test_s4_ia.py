"""S4 — IA (Los Chalanes): redactar cotización (override de estación),
categorizar gasto, resumir actividad de proyecto, sugerir precio.

Mockea `lib.analistas.analizar` con respuestas canned (mismo patrón que
test_ocr_recibo). No le pega a un LLM real.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _res(texto):
    return SimpleNamespace(
        texto=texto, provider="anthropic", modelo="claude-haiku-4-5",
        prompt_tokens=10, completion_tokens=5, costo_usd=0.0, latencia_ms=50,
    )


# ── A0: migración 0011 seedea las 4 estaciones ──────────────────────────────

def test_estaciones_s4_seedeadas():
    from chalanes.models import CuadroChalanes
    for est in ("cotizaciones", "gastos", "comunicacion", "precio"):
        assert CuadroChalanes.objects.filter(estacion=est).exists(), est


# ── A1: redactar cotización (override de estación, allowlist server-side) ────

def test_redactar_override_cotizaciones(monkeypatch):
    import lib.analistas as la
    from lib.redactor_ia import redactar
    capturado = {}

    def fake(estacion, prompt, **kw):
        capturado["estacion"] = estacion
        return _res("Términos: 50% anticipo, saldo contra entrega.")
    monkeypatch.setattr(la, "analizar", fake)
    out = redactar(instruccion="redacta los términos de pago", estacion="cotizaciones")
    assert out["ok"]
    assert capturado["estacion"] == "cotizaciones"


def test_redactar_estacion_arbitraria_cae_a_default(monkeypatch):
    import lib.analistas as la
    from lib.redactor_ia import redactar
    capturado = {}

    def fake(estacion, prompt, **kw):
        capturado["estacion"] = estacion
        return _res("texto")
    monkeypatch.setattr(la, "analizar", fake)
    out = redactar(instruccion="hola", estacion="estacion-inyectada")
    assert out["ok"]
    assert capturado["estacion"] == "redaccion_asistida"


# ── A2: categorizar gasto ───────────────────────────────────────────────────

def test_categorizar_gasto_happy(monkeypatch):
    from apps.tesoreria.categorizador_ia import sugerir_categoria
    from apps.tesoreria.models import CentroDeCosto

    import lib.analistas as la
    centro = CentroDeCosto.objects.filter(activo=True).first()
    assert centro is not None  # seedeados por migración 0002
    monkeypatch.setattr(la, "analizar", lambda estacion, prompt, **kw: _res(
        '{"centro_de_costo_slug": "' + centro.slug + '", "confianza": 0.9}'))
    out = sugerir_categoria(descripcion="compra de papelería para la oficina")
    assert out["ok"] and out["centro_de_costo_id"] == centro.pk


def test_categorizar_gasto_slug_inexistente(monkeypatch):
    from apps.tesoreria.categorizador_ia import sugerir_categoria

    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", lambda estacion, prompt, **kw: _res(
        '{"centro_de_costo_slug": "no-existe-xyz", "confianza": 0.9}'))
    out = sugerir_categoria(descripcion="algo raro")
    assert out["ok"] and out["centro_de_costo_id"] is None


def test_categorizar_gasto_confianza_baja(monkeypatch):
    from apps.tesoreria.categorizador_ia import sugerir_categoria
    from apps.tesoreria.models import CentroDeCosto

    import lib.analistas as la
    centro = CentroDeCosto.objects.filter(activo=True).first()
    monkeypatch.setattr(la, "analizar", lambda estacion, prompt, **kw: _res(
        '{"centro_de_costo_slug": "' + centro.slug + '", "confianza": 0.1}'))
    out = sugerir_categoria(descripcion="algo")
    assert out["ok"] and out["centro_de_costo_id"] is None


def test_categorizar_gasto_llm_caido(monkeypatch):
    from apps.tesoreria.categorizador_ia import sugerir_categoria

    import lib.analistas as la

    def boom(*a, **k):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(la, "analizar", boom)
    out = sugerir_categoria(descripcion="algo")
    assert out["ok"] is False and out["error"]


def test_categorizar_gasto_descripcion_vacia():
    from apps.tesoreria.categorizador_ia import sugerir_categoria
    out = sugerir_categoria(descripcion="   ")
    assert out["ok"] is False


# ── A4: sugerir precio ──────────────────────────────────────────────────────

def _servicio():
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat = CategoriaServicio.objects.first()  # seedeadas por migración
    return Servicio.objects.create(nombre="Playera bordada", precio_base=200, costo=80, categoria=cat)


def test_sugerir_precio_happy(monkeypatch):
    from apps.cotizaciones.precio_ia import sugerir_precio

    import lib.analistas as la
    s = _servicio()
    monkeypatch.setattr(la, "analizar", lambda estacion, prompt, **kw: _res(
        '{"precio_minimo": 180, "precio_maximo": 250, "justificacion": "rango usual", "confianza": 0.8}'))
    out = sugerir_precio(servicio_id=s.pk, usuario=None)
    assert out["ok"] and out["precio_minimo"] == 180.0 and out["precio_maximo"] == 250.0


def test_sugerir_precio_servicio_inexistente():
    from apps.cotizaciones.precio_ia import sugerir_precio
    out = sugerir_precio(servicio_id=999999, usuario=None)
    assert out["ok"] is False


def test_sugerir_precio_json_malo(monkeypatch):
    from apps.cotizaciones.precio_ia import sugerir_precio

    import lib.analistas as la
    s = _servicio()
    monkeypatch.setattr(la, "analizar", lambda estacion, prompt, **kw: _res("no es json válido"))
    out = sugerir_precio(servicio_id=s.pk, usuario=None)
    assert out["ok"] is False


# ── A3: resumir actividad de proyecto ───────────────────────────────────────

def test_resumir_actividad_happy(monkeypatch, proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.resumen_ia import resumir_actividad

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    Tarea.objects.create(proyecto=p, titulo="Diseñar logo", creado_por=u)
    capturado = {}

    def fake(estacion, prompt, **kw):
        capturado["estacion"] = estacion
        capturado["prompt"] = prompt
        return _res("El proyecto avanza en la etapa de diseño.")
    monkeypatch.setattr(la, "analizar", fake)
    out = resumir_actividad(proyecto=p, usuario=u)
    assert out["ok"] and "avanza" in out["resumen"]
    assert capturado["estacion"] == "comunicacion"
    assert "Diseñar logo" in capturado["prompt"]  # las tareas entran al prompt


def test_resumir_actividad_llm_caido(monkeypatch, proyecto_factory, usuario_factory):
    from apps.los_proyectos.resumen_ia import resumir_actividad

    import lib.analistas as la

    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(la, "analizar", boom)
    out = resumir_actividad(
        proyecto=proyecto_factory(), usuario=usuario_factory(rol="super_admin"))
    assert out["ok"] is False
