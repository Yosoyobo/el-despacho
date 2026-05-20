"""S2b.2.1 — Clarificación iterativa del Dictado.

El usuario responde la pregunta del Chalán; el sistema re-interpreta el
mismo dictado pasando el historial de clarificaciones al prompt.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.django_db


def _mock_resultado(texto_json: str, *, provider: str = "anthropic", modelo: str = "claude-opus-4-7"):
    from lib.analistas.base import Resultado
    return Resultado(
        texto=texto_json, provider=provider, modelo=modelo,
        prompt_tokens=100, completion_tokens=200, costo_usd=0.001, latencia_ms=50,
    )


def _seed_cuadro():
    from ajustes.models.credencial import Credencial
    from chalanes.models import CuadroChalanes
    Credencial.guardar("chalan_anthropic_api_key", "sk-ant-test")
    CuadroChalanes.objects.update_or_create(
        estacion="dictado",
        defaults={"proveedor": "anthropic", "modelo": "claude-opus-4-7"},
    )


def test_responder_clarificacion_reusa_dictado_y_acumula_historial(client, usuario_factory):
    """El usuario responde la pregunta del Chalán: se reusa el mismo Dictado,
    se acumula el turno Q&A en `historial_clarificaciones`, y se vuelve a
    interpretar pasando ese historial al prompt."""
    _seed_cuadro()
    u = usuario_factory(rol="dueno")
    client.force_login(u)

    from apps.el_dictado.models import Dictado
    from apps.el_dictado.services import interpretar

    # Turno 1: Chalán pregunta.
    pregunta_json = json.dumps({
        "pregunta_clarificacion": "¿A cuál heladería te refieres?",
        "acciones": [],
    })
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(pregunta_json)
        dictado = interpretar(texto="cobra a la heladería", usuario=u)
    assert dictado.estado == "preguntando"
    pk = dictado.pk

    # Turno 2: usuario responde, Chalán ahora propone acciones.
    respuesta_json = json.dumps({
        "pregunta_clarificacion": None,
        "acciones": [
            {"tipo": "crear_recado", "descripcion": "Cobrar a Michoacana",
             "payload": {"destinatarios_slugs": ["x"], "cuerpo": "cobra"}, "confianza": 0.9},
        ],
    })
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(respuesta_json)
        resp = client.post(f"/dictado/{pk}/responder", {"respuesta": "la Michoacana del centro"})
    assert resp.status_code == 302

    # Mismo dictado, no creó uno nuevo.
    assert Dictado.objects.filter(autor=u).count() == 1
    dictado.refresh_from_db()
    assert dictado.estado == "esperando_confirmacion"
    assert dictado.pregunta_clarificacion == ""
    assert len(dictado.historial_clarificaciones) == 1
    assert dictado.historial_clarificaciones[0]["respuesta"] == "la Michoacana del centro"
    assert dictado.acciones.count() == 1


def test_responder_clarificacion_segundo_turno_si_chalan_insiste(client, usuario_factory):
    """Si el Chalán pregunta de nuevo, el historial acumula 2 turnos."""
    _seed_cuadro()
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    from apps.el_dictado.services import interpretar

    primera = json.dumps({"pregunta_clarificacion": "¿Cuál cliente?", "acciones": []})
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(primera)
        d = interpretar(texto="manda la cotización", usuario=u)

    # Turno 2 — sigue preguntando.
    segunda = json.dumps({"pregunta_clarificacion": "¿La cotización V2 o V3?", "acciones": []})
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(segunda)
        client.post(f"/dictado/{d.pk}/responder", {"respuesta": "a la Michoacana"})

    d.refresh_from_db()
    assert d.estado == "preguntando"
    assert d.pregunta_clarificacion == "¿La cotización V2 o V3?"
    assert len(d.historial_clarificaciones) == 1

    # Turno 3 — usuario aclara, Chalán resuelve.
    final = json.dumps({"pregunta_clarificacion": None, "acciones": []})
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(final)
        client.post(f"/dictado/{d.pk}/responder", {"respuesta": "la V3"})

    d.refresh_from_db()
    assert len(d.historial_clarificaciones) == 2
    assert d.historial_clarificaciones[1]["respuesta"] == "la V3"


def test_responder_sin_pregunta_es_rechazado(client, usuario_factory):
    _seed_cuadro()
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    from apps.el_dictado.models import Dictado
    d = Dictado.objects.create(autor=u, texto_crudo="x", estado="esperando_confirmacion")
    resp = client.post(f"/dictado/{d.pk}/responder", {"respuesta": "algo"})
    assert resp.status_code == 302
    d.refresh_from_db()
    assert len(d.historial_clarificaciones) == 0


def test_responder_vacio_no_acumula(client, usuario_factory):
    _seed_cuadro()
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    from apps.el_dictado.models import Dictado
    d = Dictado.objects.create(
        autor=u, texto_crudo="x", estado="preguntando",
        pregunta_clarificacion="¿cuál?",
    )
    resp = client.post(f"/dictado/{d.pk}/responder", {"respuesta": "   "})
    assert resp.status_code == 302
    d.refresh_from_db()
    assert d.estado == "preguntando"
    assert len(d.historial_clarificaciones) == 0


def test_historial_clarificaciones_se_inyecta_en_prompt(usuario_factory):
    """El user prompt incluye los turnos previos."""
    from apps.el_dictado.prompt import construir_user_prompt
    u = usuario_factory(rol="dueno")
    prompt = construir_user_prompt(
        usuario=u, texto_crudo="cobra a la heladería",
        historial=[{"pregunta": "¿cuál?", "respuesta": "Michoacana"}],
    )
    assert "[CLARIFICACIONES PREVIAS]" in prompt
    assert "Michoacana" in prompt
