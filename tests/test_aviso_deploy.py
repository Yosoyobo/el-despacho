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


def test_semaforo_dual_copy_sincronizada():
    """S-LC-Feedback-V2: el partial del semáforo también es dual-copy."""
    root = Path(__file__).resolve().parent.parent
    a = root / "el-taller/templates/_componentes_tailadmin/_semaforo_deploy.html"
    b = root / "la-gerencia/templates/_componentes_tailadmin/_semaforo_deploy.html"
    assert a.exists(), f"falta {a}"
    assert b.exists(), f"falta {b}"
    assert filecmp.cmp(a, b, shallow=False), "Las dos copias del partial divergen — sincronizar."


def test_semaforo_renderiza_verde_sin_deploy():
    """Sin flag, el partial muestra 🟢."""
    root = Path(__file__).resolve().parent.parent
    contenido = (root / "el-taller/templates/_componentes_tailadmin/_semaforo_deploy.html").read_text()
    assert "🟢" in contenido
    assert "🔴" in contenido  # también incluye la rama de deploy


# ---------------------------------------------------------------------------
# S-NUC-Servicios (2026-08-24): la ventana de mantenimiento respira ámbar, y
# se pone roja SOLA cuando algo deja de responder.
# ---------------------------------------------------------------------------


def test_sin_ventana_no_hay_nivel(monkeypatch):
    """Sin bandera no hay banner, así que tampoco hay nivel que calcular."""
    from lib import aviso_deploy as ad

    monkeypatch.setattr(ad, "obtener_deploy_en_curso", lambda: None)
    assert ad.nivel_aviso() is None


def test_ventana_abierta_y_todo_responde_es_ambar(monkeypatch):
    from lib import aviso_deploy as ad

    monkeypatch.setattr(ad, "obtener_deploy_en_curso", lambda: "sha")
    monkeypatch.setattr(ad, "_base_responde", lambda: True)
    monkeypatch.setattr(ad, "_sondas_configuradas", list)
    monkeypatch.setattr(ad, "_client", lambda: _RedisFalso())
    assert ad.nivel_aviso() == ad.NIVEL_AMBAR


def test_base_caida_pone_el_banner_en_rojo(monkeypatch):
    """El rojo no se marca a mano: lo enciende la sonda."""
    from lib import aviso_deploy as ad

    monkeypatch.setattr(ad, "obtener_deploy_en_curso", lambda: "sha")
    monkeypatch.setattr(ad, "_base_responde", lambda: False)
    monkeypatch.setattr(ad, "_sondas_configuradas", list)
    monkeypatch.setattr(ad, "_client", lambda: _RedisFalso())
    assert ad.nivel_aviso() == ad.NIVEL_ROJO


def test_un_servicio_sondeado_caido_pone_rojo(monkeypatch):
    from lib import aviso_deploy as ad

    monkeypatch.setattr(ad, "obtener_deploy_en_curso", lambda: "sha")
    monkeypatch.setattr(ad, "_base_responde", lambda: True)
    monkeypatch.setattr(ad, "_sondas_configuradas", lambda: ["http://gotenberg:3000/health"])
    monkeypatch.setattr(ad, "_servicio_responde", lambda url: False)
    monkeypatch.setattr(ad, "_client", lambda: _RedisFalso())
    assert ad.nivel_aviso() == ad.NIVEL_ROJO


def test_el_veredicto_se_cachea_para_no_sondear_por_cada_pestana(monkeypatch):
    """El banner poll cada 10s desde cada pestaña: sin caché compartido el
    costo se multiplicaría por el número de personas mirando."""
    from lib import aviso_deploy as ad

    llamadas = {"n": 0}

    def _contar():
        llamadas["n"] += 1
        return True

    falso = _RedisFalso()
    monkeypatch.setattr(ad, "obtener_deploy_en_curso", lambda: "sha")
    monkeypatch.setattr(ad, "_base_responde", _contar)
    monkeypatch.setattr(ad, "_sondas_configuradas", list)
    monkeypatch.setattr(ad, "_client", lambda: falso)

    for _ in range(5):
        ad.nivel_aviso()
    assert llamadas["n"] == 1, "se sondeó más de una vez pese al caché"


def test_redis_caido_durante_la_ventana_es_rojo(monkeypatch):
    """Redis caído ES una caída: si la ventana está abierta, hay que decirlo."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    from lib import aviso_deploy as ad

    def _explota():
        raise RedisConnectionError("sin redis")

    monkeypatch.setattr(ad, "obtener_deploy_en_curso", lambda: "sha")
    monkeypatch.setattr(ad, "_client", _explota)
    assert ad.nivel_aviso() == ad.NIVEL_ROJO


def test_el_banner_tiene_las_dos_ramas_y_respira():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    html = (root / "el-taller/templates/_componentes_tailadmin/_banner_deploy.html").read_text()
    assert 'nivel_aviso == "rojo"' in html, "falta la rama del rojo"
    assert "bg-error-50" in html and "bg-warning-50" in html, "faltan los dos colores"
    assert html.count("respira ") >= 2, "las dos ramas deben respirar"


def test_la_animacion_vive_en_los_dos_input_css():
    """`respira` es clase propia (no de Tailwind): tiene que estar en el CSS
    fuente de las dos apps o el banner no late en una de ellas."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for app in ("el-taller", "la-gerencia"):
        css = (root / app / "static/css/input.css").read_text()
        assert "@keyframes respirar" in css, f"falta la animación en {app}"
        assert ".respira" in css, f"falta la clase en {app}"
        assert "prefers-reduced-motion" in css, f"{app}: la animación no es opcional"


class _RedisFalso:
    """Redis de mentiras que sí respeta get/set — para probar el caché."""

    def __init__(self):
        self.datos = {}

    def get(self, k):
        return self.datos.get(k)

    def set(self, k, v, ex=None):
        self.datos[k] = v

    def delete(self, k):
        """La fixture autouse limpia la clave en el teardown; sin esto, el
        test pasa y el teardown truena."""
        self.datos.pop(k, None)


def test_el_context_processor_no_relee_la_bandera(monkeypatch):
    """Corre en CADA petición de las tres apps: releer la bandera aquí
    duplicaría el viaje a Redis del camino caliente sin ganar nada."""
    from lib import aviso_deploy as ad

    lecturas = {"n": 0}

    def _contar():
        lecturas["n"] += 1
        return None

    monkeypatch.setattr(ad, "obtener_deploy_en_curso", _contar)
    ad.contexto_aviso_deploy(request=None)
    assert lecturas["n"] == 1, "se leyó la bandera más de una vez por petición"
