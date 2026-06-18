"""S-Chalan-Negocio-V1 — El Chalán aprende y opina del negocio.

Cubre: lecturas de negocio (Fase 1), herramientas del chat gateadas (Fase 2),
análisis proactivo → PropuestaChalan + modal (Fase 3), destilador de
conocimiento review-first + inyección de contexto (Fase 4). Mockean
`lib.analistas.analizar` y silencian el push del Interfón.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── helpers ──────────────────────────────────────────────────────────


def _res(texto: str):
    return SimpleNamespace(texto=texto, provider="anthropic", modelo="claude-sonnet-4-6",
                           costo_usd=0.0, prompt_tokens=1, completion_tokens=1, latencia_ms=1)


def _mock_analizar(monkeypatch, texto: str):
    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", lambda *a, **k: _res(texto))


def _mute_push(monkeypatch):
    import lib.interfono as inf
    llamadas = []
    monkeypatch.setattr(inf, "enviar_a_usuario", lambda *a, **k: llamadas.append((a, k)) or {"entrega_id": 1})
    return llamadas


# ── Fase 1: lecturas de negocio ──────────────────────────────────────


def test_hechos_por_dominio_estructura():
    from apps.taller_home import negocio
    for dom in negocio.DOMINIOS:
        h = negocio.hechos_de(dom)
        assert set(h) >= {"titulo", "hechos", "metricas"}
        assert h["titulo"]


def test_hechos_finanzas_con_datos():
    from apps.taller_home.negocio import hechos_finanzas
    h = hechos_finanzas()
    # Aun con DB vacía arma el resumen (ceros), no truena.
    assert "Ingresos" in h["hechos"] or h["hechos"] == ""


# ── Fase 2: herramientas del chat gateadas ───────────────────────────


def test_tool_resumen_cobranza_gateada(usuario_factory):
    from apps.el_dictado.herramientas import ejecutar_herramienta
    diseniador = usuario_factory(rol="disenador")
    r = ejecutar_herramienta("resumen_cobranza", {}, diseniador)
    assert r.get("error") == "sin_permiso"


def test_tool_resumen_cobranza_admin_ok(usuario_factory):
    from apps.el_dictado.herramientas import ejecutar_herramienta
    admin = usuario_factory(rol="super_admin")
    r = ejecutar_herramienta("resumen_cobranza", {}, admin)
    assert "error" not in r
    assert r.get("dominio") == "cobranza" and r.get("resumen")


def test_tools_negocio_visibles_en_prompt(usuario_factory):
    from apps.el_dictado.prompt_chat import construir_system_prompt
    admin = usuario_factory(rol="super_admin")
    prompt = construir_system_prompt(admin)
    assert "resumen_finanzas" in prompt and "resumen_cobranza" in prompt


# ── Fase 3: análisis proactivo ───────────────────────────────────────


def test_analizar_dominio_crea_propuesta_y_es_idempotente(monkeypatch, usuario_factory):
    from apps.el_dictado.analisis_negocio import analizar_dominio
    from apps.el_dictado.models import PropuestaChalan
    _mute_push(monkeypatch)
    _mock_analizar(monkeypatch, "- La cobranza está sana.\n- Recomiendo seguir así.")
    admin = usuario_factory(rol="super_admin")

    r1 = analizar_dominio(dominio="cobranza")
    assert r1["ok"] and r1["creadas"] >= 1
    props = PropuestaChalan.objects.filter(usuario=admin, tipo="analisis_cobranza")
    assert props.count() == 1
    p = props.first()
    assert p.url == f"/chalan/analisis/{p.pk}/" and p.cuerpo

    # Segunda corrida en la misma semana NO duplica.
    r2 = analizar_dominio(dominio="cobranza")
    assert r2["creadas"] == 0
    assert PropuestaChalan.objects.filter(usuario=admin, tipo="analisis_cobranza").count() == 1


def test_analizar_dominio_dry_run_no_crea(monkeypatch, usuario_factory):
    from apps.el_dictado.analisis_negocio import analizar_dominio
    from apps.el_dictado.models import PropuestaChalan
    _mute_push(monkeypatch)
    _mock_analizar(monkeypatch, "opinión")
    usuario_factory(rol="super_admin")
    r = analizar_dominio(dominio="finanzas", dry_run=True)
    assert r["ok"] and r["texto"] and PropuestaChalan.objects.count() == 0


def test_analizar_dominio_ia_caida(monkeypatch, usuario_factory):
    from apps.el_dictado.analisis_negocio import analizar_dominio
    from apps.el_dictado.models import PropuestaChalan

    import lib.analistas as la
    _mute_push(monkeypatch)
    monkeypatch.setattr(la, "analizar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("caído")))
    usuario_factory(rol="super_admin")
    r = analizar_dominio(dominio="ventas")
    assert r["ok"] is False and r["motivo"] == "fallo_ia"
    assert PropuestaChalan.objects.count() == 0


def test_modal_analisis_marca_vista(client, monkeypatch, usuario_factory):
    from apps.el_dictado.models import PropuestaChalan
    admin = usuario_factory(rol="super_admin")
    prop = PropuestaChalan.objects.create(
        usuario=admin, tipo="analisis_finanzas", clave_dedup="analisis_finanzas:x:1",
        titulo="El Chalán opina: Finanzas", cuerpo="- Todo bien\n- Sigue así",
        url="", estado="pendiente")
    prop.url = f"/chalan/analisis/{prop.pk}/"
    prop.save(update_fields=["url"])
    client.force_login(admin)
    resp = client.get(f"/chalan/analisis/{prop.pk}/")
    assert resp.status_code == 200
    assert b"El Chal" in resp.content
    prop.refresh_from_db()
    assert prop.estado == "vista"


# ── Fase 4: destilador de conocimiento + inyección ───────────────────


def _obs(*pares):
    return json.dumps({"observaciones": [
        {"ambito": a, "observacion": o, "evidencia": "dato", "peso": 1.1}
        for a, o in pares
    ]})


def test_destilar_negocio_crea_inactivos(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar_negocio import destilar
    from apps.el_dictado.models import ConocimientoNegocio
    _mock_analizar(monkeypatch, _obs(
        ("cobranza", "Hay clientes que pagan tarde"),
        ("margenes", "El margen promedio es bajo")))
    r = destilar(creado_por=usuario_factory(rol="super_admin"))
    assert r["ok"] and r["creados"] == 2
    for c in ConocimientoNegocio.objects.all():
        assert c.activo is False and c.origen == "chalan_destilado"
        assert c.peso_efectivo() == 0.0


def test_destilar_negocio_dedup(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar_negocio import destilar
    from apps.el_dictado.models import ConocimientoNegocio
    ConocimientoNegocio.objects.create(
        ambito="cobranza", observacion="Hay clientes que pagan tarde",
        activo=True, origen="manual")
    _mock_analizar(monkeypatch, _obs(
        ("cobranza", "Hay clientes que pagan tarde"),  # dup → se filtra
        ("ventas", "Pipeline concentrado en por_cotizar")))
    r = destilar(creado_por=usuario_factory(rol="super_admin"))
    assert r["creados"] == 1
    assert ConocimientoNegocio.objects.filter(origen="chalan_destilado").count() == 1


def test_destilar_negocio_dry_run(monkeypatch, usuario_factory):
    from apps.el_dictado.destilar_negocio import destilar
    from apps.el_dictado.models import ConocimientoNegocio
    _mock_analizar(monkeypatch, _obs(("finanzas", "Utilidad estable")))
    r = destilar(dry_run=True)
    assert r["ok"] and len(r["candidatos"]) == 1 and ConocimientoNegocio.objects.count() == 0


def test_bloque_contexto_solo_activos():
    from apps.el_dictado.conocimiento import bloque_contexto_negocio
    from apps.el_dictado.models import ConocimientoNegocio
    ConocimientoNegocio.objects.create(ambito="finanzas", observacion="Margen sano", activo=True)
    ConocimientoNegocio.objects.create(ambito="ventas", observacion="Oculto", activo=False)
    bloque = bloque_contexto_negocio()
    assert "Margen sano" in bloque and "Oculto" not in bloque
    assert "CONTEXTO DEL NEGOCIO" in bloque


def test_bloque_contexto_vacio_sin_activos():
    from apps.el_dictado.conocimiento import bloque_contexto_negocio
    assert bloque_contexto_negocio() == ""
