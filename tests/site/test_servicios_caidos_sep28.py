"""La alarma de los servicios que no responden (S-Pendientes-Sep28).

El 2026-09-18 el NUC se reinició, Docker arrancó antes que Tailscale y n8n y
Paperless no pudieron escuchar en la IP del tailnet. Nunca arrancaron, la poda
nocturna borró sus contenedores y **nadie se enteró en 10 días**: El Vigía sólo
cuenta los contenedores que existen, y `/salud` no miraba los servicios. Estas
pruebas fijan que ahora se ve en los dos lados, y sólo donde se esperan.
"""

from __future__ import annotations

import pytest

from lib import salud
from lib.site import servicios


def _lista(vivos: dict[str, bool]) -> list[dict]:
    return [
        {"clave": c, "nombre": c.capitalize(), "oficio": f"hace {c}", "vivo": v}
        for c, v in vivos.items()
    ]


@pytest.fixture
def en_el_nuc(monkeypatch):
    monkeypatch.setenv("SITE_SERVICIOS_ESPERADOS", "1")


def test_donde_no_se_esperan_no_hay_nada_que_extranar(monkeypatch):
    """En HAL o en CI los servicios no existen: la alarma estaría prendida siempre."""
    monkeypatch.delenv("SITE_SERVICIOS_ESPERADOS", raising=False)
    monkeypatch.setattr(servicios, "estado_cacheado", lambda: pytest.fail("no debía sondear"))
    assert servicios.caidos() == []
    assert salud._m_servicios(de_la_casa=False) is None


def test_en_el_nuc_los_caidos_salen_con_nombre(en_el_nuc, monkeypatch):
    monkeypatch.setattr(
        servicios, "estado_cacheado",
        lambda: _lista({"gotenberg": True, "osrm": True, "n8n": False, "paperless": False}),
    )
    assert [p["clave"] for p in servicios.caidos()] == ["n8n", "paperless"]


def test_salud_degrada_y_solo_la_casa_ve_los_nombres(en_el_nuc, monkeypatch):
    monkeypatch.setattr(
        servicios, "estado_cacheado", lambda: _lista({"gotenberg": True, "n8n": False}),
    )
    publico = salud._m_servicios(de_la_casa=False)
    privado = salud._m_servicios(de_la_casa=True)
    assert publico["estado"] == privado["estado"] == "degradado"
    assert publico["detalle"] == "1 servicio no responde"
    assert "N8n" in privado["detalle"]
    # No es `falla`: un servicio auxiliar caído no tumba el despacho.
    assert salud.estado_del_conjunto([publico]) == "degradado"


def test_salud_ok_cuando_todos_responden(en_el_nuc, monkeypatch):
    monkeypatch.setattr(servicios, "estado_cacheado", lambda: _lista({"gotenberg": True, "n8n": True}))
    m = salud._m_servicios(de_la_casa=False)
    assert m == {"modulo": "servicios", "estado": "ok", "detalle": "2 servicios responden"}


def test_los_modulos_de_salud_saltan_lo_que_no_aplica(monkeypatch):
    monkeypatch.delenv("SITE_SERVICIOS_ESPERADOS", raising=False)
    nombres = {m["modulo"] for m in salud.modulos()}
    assert "servicios" not in nombres


@pytest.mark.django_db
def test_el_vigia_pinta_los_caidos_en_la_pared(en_el_nuc, monkeypatch, client, settings):
    """El panel «Las piezas» lo comparten la pared y El Site (§4 #22): con que
    lo pinte uno, lo pintan los dos."""
    settings.ROOT_URLCONF = "tests.urls_gerencia"
    settings.ALLOWED_HOSTS = ["*"]
    from lib.site import contenedores

    monkeypatch.setattr(contenedores, "estadisticas", lambda: [])
    monkeypatch.setattr(servicios, "estado_cacheado", lambda: _lista({"n8n": False}))
    r = client.get("/site/vivo/contenedores", HTTP_HOST="localhost")
    assert r.status_code == 200
    html = r.content.decode()
    assert "data-servicios-caidos" in html
    assert "N8n</span> no responde" in html
