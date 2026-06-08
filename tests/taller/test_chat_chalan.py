"""Tests del Chat conversacional del Taller (El Chalán) — S-Chalan-Chat-V1.

Mockean `lib.analistas.analizar` con sobres JSON canned para ejercitar el loop
de tool-use sin pegarle a un LLM real.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ns(texto: str):
    return SimpleNamespace(
        texto=texto, provider="anthropic", modelo="claude-haiku-4-5",
        prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1,
    )


def _fake_analizar(respuestas):
    """Devuelve un fake de `analizar` que emite `respuestas` en orden.

    Cada item puede ser un dict (se serializa) o un callable(i) -> str|dict.
    Si se agotan, repite el último.
    """
    estado = {"i": 0}

    def fake(estacion, prompt, **kw):
        i = estado["i"]
        estado["i"] += 1
        item = respuestas[i] if i < len(respuestas) else respuestas[-1]
        if callable(item):
            item = item(i)
        return _ns(item if isinstance(item, str) else json.dumps(item))

    return fake, estado


def _conv(usuario):
    from apps.el_dictado.services_chat import crear_conversacion
    return crear_conversacion(usuario=usuario)


# ── Loop ──────────────────────────────────────────────────────────────────────

def test_loop_responder(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    fake, estado = _fake_analizar([{"tipo": "responder", "texto": "Hay 5 proyectos activos."}])
    monkeypatch.setattr(la, "analizar", fake)
    res = conversar(mensaje="¿cuántos proyectos?", usuario=u, conversacion=_conv(u))
    assert estado["i"] == 1
    tipos = [(m.rol, m.tipo) for m in res["mensajes"]]
    assert tipos == [("user", "texto"), ("bot", "texto")]
    assert "5 proyectos" in res["mensajes"][-1].cuerpo


def test_loop_herramienta_y_responde(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    fake, estado = _fake_analizar([
        {"tipo": "herramienta", "nombre": "gasto_ia", "args": {"dias": 30}},
        {"tipo": "responder", "texto": "Llevas poco gasto."},
    ])
    monkeypatch.setattr(la, "analizar", fake)
    res = conversar(mensaje="¿cuánto gasto en IA?", usuario=u, conversacion=_conv(u))
    assert estado["i"] == 2  # 1 herramienta + 1 respuesta
    tipos = [(m.rol, m.tipo) for m in res["mensajes"]]
    assert tipos == [("user", "texto"), ("bot", "herramienta"), ("bot", "texto")]


def test_cap_iteraciones(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import MAX_ITERACIONES, conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    # Siempre herramienta, args distintos cada vez (evita dedup) → agota el cap.
    fake, estado = _fake_analizar([
        lambda i: {"tipo": "herramienta", "nombre": "gasto_ia", "args": {"dias": 10 + i}},
    ])
    monkeypatch.setattr(la, "analizar", fake)
    res = conversar(mensaje="loop", usuario=u, conversacion=_conv(u))
    assert estado["i"] == MAX_ITERACIONES
    assert "específica" in res["mensajes"][-1].cuerpo


def test_json_invalido(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    fake, _ = _fake_analizar(["esto no es json"])
    monkeypatch.setattr(la, "analizar", fake)
    res = conversar(mensaje="hola", usuario=u, conversacion=_conv(u))
    assert res["mensajes"][-1].rol == "bot"
    assert "reformular" in res["mensajes"][-1].cuerpo


def test_herramienta_inexistente_no_crashea(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    fake, estado = _fake_analizar([
        {"tipo": "herramienta", "nombre": "no_existe", "args": {}},
        {"tipo": "responder", "texto": "Ok"},
    ])
    monkeypatch.setattr(la, "analizar", fake)
    res = conversar(mensaje="x", usuario=u, conversacion=_conv(u))
    assert estado["i"] == 2
    assert res["mensajes"][-1].cuerpo == "Ok"


def test_dedup_tool_call(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    # Misma herramienta+args repetida → dedup corta en la 2a.
    fake, estado = _fake_analizar([{"tipo": "herramienta", "nombre": "gasto_ia", "args": {"dias": 30}}])
    monkeypatch.setattr(la, "analizar", fake)
    res = conversar(mensaje="x", usuario=u, conversacion=_conv(u))
    assert estado["i"] == 2
    assert "específica" in res["mensajes"][-1].cuerpo


def test_llm_caido(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")

    def boom(*a, **k):
        raise RuntimeError("todos fallaron")

    monkeypatch.setattr(la, "analizar", boom)
    res = conversar(mensaje="x", usuario=u, conversacion=_conv(u))
    assert "no están disponibles" in res["mensajes"][-1].cuerpo


# ── Acciones (escritura vía Dictado) ───────────────────────────────────────────

def test_accion_crea_dictado_pendiente(monkeypatch, usuario_factory, proyecto_factory):
    from apps.el_dictado.models import Dictado
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    fake, _ = _fake_analizar([{
        "tipo": "accion", "texto": "Te propongo:",
        "acciones": [{"tipo": "crear_tarea", "descripcion": "diseñar logo",
                      "payload": {"proyecto_slug": p.slug, "titulo": "logo"}, "confianza": 0.9}],
    }])
    monkeypatch.setattr(la, "analizar", fake)
    res = conversar(mensaje="crea tarea", usuario=u, conversacion=_conv(u))
    d = res["dictado"]
    assert d is not None
    assert d.origen == "taller_chat"
    assert d.estado == "esperando_confirmacion"
    assert d.acciones.count() == 1
    # NO se auto-aplicó.
    assert not d.acciones.filter(aplicada=True).exists()
    assert Dictado.objects.filter(pk=d.pk, origen="taller_chat").exists()


def test_accion_filtra_tipos_prohibidos(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    fake, _ = _fake_analizar([{
        "tipo": "accion", "texto": "ojo",
        "acciones": [{"tipo": "eliminar_entidad", "descripcion": "borra todo", "payload": {}, "confianza": 1.0}],
    }])
    monkeypatch.setattr(la, "analizar", fake)
    res = conversar(mensaje="borra", usuario=u, conversacion=_conv(u))
    assert res["dictado"].acciones.count() == 0


# ── Herramientas: gating, whitelist, recorte ────────────────────────────────────

def test_gating_finanzas_sin_permiso_no_corre_query(monkeypatch, usuario_factory):
    from apps.el_dictado import herramientas
    u = usuario_factory(rol="disenador")
    # Spy: si la query corriera, Factura.objects sería tocado. Verificamos
    # que la herramienta no esté ni listada y que el ejecutor la rechace.
    visibles = {h.nombre for h in herramientas.herramientas_para(u)}
    assert "detalle_factura" not in visibles
    salida = herramientas.ejecutar_herramienta("detalle_factura", {"codigo": "FAC-2026-0001"}, u)
    assert salida == {"error": "sin_permiso", "nombre": "detalle_factura"}


def test_estado_servidor_abierto_a_todos(usuario_factory):
    from apps.el_dictado import herramientas
    u = usuario_factory(rol="disenador")
    assert "estado_servidor" in {h.nombre for h in herramientas.herramientas_para(u)}
    salida = herramientas.ejecutar_herramienta("estado_servidor", {}, u)
    assert salida.get("error") != "sin_permiso"


def test_consultar_metrica_fuera_de_whitelist(usuario_factory):
    from apps.el_dictado import herramientas
    u = usuario_factory(rol="super_admin")
    salida = herramientas.ejecutar_herramienta("consultar_metrica", {"entidad": "usuario"}, u)
    assert "error" in salida


def test_args_invalidos(usuario_factory):
    from apps.el_dictado import herramientas
    u = usuario_factory(rol="super_admin")
    salida = herramientas.ejecutar_herramienta("consultar_kpi", {"campo_raro": 1}, u)
    assert salida["error"] == "args_invalidos"


def test_consultar_kpi_por_rol(usuario_factory):
    from apps.el_dictado import herramientas
    # ingresos-mes es ROLES_ADMIN_CONTADOR → un diseñador no lo ve.
    u = usuario_factory(rol="disenador")
    salida = herramientas.ejecutar_herramienta("consultar_kpi", {"slug": "ingresos-mes"}, u)
    assert salida.get("error") == "sin_permiso"


def test_recorte_trunca(usuario_factory):
    from apps.el_dictado.herramientas import recortar
    grande = {"datos": "x" * 5000}
    out = recortar(grande, max_chars=100)
    assert out.get("_truncado") is True


# ── Conversaciones / persistencia ───────────────────────────────────────────────

def test_crear_conversacion_deriva_titulo(usuario_factory):
    from apps.el_dictado.services_chat import crear_conversacion
    u = usuario_factory(rol="super_admin")
    c = crear_conversacion(usuario=u, mensaje_inicial="¿Cuántos proyectos activos hay hoy en el taller?")
    assert c.titulo.startswith("¿Cuántos proyectos")


def test_historial_capado_a_seis(monkeypatch, usuario_factory):
    from apps.el_dictado.services_chat import MAX_TURNOS_PROMPT, _historial_para_prompt, conversar

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    conv = _conv(u)
    fake, _ = _fake_analizar([{"tipo": "responder", "texto": "ok"}])
    monkeypatch.setattr(la, "analizar", fake)
    for n in range(5):
        conversar(mensaje=f"pregunta {n}", usuario=u, conversacion=conv)
    historial = _historial_para_prompt(conv)
    assert len(historial) <= MAX_TURNOS_PROMPT


# ── Views ───────────────────────────────────────────────────────────────────────

def test_nuevo_desde_dashboard_redirige(monkeypatch, client, usuario_factory):
    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    fake, _ = _fake_analizar([{"tipo": "responder", "texto": "ok"}])
    monkeypatch.setattr(la, "analizar", fake)
    resp = client.post("/chalan/nuevo", {"mensaje": "hola chalán"})
    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].startswith("/chalan/c/")


def test_enviar_htmx_devuelve_fragmento(monkeypatch, client, usuario_factory):
    from apps.el_dictado.services_chat import crear_conversacion

    import lib.analistas as la
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    conv = crear_conversacion(usuario=u)
    fake, _ = _fake_analizar([{"tipo": "responder", "texto": "respuesta del chalán"}])
    monkeypatch.setattr(la, "analizar", fake)
    resp = client.post(f"/chalan/c/{conv.pk}/enviar", {"mensaje": "hola"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert b"respuesta del chal" in resp.content


def test_enviar_requiere_login(client):
    resp = client.post("/chalan/c/1/enviar", {"mensaje": "hola"})
    assert resp.status_code in (302, 301)


# ── Fase A: herramientas de lectura nuevas (S-Chalan-Scope-OCR) ─────────────────

def test_mis_tareas_solo_del_usuario(usuario_factory, proyecto_factory):
    from apps.el_dictado import herramientas
    from apps.el_pizarron.models.tarea import Tarea
    u = usuario_factory(rol="disenador")
    otro = usuario_factory(rol="disenador")
    p = proyecto_factory()
    Tarea.objects.create(proyecto=p, titulo="Mía abierta", asignada_a=u)
    Tarea.objects.create(proyecto=p, titulo="Mía cerrada", asignada_a=u, estado="completada")
    Tarea.objects.create(proyecto=p, titulo="De otro", asignada_a=otro)
    salida = herramientas.ejecutar_herramienta("mis_tareas", {}, u)
    titulos = {t["titulo"] for t in salida["tareas"]}
    assert titulos == {"Mía abierta"}  # excluye completada y la de otro


def test_tareas_de_proyecto_por_codigo(usuario_factory, proyecto_factory):
    from apps.el_dictado import herramientas
    from apps.el_pizarron.models.tarea import Tarea
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    Tarea.objects.create(proyecto=p, titulo="T1")
    salida = herramientas.ejecutar_herramienta(
        "tareas_de_proyecto", {"proyecto_slug": p.codigo}, u
    )
    assert salida["proyecto"] == p.codigo
    assert any(t["titulo"] == "T1" for t in salida["tareas"])


def test_detalle_ingreso_requiere_finanzas(usuario_factory):
    from apps.el_dictado import herramientas
    u = usuario_factory(rol="disenador")
    assert "detalle_ingreso" not in {h.nombre for h in herramientas.herramientas_para(u)}
    salida = herramientas.ejecutar_herramienta("detalle_ingreso", {"codigo": "ING-2026-0001"}, u)
    assert salida == {"error": "sin_permiso", "nombre": "detalle_ingreso"}


def test_contaduria_balance_gating(usuario_factory):
    from apps.el_dictado import herramientas
    diseñador = usuario_factory(rol="disenador")
    assert "contaduria_balance" not in {h.nombre for h in herramientas.herramientas_para(diseñador)}
    admin = usuario_factory(rol="super_admin")
    assert "contaduria_balance" in {h.nombre for h in herramientas.herramientas_para(admin)}
    salida = herramientas.ejecutar_herramienta("contaduria_balance", {}, admin)
    assert salida.get("error") != "sin_permiso"


def test_buscar_respeta_permisos_por_entidad(usuario_factory, proyecto_factory):
    from apps.el_dictado import herramientas
    u = usuario_factory(rol="disenador")
    proyecto_factory(nombre="Proyecto Buscable XYZ")
    salida = herramientas.ejecutar_herramienta("buscar", {"texto": "Buscable"}, u)
    # diseñador no ve clientes/facturas/cotizaciones, solo proyectos
    assert "proyectos" in salida
    assert "facturas" not in salida and "cotizaciones" not in salida


def test_buscar_texto_muy_corto(usuario_factory):
    from apps.el_dictado import herramientas
    u = usuario_factory(rol="super_admin")
    salida = herramientas.ejecutar_herramienta("buscar", {"texto": "x"}, u)
    assert salida["error"] == "texto_muy_corto"


def test_proximos_eventos_abierto(usuario_factory, proyecto_factory):
    from datetime import date, timedelta

    from apps.el_dictado import herramientas
    u = usuario_factory(rol="super_admin")
    proyecto_factory(nombre="Entrega próxima", fecha_compromiso=date.today() + timedelta(days=3))
    salida = herramientas.ejecutar_herramienta("proximos_eventos", {"dias": 14}, u)
    assert salida.get("error") != "sin_permiso"
    assert "eventos" in salida
