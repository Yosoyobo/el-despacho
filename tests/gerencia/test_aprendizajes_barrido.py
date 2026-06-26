"""S-Chalan-Aprende-Boton — botón de "barrido" en La Gerencia → Chalanes.

Cierra la deuda de S-Chalan-Aprende-V1: el super_admin puede forzar AHORA un
destilado de aprendizajes desde la UI (antes solo corría por cron). El puente
cross-app es `chalanes.destilar` leyendo vía shadow models `managed=False`
(`chalanes.Dictado` / `DictadoAccion`) — Gerencia no instala `apps.el_dictado`.

Mockean `lib.analistas.analizar` para no pegarle a un LLM.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]

URL = "/chalanes/aprendizajes/barrido"


def _res_ia(payload: dict):
    return SimpleNamespace(
        texto=json.dumps(payload), provider="anthropic", modelo="claude-sonnet-4-6",
        prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1,
    )


def _mock_ia(monkeypatch, payload: dict):
    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", lambda *a, **k: _res_ia(payload))


def _dictado_con_correccion(autor):
    """Crea evidencia mínima: un dictado donde el usuario corrigió al Chalán."""
    from apps.el_dictado.models import Dictado
    return Dictado.objects.create(
        autor=autor, texto_crudo="haz lo de la heladería", estado="aplicado",
        historial_clarificaciones=[{"pregunta": "¿cuál?", "respuesta": "$heladeria-michoacana"}],
    )


def _payload_un_aprendizaje():
    return {"aprendizajes": [{
        "frase_o_patron": "la heladería",
        "interpretacion_correcta": "$heladeria-michoacana (cliente)",
        "peso": 1.2, "razon": "el usuario lo corrigió",
    }]}


def test_barrido_crea_propuesta_inactiva_y_redirige(client, monkeypatch, usuario_factory):
    from chalanes.models import Aprendizaje

    Aprendizaje.objects.all().delete()  # tabla compartida managed=False — partir limpio
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    _dictado_con_correccion(u)
    _mock_ia(monkeypatch, _payload_un_aprendizaje())

    resp = client.post(URL)
    assert resp.status_code == 302
    assert "filtro=propuestos" in resp["Location"]

    propuesta = Aprendizaje.objects.get(frase_o_patron="la heladería")
    assert propuesta.activo is False                  # nace inactiva → revisión
    assert propuesta.origen == "chalan_destilado"
    assert propuesta.autor_id == u.pk


def test_barrido_sin_evidencia_no_llama_ia(client, monkeypatch, usuario_factory):
    from chalanes.models import Aprendizaje

    Aprendizaje.objects.all().delete()
    u = usuario_factory(rol="super_admin")
    client.force_login(u)

    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", lambda *a, **k: pytest.fail("no debió llamar IA"))

    # Sin dictados recientes del usuario → sin evidencia, no crea nada.
    resp = client.post(URL)
    assert resp.status_code == 302
    assert Aprendizaje.objects.filter(origen="chalan_destilado").count() == 0


def test_barrido_get_no_permitido(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get(URL)
    assert resp.status_code == 405  # require_POST


def test_barrido_bloqueado_para_disenador(client, monkeypatch, usuario_factory):
    from chalanes.models import Aprendizaje

    Aprendizaje.objects.all().delete()
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    _dictado_con_correccion(u)
    # Si llegara a destilar, esto reventaría.
    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", lambda *a, **k: pytest.fail("disenador no debe destilar"))

    resp = client.post(URL)
    assert resp.status_code in (302, 403)
    assert Aprendizaje.objects.filter(origen="chalan_destilado").count() == 0


def test_boton_visible_en_panel_para_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/chalanes/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "aprendizajes/barrido" in body
    assert "Aprender de mi historial ahora" in body


def test_boton_oculto_para_dueno(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get("/chalanes/")
    assert resp.status_code == 200
    assert "aprendizajes/barrido" not in resp.content.decode()
