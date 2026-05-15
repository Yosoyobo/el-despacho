"""Los Analistas — adapters + reemplazo + log. httpx mockeado."""

from __future__ import annotations

from unittest.mock import patch

import httpx  # noqa: F401  (asegura módulo cargado para patch)
import pytest

from lib.analistas.adapters.anthropic import AnthropicAdapter
from lib.analistas.adapters.openai import OpenAIAdapter
from lib.analistas.base import (
    ErrorPermanente,
    ErrorTransitorio,
    FaltaCredencial,
    Resultado,
)
from lib.analistas.reemplazo import TodosLosAnalistasFallaron, analizar


class _RespFalsa:
    def __init__(self, status: int, payload: dict | None = None, text: str = ""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _anthropic_payload(texto: str = "ok", input_tokens: int = 5, output_tokens: int = 2):
    return {
        "model": "claude-haiku-4-5",
        "content": [{"type": "text", "text": texto}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def _openai_payload(texto: str = "ok", pt: int = 5, ct: int = 2):
    return {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"role": "assistant", "content": texto}}],
        "usage": {"prompt_tokens": pt, "completion_tokens": ct},
    }


@pytest.fixture
def credenciales_dummy(db):
    """Inserta llaves dummy en Los Ajustes (cifradas con Bóveda) para que los
    adapters no aborten con FaltaCredencial."""
    from ajustes.models.credencial import Credencial
    Credencial.guardar("anthropic_api_key", "sk-ant-test-xxxx")
    Credencial.guardar("openai_api_key", "sk-test-xxxx")


@pytest.mark.django_db
class TestAdaptersUnitarios:

    def test_anthropic_sin_credencial_lanza_falta(self, db):
        # Sin guardar la llave
        with pytest.raises(FaltaCredencial):
            AnthropicAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_anthropic_200_devuelve_resultado(self, credenciales_dummy):
        with patch("httpx.post",
                   return_value=_RespFalsa(200, _anthropic_payload("ok"))):
            res = AnthropicAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)
        assert res.texto == "ok"
        assert res.provider == "anthropic"
        assert res.prompt_tokens == 5
        assert res.completion_tokens == 2
        assert res.costo_usd > 0

    def test_anthropic_401_es_permanente(self, credenciales_dummy):
        with patch("httpx.post",
                   return_value=_RespFalsa(401, text="bad key")):
            with pytest.raises(ErrorPermanente):
                AnthropicAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_anthropic_429_es_transitorio(self, credenciales_dummy):
        with patch("httpx.post",
                   return_value=_RespFalsa(429, text="rate")):
            with pytest.raises(ErrorTransitorio):
                AnthropicAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_anthropic_500_es_transitorio(self, credenciales_dummy):
        with patch("httpx.post",
                   return_value=_RespFalsa(503, text="upstream")):
            with pytest.raises(ErrorTransitorio):
                AnthropicAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_openai_200_devuelve_resultado(self, credenciales_dummy):
        with patch("httpx.post",
                   return_value=_RespFalsa(200, _openai_payload("ok"))):
            res = OpenAIAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)
        assert res.texto == "ok"
        assert res.provider == "openai"


def _post_routed(*, anthropic_resp, openai_resp):
    """side_effect que despacha según URL al adapter correcto."""
    def _post(url, *a, **kw):
        if "anthropic" in url:
            return anthropic_resp
        if "openai" in url:
            return openai_resp
        raise RuntimeError(f"URL no esperada: {url}")
    return _post


@pytest.mark.django_db
class TestCadenaReemplazo:

    def test_anthropic_ok_no_intenta_openai(self, credenciales_dummy):
        from ajustes.models import AnalistaLog

        with patch("httpx.post", side_effect=_post_routed(
            anthropic_resp=_RespFalsa(200, _anthropic_payload("hola")),
            openai_resp=_RespFalsa(500),
        )) as mock:
            res = analizar("cotizaciones", "prompt", max_tokens=5)
        assert res.provider == "anthropic"
        # Solo se llamó una vez (a anthropic) — openai no se intentó.
        assert mock.call_count == 1
        logs = list(AnalistaLog.objects.all())
        assert len(logs) == 1
        assert logs[0].exito is True
        assert logs[0].provider == "anthropic"
        # No persiste prompt en claro — solo hash sha256.
        assert len(logs[0].prompt_hash) == 64

    def test_anthropic_transitorio_cae_a_openai(self, credenciales_dummy):
        from ajustes.models import AnalistaLog

        with patch("httpx.post", side_effect=_post_routed(
            anthropic_resp=_RespFalsa(503),
            openai_resp=_RespFalsa(200, _openai_payload("ok")),
        )):
            res = analizar("cotizaciones", "prompt", max_tokens=5)
        assert res.provider == "openai"
        logs = list(AnalistaLog.objects.order_by("creado_en"))
        assert len(logs) == 2
        assert logs[0].exito is False and logs[0].provider == "anthropic"
        assert logs[1].exito is True and logs[1].provider == "openai"

    def test_anthropic_permanente_NO_intenta_openai(self, credenciales_dummy):
        with patch("httpx.post", side_effect=_post_routed(
            anthropic_resp=_RespFalsa(401),
            openai_resp=_RespFalsa(200, _openai_payload()),
        )) as mock:
            with pytest.raises(ErrorPermanente):
                analizar("cotizaciones", "prompt")
        assert mock.call_count == 1  # Solo se intentó anthropic.

    def test_ambos_transitorios_falla_cadena(self, credenciales_dummy):
        with patch("httpx.post", side_effect=_post_routed(
            anthropic_resp=_RespFalsa(503),
            openai_resp=_RespFalsa(503),
        )):
            with pytest.raises(TodosLosAnalistasFallaron):
                analizar("cotizaciones", "prompt")

    def test_falta_credencial_anthropic_cae_a_openai(self, db):
        from ajustes.models.credencial import Credencial
        Credencial.guardar("openai_api_key", "sk-test")
        # anthropic_api_key ausente — anthropic levanta FaltaCredencial sin hacer POST.
        with patch("httpx.post", side_effect=_post_routed(
            anthropic_resp=_RespFalsa(200, _anthropic_payload()),
            openai_resp=_RespFalsa(200, _openai_payload()),
        )):
            res = analizar("cotizaciones", "prompt")
        assert res.provider == "openai"


def test_hash_prompt_es_sha256():
    from lib.analistas.log import hash_prompt
    h = hash_prompt("hola")
    assert len(h) == 64
    assert hash_prompt("hola") == h  # determinista
    assert hash_prompt("hola2") != h
