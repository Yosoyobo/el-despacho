"""S-Chalan-Aprende-V1 — El Chalán destila aprendizajes de su historial.

Mockean `lib.analistas.analizar` para no pegarle a un LLM. Verifican:
recolección priorizando señales de corrección, dry-run sin escribir,
creación de propuestas INACTIVAS (`origen='chalan_destilado'`), dedup por
frase normalizada, y degradación cuando la IA cae o el usuario está topado.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── helpers ──────────────────────────────────────────────────────────


def _res_ia(payload: dict):
    return SimpleNamespace(
        texto=json.dumps(payload), provider="anthropic", modelo="claude-sonnet-4-6",
        prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1,
    )


def _mock_ia(monkeypatch, payload: dict):
    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", lambda *a, **k: _res_ia(payload))


def _dictado(autor, texto, *, estado="aplicado", clarificaciones=None, interpretacion=None):
    from apps.el_dictado.models import Dictado
    return Dictado.objects.create(
        autor=autor, texto_crudo=texto, estado=estado,
        historial_clarificaciones=clarificaciones or [],
        interpretacion_raw=interpretacion or {},
    )


def _dos_aprendizajes():
    return {"aprendizajes": [
        {"frase_o_patron": "la heladería", "interpretacion_correcta": "$heladeria-michoacana (cliente)",
         "peso": 1.2, "razon": "el usuario lo corrigió dos veces"},
        {"frase_o_patron": "el chofer", "interpretacion_correcta": "asignar runner más cercano",
         "peso": 1.0, "razon": "desmarcó la tarea genérica"},
    ]}


# ── recolección ──────────────────────────────────────────────────────


def test_recolectar_prioriza_correcciones(usuario_factory):
    from apps.el_dictado.destilar import recolectar_evidencia
    from apps.el_dictado.models import DictadoAccion

    u = usuario_factory(rol="super_admin")
    # 1) dictado con clarificación (señal fuerte)
    _dictado(u, "haz lo de la heladería", clarificaciones=[
        {"pregunta": "¿cuál heladería?", "respuesta": "$heladeria-michoacana"}])
    # 2) dictado con acción desmarcada (señal fuerte)
    d2 = _dictado(u, "manda al chofer por el material", estado="confirmado_parcial")
    DictadoAccion.objects.create(dictado=d2, orden=0, tipo="crear_tarea",
                                 descripcion="tarea genérica", payload={}, confirmada=False)
    # 3) dictado plano sin señal
    _dictado(u, "crea el proyecto del catálogo")

    ev = recolectar_evidencia(dias=30, limite=60)
    assert len(ev) == 3
    # Las señales de corrección van primero.
    assert "la heladería" in ev[0]["texto"] or "chofer" in ev[0]["texto"]
    por_id = {e["id"]: e for e in ev}
    assert por_id[d2.pk]["desmarcadas"]  # captó la acción desmarcada
    con_clarif = [e for e in ev if e["clarificaciones"]]
    assert con_clarif and "corrigió" in con_clarif[0]["clarificaciones"][0]


def test_sin_evidencia_no_llama_ia(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar import destilar_aprendizajes

    import lib.analistas as la
    # Si llegara a llamar a la IA, esto reventaría el test.
    monkeypatch.setattr(la, "analizar", lambda *a, **k: pytest.fail("no debió llamar IA"))
    usuario_factory(rol="super_admin")  # sin dictados
    r = destilar_aprendizajes(dias=30)
    assert r["ok"] and r["analizados"] == 0 and r["creados"] == 0
    assert r["motivo"] == "sin_evidencia"


# ── destilado ────────────────────────────────────────────────────────


def test_dry_run_no_persiste(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar import destilar_aprendizajes
    from apps.el_dictado.models import DictadoAprendizaje

    u = usuario_factory(rol="super_admin")
    _dictado(u, "lo de la heladería", clarificaciones=[
        {"pregunta": "¿cuál?", "respuesta": "michoacana"}])
    _mock_ia(monkeypatch, _dos_aprendizajes())

    r = destilar_aprendizajes(dias=30, dry_run=True, creado_por=u)
    assert r["ok"] and len(r["candidatos"]) == 2 and r["creados"] == 0
    assert DictadoAprendizaje.objects.count() == 0  # nada escrito


def test_crea_propuestas_inactivas(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar import destilar_aprendizajes
    from apps.el_dictado.models import DictadoAprendizaje

    u = usuario_factory(rol="super_admin")
    _dictado(u, "lo de la heladería", clarificaciones=[
        {"pregunta": "¿cuál?", "respuesta": "michoacana"}])
    _mock_ia(monkeypatch, _dos_aprendizajes())

    r = destilar_aprendizajes(dias=30, creado_por=u)
    assert r["ok"] and r["creados"] == 2
    creados = DictadoAprendizaje.objects.all()
    assert creados.count() == 2
    for ap in creados:
        assert ap.activo is False                # nace inactivo → revisión
        assert ap.origen == "chalan_destilado"
        assert ap.peso_efectivo() == 0.0         # inactivo no se inyecta


def test_dedup_no_repropone_frase_existente(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar import destilar_aprendizajes
    from apps.el_dictado.models import DictadoAprendizaje

    u = usuario_factory(rol="super_admin")
    # Ya existe "la heladería" (incluso con otra capitalización).
    DictadoAprendizaje.objects.create(
        frase_o_patron="La Heladería", interpretacion_correcta="x", activo=True)
    _dictado(u, "haz lo de la heladería", clarificaciones=[
        {"pregunta": "¿cuál?", "respuesta": "michoacana"}])
    _mock_ia(monkeypatch, _dos_aprendizajes())

    r = destilar_aprendizajes(dias=30, creado_por=u)
    # "la heladería" se filtra (ya existe); solo "el chofer" se propone.
    assert r["creados"] == 1
    frases = set(DictadoAprendizaje.objects.values_list("frase_o_patron", flat=True))
    assert "el chofer" in frases
    assert DictadoAprendizaje.objects.filter(origen="chalan_destilado").count() == 1


def test_ia_caida_no_crea_ni_revienta(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar import destilar_aprendizajes
    from apps.el_dictado.models import DictadoAprendizaje

    import lib.analistas as la

    u = usuario_factory(rol="super_admin")
    _dictado(u, "lo de la heladería", clarificaciones=[{"pregunta": "x", "respuesta": "y"}])

    def _boom(*a, **k):
        raise RuntimeError("todos los chalanes caídos")
    monkeypatch.setattr(la, "analizar", _boom)

    r = destilar_aprendizajes(dias=30, creado_por=u)
    assert r["ok"] is False and r["motivo"] == "fallo_ia" and r["creados"] == 0
    assert DictadoAprendizaje.objects.count() == 0


def test_presupuesto_topado_degrada(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar import destilar_aprendizajes

    import lib.analistas as la
    from lib.analistas import PresupuestoIAExcedido

    u = usuario_factory(rol="super_admin")
    _dictado(u, "lo de la heladería", clarificaciones=[{"pregunta": "x", "respuesta": "y"}])

    def _topado(*a, **k):
        raise PresupuestoIAExcedido("topado")
    monkeypatch.setattr(la, "analizar", _topado)

    r = destilar_aprendizajes(dias=30, creado_por=u)
    assert r["ok"] is False and r["motivo"] == "presupuesto_topado" and r["creados"] == 0


def test_json_invalido_no_crea(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar import destilar_aprendizajes
    from apps.el_dictado.models import DictadoAprendizaje

    import lib.analistas as la

    u = usuario_factory(rol="super_admin")
    _dictado(u, "lo de la heladería", clarificaciones=[{"pregunta": "x", "respuesta": "y"}])
    monkeypatch.setattr(la, "analizar", lambda *a, **k: SimpleNamespace(
        texto="esto no es json", provider="anthropic"))

    r = destilar_aprendizajes(dias=30, creado_por=u)
    assert r["ok"] is False and r["motivo"] == "json_invalido"
    assert DictadoAprendizaje.objects.count() == 0
