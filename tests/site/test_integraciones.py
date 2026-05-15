"""lib.site.integraciones — chequeos externos. Mockea HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest


@pytest.mark.django_db
def test_anthropic_sin_credencial():
    from lib.site.integraciones import chequear_anthropic
    r = chequear_anthropic()
    assert r["estado"] == "no_configurada"


@pytest.mark.django_db
def test_openai_sin_credencial():
    from lib.site.integraciones import chequear_openai
    r = chequear_openai()
    assert r["estado"] == "no_configurada"


@pytest.mark.django_db
def test_anthropic_con_credencial_ok():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("anthropic_api_key", "sk-ant-fake")
    from lib.site.integraciones import chequear_anthropic
    with patch("httpx.post") as p:
        p.return_value = MagicMock(status_code=200, text="{}")
        r = chequear_anthropic()
    assert r["estado"] == "ok"
    assert r["latencia_ms"] is not None


@pytest.mark.django_db
def test_anthropic_con_credencial_error_http():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("anthropic_api_key", "sk-ant-fake")
    from lib.site.integraciones import chequear_anthropic
    with patch("httpx.post") as p:
        p.return_value = MagicMock(status_code=401, text="unauthorized")
        r = chequear_anthropic()
    assert r["estado"] == "error"
    assert "401" in r["mensaje_error"]


@pytest.mark.django_db
def test_openai_con_credencial_timeout():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("openai_api_key", "sk-fake")
    from lib.site.integraciones import chequear_openai
    with patch("httpx.post", side_effect=httpx.ConnectTimeout("timeout")):
        r = chequear_openai()
    assert r["estado"] == "error"
    assert "timeout" in r["mensaje_error"].lower()


@pytest.mark.django_db
def test_n8n_sin_credencial():
    from lib.site.integraciones import chequear_n8n
    r = chequear_n8n()
    assert r["estado"] == "no_configurada"


@pytest.mark.django_db
def test_n8n_con_url_ok():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("n8n_health_url", "http://hal.example.ts.net:5678/healthz")
    from lib.site.integraciones import chequear_n8n
    with patch("httpx.get") as p:
        p.return_value = MagicMock(status_code=200)
        r = chequear_n8n()
    assert r["estado"] == "ok"


def test_tailscale_sin_binario(monkeypatch):
    """Si tailscale no está instalado en el host del test runner, devuelve no_configurada."""
    monkeypatch.setattr("shutil.which", lambda x: None)
    monkeypatch.setattr("os.path.exists", lambda p: False)
    from lib.site.integraciones import chequear_tailscale
    r = chequear_tailscale()
    assert r["estado"] == "no_configurada"


def test_docker_sin_socket(monkeypatch):
    monkeypatch.setenv("SITE_DOCKER_SOCK", "/no/existe/docker.sock")
    import importlib

    from lib.site import contenedores
    importlib.reload(contenedores)
    from lib.site.integraciones import chequear_docker
    r = chequear_docker()
    assert r["estado"] == "no_configurada"
