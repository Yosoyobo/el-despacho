"""S2b.5 — Flujo NL→DSL→KPICustom y aparición en el dashboard."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.django_db


def _mock_resultado(texto_json: str):
    from lib.analistas.base import Resultado
    return Resultado(
        texto=texto_json, provider="anthropic", modelo="claude-opus-4-7",
        prompt_tokens=100, completion_tokens=200, costo_usd=0.001, latencia_ms=50,
    )


def _seed_estacion_kpi_dsl():
    from ajustes.models.credencial import Credencial
    from chalanes.models import CuadroChalanes
    Credencial.guardar("chalan_anthropic_api_key", "sk-ant-test")
    CuadroChalanes.objects.update_or_create(
        estacion="kpi_dsl",
        defaults={"proveedor": "anthropic", "modelo": "claude-opus-4-7"},
    )


def test_nl_a_dsl_traduce_y_valida(usuario_factory):
    _seed_estacion_kpi_dsl()
    u = usuario_factory(rol="dueno")
    from apps.taller_home.services_kpi_chalan import nl_a_dsl

    respuesta = json.dumps({
        "entidad": "proyecto",
        "agregacion": "count",
        "filtros": [{"campo": "estado", "op": "in", "valor": ["en_proceso_produccion"]}],
        "ventana_tiempo": "siempre",
        "alcance_usuario": "todos",
        "titulo_sugerido": "Proyectos en producción",
        "categoria_sugerida": "operacion",
    })
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(respuesta)
        res = nl_a_dsl(texto="cuántos proyectos en producción", usuario=u)

    assert res["ok"]
    assert res["definicion"]["entidad"] == "proyecto"
    assert res["titulo_sugerido"] == "Proyectos en producción"
    assert res["preview"]["valor"] == 0  # sin data, count=0


def test_nl_a_dsl_chalan_rechaza_por_validacion(usuario_factory):
    """Si el LLM devuelve algo fuera del whitelist, NO se ejecuta."""
    _seed_estacion_kpi_dsl()
    u = usuario_factory(rol="dueno")
    from apps.taller_home.services_kpi_chalan import nl_a_dsl

    respuesta = json.dumps({"entidad": "sistemas_internos_de_anthropic"})
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(respuesta)
        res = nl_a_dsl(texto="hackeame anthropic", usuario=u)

    assert not res["ok"]
    assert "no permitida" in res["error"].lower() or "entidad" in res["error"].lower()


def test_crear_kpi_personal_queda_activo(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)

    definicion = {"entidad": "proyecto", "agregacion": "count",
                  "filtros": [], "ventana_tiempo": "siempre", "alcance_usuario": "todos"}
    resp = client.post("/kpis/custom/crear", {
        "titulo": "Total de proyectos",
        "alcance": "personal",
        "categoria": "operacion",
        "definicion_json": json.dumps(definicion),
    })
    assert resp.status_code == 302

    from apps.taller_home.models import KPICustom
    k = KPICustom.objects.get(autor=u)
    assert k.estado == "activo"
    assert k.alcance == "personal"


def test_crear_kpi_equipo_queda_pendiente(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)

    definicion = {"entidad": "proyecto", "agregacion": "count"}
    client.post("/kpis/custom/crear", {
        "titulo": "Total team",
        "alcance": "equipo",
        "definicion_json": json.dumps(definicion),
    })
    from apps.taller_home.models import KPICustom
    k = KPICustom.objects.get(autor=u)
    assert k.estado == "pendiente_aprobacion"


def test_kpi_custom_aparece_en_dashboard_del_autor(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    from apps.taller_home.models import KPICustom

    KPICustom.objects.create(
        slug="mi-test", titulo="Mi KPI ZZZTEST",
        definicion_json={"entidad": "proyecto", "agregacion": "count",
                         "filtros": [], "ventana_tiempo": "siempre",
                         "alcance_usuario": "todos"},
        alcance="personal", estado="activo", autor=u,
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Mi KPI ZZZTEST" in resp.content


def test_kpi_custom_equipo_no_aparece_si_no_aprobado(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    otro = usuario_factory(rol="dueno", email="otro@x.com")
    client.force_login(otro)
    from apps.taller_home.models import KPICustom

    KPICustom.objects.create(
        slug="team-test", titulo="Team KPI ZZZTEST",
        definicion_json={"entidad": "proyecto"},
        alcance="equipo", estado="pendiente_aprobacion", autor=u,
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Team KPI ZZZTEST" not in resp.content


def test_proponer_pide_chalan_y_renderiza_preview(client, usuario_factory):
    _seed_estacion_kpi_dsl()
    u = usuario_factory(rol="dueno")
    client.force_login(u)

    respuesta = json.dumps({
        "entidad": "proyecto", "agregacion": "count",
        "filtros": [], "ventana_tiempo": "siempre", "alcance_usuario": "todos",
        "titulo_sugerido": "Sugerido", "categoria_sugerida": "operacion",
    })
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(respuesta)
        resp = client.post("/kpis/custom/proponer", {"texto": "Cuántos proyectos hay"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Sugerido" in body
    assert "Confirma el KPI" in body
