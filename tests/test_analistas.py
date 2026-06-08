"""Los Analistas — adapters + reemplazo + log. httpx mockeado."""

from __future__ import annotations

from unittest.mock import patch

import httpx  # noqa: F401  (asegura módulo cargado para patch)
import pytest

from lib.analistas.adapters.anthropic import AnthropicAdapter
from lib.analistas.adapters.gemini import GeminiAdapter
from lib.analistas.adapters.mimo import MimoAdapter
from lib.analistas.adapters.openai import OpenAIAdapter
from lib.analistas.base import (
    ErrorPermanente,
    ErrorTransitorio,
    FaltaCredencial,
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
        with patch("httpx.post", return_value=_RespFalsa(401, text="bad key")), \
             pytest.raises(ErrorPermanente):
            AnthropicAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_anthropic_429_es_transitorio(self, credenciales_dummy):
        with patch("httpx.post", return_value=_RespFalsa(429, text="rate")), \
             pytest.raises(ErrorTransitorio):
            AnthropicAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_anthropic_500_es_transitorio(self, credenciales_dummy):
        with patch("httpx.post", return_value=_RespFalsa(503, text="upstream")), \
             pytest.raises(ErrorTransitorio):
            AnthropicAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_openai_200_devuelve_resultado(self, credenciales_dummy):
        with patch("httpx.post",
                   return_value=_RespFalsa(200, _openai_payload("ok"))):
            res = OpenAIAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)
        assert res.texto == "ok"
        assert res.provider == "openai"

    def test_mimo_sin_credencial_lanza_falta(self, db):
        with pytest.raises(FaltaCredencial):
            MimoAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_mimo_200_devuelve_resultado(self, db):
        from ajustes.models.credencial import Credencial
        Credencial.guardar("chalan_mimo_api_key", "mimo-test-xxxx")
        payload = {
            "model": "mimo-v2.5-pro",
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }
        with patch("httpx.post", return_value=_RespFalsa(200, payload)) as mock_post:
            res = MimoAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)
        # Auth con api-key, no Bearer
        _, kw = mock_post.call_args
        assert kw["headers"]["api-key"] == "mimo-test-xxxx"
        assert "Authorization" not in kw["headers"]
        # max_completion_tokens, no max_tokens
        assert "max_completion_tokens" in kw["json"]
        assert "max_tokens" not in kw["json"]
        assert kw["json"]["max_completion_tokens"] == 10
        assert res.texto == "ok"
        assert res.provider == "mimo"
        assert res.prompt_tokens == 5
        assert res.completion_tokens == 2
        # MiMo dejó de ser gratis — el costo se cuenta con la tarifa del adapter.
        from lib.analistas.adapters.mimo import PRECIO_IN, PRECIO_OUT
        assert res.costo_usd == round(5 * PRECIO_IN + 2 * PRECIO_OUT, 6)
        assert res.costo_usd > 0

    def test_mimo_401_es_permanente(self, db):
        from ajustes.models.credencial import Credencial
        Credencial.guardar("chalan_mimo_api_key", "mimo-test-xxxx")
        with patch("httpx.post", return_value=_RespFalsa(401, text="bad key")), \
             pytest.raises(ErrorPermanente):
            MimoAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_mimo_429_es_transitorio(self, db):
        from ajustes.models.credencial import Credencial
        Credencial.guardar("chalan_mimo_api_key", "mimo-test-xxxx")
        with patch("httpx.post", return_value=_RespFalsa(429, text="rate")), \
             pytest.raises(ErrorTransitorio):
            MimoAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_mimo_registrado_en_factories(self):
        from lib.analistas.registry import _FACTORIES, adapter_de
        assert "mimo" in _FACTORIES
        adapter = adapter_de("mimo")
        assert adapter is not None
        assert adapter.nombre == "mimo"

    # ── Gemini (S-Demo-Pre-Showcase) ──

    def test_gemini_sin_credencial_lanza_falta(self, db):
        with pytest.raises(FaltaCredencial):
            GeminiAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_gemini_200_devuelve_resultado(self, db):
        from ajustes.models.credencial import Credencial
        Credencial.guardar("chalan_gemini_api_key", "AIza-test-xxxx")
        payload = {
            "candidates": [
                {"content": {"parts": [{"text": "hola desde gemini"}], "role": "model"}}
            ],
            "usageMetadata": {
                "promptTokenCount": 7,
                "candidatesTokenCount": 4,
                "totalTokenCount": 11,
            },
        }
        with patch("httpx.post", return_value=_RespFalsa(200, payload)) as mock_post:
            res = GeminiAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)
        # API key va por query string, NO en header de auth.
        _, kw = mock_post.call_args
        assert kw["params"]["key"] == "AIza-test-xxxx"
        assert "Authorization" not in kw["headers"]
        assert "api-key" not in kw["headers"]
        # Body es contents/parts, no messages/choices.
        assert "contents" in kw["json"]
        assert kw["json"]["generationConfig"]["maxOutputTokens"] == 10
        assert res.texto == "hola desde gemini"
        assert res.provider == "gemini"
        assert res.prompt_tokens == 7
        assert res.completion_tokens == 4
        # Tarifa gemini-2.5-flash: 7 in * 0.30 + 4 out * 2.50 = $1.21e-5
        assert res.costo_usd > 0
        assert round(res.costo_usd, 6) == round(7 * 0.30 / 1_000_000 + 4 * 2.50 / 1_000_000, 6)

    def test_gemini_400_es_permanente(self, db):
        from ajustes.models.credencial import Credencial
        Credencial.guardar("chalan_gemini_api_key", "AIza-test-xxxx")
        with patch("httpx.post", return_value=_RespFalsa(400, text="API_KEY_INVALID")), \
             pytest.raises(ErrorPermanente):
            GeminiAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_gemini_429_es_transitorio(self, db):
        from ajustes.models.credencial import Credencial
        Credencial.guardar("chalan_gemini_api_key", "AIza-test-xxxx")
        with patch("httpx.post", return_value=_RespFalsa(429, text="rate")), \
             pytest.raises(ErrorTransitorio):
            GeminiAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)

    def test_gemini_registrado_en_factories(self):
        from lib.analistas.registry import _FACTORIES, adapter_de
        assert "gemini" in _FACTORIES
        adapter = adapter_de("gemini")
        assert adapter is not None
        assert adapter.nombre == "gemini"
        assert adapter.apodo == "Chalán Gemini"


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

    def test_anthropic_permanente_cae_a_openai(self, credenciales_dummy):
        # Política v3 (S-LC-Feedback-V1): ErrorPermanente también dispara
        # fallback. Una llave inválida en un proveedor no implica nada del
        # siguiente — cada Chalán tiene su propia credencial.
        from ajustes.models import AnalistaLog

        post_mock = _post_routed(
            anthropic_resp=_RespFalsa(401),
            openai_resp=_RespFalsa(200, _openai_payload("ok")),
        )
        with patch("httpx.post", side_effect=post_mock) as mock:
            res = analizar("cotizaciones", "prompt")
        assert res.provider == "openai"
        assert mock.call_count == 2
        logs = list(AnalistaLog.objects.order_by("creado_en"))
        assert logs[0].exito is False and logs[0].provider == "anthropic"
        assert logs[1].exito is True and logs[1].provider == "openai"

    def test_ambos_transitorios_falla_cadena(self, credenciales_dummy):
        post_mock = _post_routed(
            anthropic_resp=_RespFalsa(503),
            openai_resp=_RespFalsa(503),
        )
        with patch("httpx.post", side_effect=post_mock), \
             pytest.raises(TodosLosAnalistasFallaron):
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


# ── Fase C1 (S-Chalán-Scope-OCR): plomería multimodal ──────────────────────────

_IMG = [{"base64": "QQ==", "media_type": "image/png"}]


def test_normalizar_imagenes_filtra_y_capea():
    from lib.analistas.multimodal import MAX_IMAGENES, normalizar_imagenes
    assert normalizar_imagenes(None) == []
    assert normalizar_imagenes([{"data": "X", "mime_type": "image/jpeg"}]) == [
        {"base64": "X", "media_type": "image/jpeg"}
    ]
    assert normalizar_imagenes(["basura", {"sin": "datos"}]) == []
    muchas = [{"base64": "X", "media_type": "image/png"} for _ in range(MAX_IMAGENES + 5)]
    assert len(normalizar_imagenes(muchas)) == MAX_IMAGENES


@pytest.mark.django_db
class TestMultimodal:

    def test_anthropic_incluye_imagen(self, credenciales_dummy):
        with patch("httpx.post", return_value=_RespFalsa(200, _anthropic_payload("ok"))) as m:
            AnthropicAdapter()._invocar("describe", max_tokens=10, temperatura=0.0, imagenes=_IMG)
        contenido = m.call_args.kwargs["json"]["messages"][0]["content"]
        assert isinstance(contenido, list)
        assert any(b.get("type") == "image" for b in contenido)
        assert any(b.get("type") == "text" for b in contenido)

    def test_anthropic_sin_imagen_es_texto_plano(self, credenciales_dummy):
        with patch("httpx.post", return_value=_RespFalsa(200, _anthropic_payload("ok"))) as m:
            AnthropicAdapter()._invocar("hola", max_tokens=10, temperatura=0.0)
        assert m.call_args.kwargs["json"]["messages"][0]["content"] == "hola"

    def test_openai_incluye_imagen_data_url(self, credenciales_dummy):
        with patch("httpx.post", return_value=_RespFalsa(200, _openai_payload("ok"))) as m:
            OpenAIAdapter()._invocar("describe", max_tokens=10, temperatura=0.0, imagenes=_IMG)
        contenido = m.call_args.kwargs["json"]["messages"][0]["content"]
        url = next(b["image_url"]["url"] for b in contenido if b.get("type") == "image_url")
        assert url.startswith("data:image/png;base64,")

    def test_gemini_incluye_inline_data(self, db):
        from ajustes.models.credencial import Credencial
        Credencial.guardar("chalan_gemini_api_key", "g-test-xxxx")
        payload = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                   "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 1}}
        with patch("httpx.post", return_value=_RespFalsa(200, payload)) as m:
            GeminiAdapter()._invocar("describe", max_tokens=10, temperatura=0.0, imagenes=_IMG)
        partes = m.call_args.kwargs["json"]["contents"][0]["parts"]
        assert any("inline_data" in p for p in partes)

    def test_mimo_incluye_imagen(self, db):
        from ajustes.models.credencial import Credencial
        Credencial.guardar("chalan_mimo_api_key", "mimo-test-xxxx")
        payload = {"model": "mimo", "choices": [{"message": {"content": "ok"}}],
                   "usage": {"prompt_tokens": 3, "completion_tokens": 1}}
        with patch("httpx.post", return_value=_RespFalsa(200, payload)) as m:
            MimoAdapter()._invocar("describe", max_tokens=10, temperatura=0.0, imagenes=_IMG)
        contenido = m.call_args.kwargs["json"]["messages"][0]["content"]
        assert any(b.get("type") == "image_url" for b in contenido)

    def test_reemplazo_con_imagenes_salta_no_vision(self, monkeypatch):
        """Si se pasan imágenes, el Reemplazo exige VISION y salta los adapters
        que no la soportan (Deepseek)."""
        from lib.analistas import reemplazo
        from lib.analistas.adapters.deepseek import DeepseekAdapter
        monkeypatch.setattr(reemplazo, "cadena_de", lambda *a, **k: [DeepseekAdapter()])
        with pytest.raises(TodosLosAnalistasFallaron):
            analizar("ocr_recibo", "lee el recibo", imagenes=_IMG)
