"""S-Aviso-Deploy-V1 — lib/aviso_deploy + partial + endpoint + context processor."""

from __future__ import annotations

import filecmp
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.aviso_deploy import (
    CLAVE_REDIS,
    contexto_aviso_deploy,
    limpiar_deploy_en_curso,
    marcar_deploy_en_curso,
    obtener_deploy_en_curso,
)


@pytest.fixture(autouse=True)
def _limpiar_redis():
    """Asegura clave limpia antes y después de cada test."""
    limpiar_deploy_en_curso()
    yield
    limpiar_deploy_en_curso()


def test_sin_flag_obtener_devuelve_none():
    assert obtener_deploy_en_curso() is None


def test_marcar_setea_ttl():
    from lib.aviso_deploy import _client
    marcar_deploy_en_curso("abc123", ttl_segundos=300)
    assert obtener_deploy_en_curso() == "abc123"
    ttl = _client().ttl(CLAVE_REDIS)
    assert 0 < ttl <= 300


def test_limpiar_borra_la_clave():
    marcar_deploy_en_curso("xyz")
    assert obtener_deploy_en_curso() == "xyz"
    limpiar_deploy_en_curso()
    assert obtener_deploy_en_curso() is None


def test_redis_caido_no_rompe_obtener():
    """Si Redis tira ConnectionError, obtener_deploy_en_curso devuelve None
    en lugar de propagar el error — el banner es nice-to-have."""
    from redis.exceptions import ConnectionError as RCE
    with patch("lib.aviso_deploy._client") as mock:
        mock.return_value.get.side_effect = RCE("boom")
        assert obtener_deploy_en_curso() is None


def test_context_processor_expone_flag():
    marcar_deploy_en_curso("sha-test")
    ctx = contexto_aviso_deploy(request=None)
    assert ctx["hay_deploy_en_curso"] is True
    assert ctx["deploy_commit_sha"] == "sha-test"


def test_context_processor_sin_flag():
    ctx = contexto_aviso_deploy(request=None)
    assert ctx["hay_deploy_en_curso"] is False
    assert ctx["deploy_commit_sha"] is None


def test_partial_dos_copias_sincronizadas():
    """Patrón S-TailAdmin-1 (regla #18): partials dual-copy deben ser idénticos."""
    root = Path(__file__).resolve().parent.parent
    a = root / "el-taller/templates/_componentes_tailadmin/_banner_deploy.html"
    b = root / "la-gerencia/templates/_componentes_tailadmin/_banner_deploy.html"
    assert a.exists(), f"falta {a}"
    assert b.exists(), f"falta {b}"
    assert filecmp.cmp(a, b, shallow=False), "Las dos copias del partial divergen — sincronizar."
