"""Fase 3 — El Chalán proactivo (propone, nunca actúa).

Mockean `lib.analistas.analizar` y `lib.interfono.enviar_a_usuario` para no
pegarle a un LLM ni al push real. Verifican: materialización de propuestas
(informativas y con acciones → Dictado pendiente), idempotencia, degradación
(IA caída / presupuesto topado), filtro de tipos prohibidos, scout, surface y
cierre del ciclo al aplicar.
"""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _res_ia(payload: dict):
    return SimpleNamespace(
        texto=json.dumps(payload), provider="anthropic", modelo="claude-haiku-4-5",
        prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1,
    )


def _mock_ia(monkeypatch, payload: dict):
    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", lambda *a, **k: _res_ia(payload))


def _mute_push(monkeypatch):
    """Neutraliza el push del Interfón (spy)."""
    import lib.interfono as inf
    llamadas = []
    monkeypatch.setattr(inf, "enviar_a_usuario", lambda *a, **k: llamadas.append((a, k)))
    return llamadas


# ── proponer ────────────────────────────────────────────────────────────────────

def test_proponer_informativa_sin_dictado(monkeypatch, usuario_factory):
    from apps.el_dictado.models import PropuestaChalan
    from apps.el_dictado.proactivo import proponer
    _mute_push(monkeypatch)
    _mock_ia(monkeypatch, {"texto": "Tienes 3 facturas vencidas.", "acciones": []})
    u = usuario_factory(rol="super_admin")
    prop = proponer(destinatario=u, tipo="digest", clave_dedup="k1",
                    titulo="Resumen", hechos="datos", permitir_acciones=False)
    assert prop is not None
    assert prop.dictado is None
    assert prop.estado == "pendiente"
    assert PropuestaChalan.objects.filter(usuario=u, clave_dedup="k1").count() == 1


def test_proponer_con_acciones_materializa_dictado_pendiente(monkeypatch, usuario_factory, proyecto_factory):
    from apps.el_dictado.proactivo import proponer
    _mute_push(monkeypatch)
    p = proyecto_factory()
    u = usuario_factory(rol="super_admin")
    _mock_ia(monkeypatch, {"texto": "Te propongo dar seguimiento.", "acciones": [
        {"tipo": "crear_tarea", "descripcion": "seguir factura",
         "payload": {"proyecto_slug": p.slug, "titulo": "seguimiento"}, "confianza": 0.8},
    ]})
    prop = proponer(destinatario=u, tipo="factura_vencida", clave_dedup="f:1",
                    titulo="Factura vencida", hechos="datos")
    assert prop.dictado is not None
    d = prop.dictado
    assert d.origen == "chalan_proactivo"
    assert d.estado == "esperando_confirmacion"
    assert d.acciones.count() == 1
    # NUNCA se auto-aplica: la acción queda sin confirmar ni aplicar.
    assert not d.acciones.filter(confirmada=True).exists()
    assert not d.acciones.filter(aplicada=True).exists()
    assert prop.url == f"/dictado/{d.pk}/preview"


def test_proponer_idempotente(monkeypatch, usuario_factory):
    from apps.el_dictado.models import PropuestaChalan
    from apps.el_dictado.proactivo import proponer
    _mute_push(monkeypatch)
    _mock_ia(monkeypatch, {"texto": "hola", "acciones": []})
    u = usuario_factory(rol="super_admin")
    a = proponer(destinatario=u, tipo="x", clave_dedup="dup", titulo="t", hechos="h", permitir_acciones=False)
    b = proponer(destinatario=u, tipo="x", clave_dedup="dup", titulo="t", hechos="h", permitir_acciones=False)
    assert a is not None and b is None
    assert PropuestaChalan.objects.filter(usuario=u, clave_dedup="dup").count() == 1


def test_proponer_ia_caida_no_crea(monkeypatch, usuario_factory):
    from apps.el_dictado.models import PropuestaChalan
    from apps.el_dictado.proactivo import proponer

    import lib.analistas as la
    _mute_push(monkeypatch)
    monkeypatch.setattr(la, "analizar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("caído")))
    u = usuario_factory(rol="super_admin")
    assert proponer(destinatario=u, tipo="x", clave_dedup="k", titulo="t", hechos="h") is None
    assert not PropuestaChalan.objects.filter(usuario=u).exists()


def test_proponer_presupuesto_topado_no_crea(monkeypatch, usuario_factory):
    from apps.el_dictado.models import PropuestaChalan
    from apps.el_dictado.proactivo import proponer

    import lib.analistas as la
    from lib.analistas import PresupuestoIAExcedido
    _mute_push(monkeypatch)

    def topado(*a, **k):
        raise PresupuestoIAExcedido("tope alcanzado")

    monkeypatch.setattr(la, "analizar", topado)
    u = usuario_factory(rol="super_admin")
    assert proponer(destinatario=u, tipo="x", clave_dedup="k", titulo="t", hechos="h") is None
    assert not PropuestaChalan.objects.filter(usuario=u).exists()


def test_proponer_filtra_tipos_prohibidos(monkeypatch, usuario_factory):
    from apps.el_dictado.proactivo import proponer
    _mute_push(monkeypatch)
    _mock_ia(monkeypatch, {"texto": "ojo", "acciones": [
        {"tipo": "eliminar_entidad", "descripcion": "borrar", "payload": {}, "confianza": 1.0},
    ]})
    u = usuario_factory(rol="super_admin")
    prop = proponer(destinatario=u, tipo="x", clave_dedup="k", titulo="t", hechos="h")
    # La única acción era prohibida → sin dictado, propuesta sigue siendo informativa.
    assert prop is not None
    assert prop.dictado is None


def test_proponer_manda_push(monkeypatch, usuario_factory):
    from apps.el_dictado.proactivo import CATEGORIA_PUSH, proponer
    llamadas = _mute_push(monkeypatch)
    _mock_ia(monkeypatch, {"texto": "aviso", "acciones": []})
    u = usuario_factory(rol="super_admin")
    proponer(destinatario=u, tipo="x", clave_dedup="k", titulo="t", hechos="h", permitir_acciones=False)
    assert len(llamadas) == 1
    assert llamadas[0][1]["categoria"] == CATEGORIA_PUSH


# ── scouts ────────────────────────────────────────────────────────────────────────

def test_scout_proyectos_estancados(monkeypatch, usuario_factory, proyecto_factory):
    from apps.el_dictado.models import PropuestaChalan
    from apps.el_dictado.scouts import scout_proyectos_estancados
    from apps.los_proyectos.models import Proyecto
    from django.utils import timezone
    _mute_push(monkeypatch)
    _mock_ia(monkeypatch, {"texto": "Este proyecto lleva días sin avanzar.", "acciones": []})
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="en_proceso_diseno")
    # actualizado_en es auto_now → forzamos una fecha vieja por queryset.
    Proyecto.objects.filter(pk=p.pk).update(actualizado_en=timezone.now() - timedelta(days=20))
    n = scout_proyectos_estancados()
    assert n >= 1
    assert PropuestaChalan.objects.filter(usuario=admin, tipo="proyecto_estancado").exists()


# ── surface + cierre de ciclo ───────────────────────────────────────────────────

def test_descartar_propuesta(client, monkeypatch, usuario_factory):
    from apps.el_dictado.proactivo import proponer
    _mute_push(monkeypatch)
    _mock_ia(monkeypatch, {"texto": "x", "acciones": []})
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    prop = proponer(destinatario=u, tipo="x", clave_dedup="k", titulo="t", hechos="h", permitir_acciones=False)
    resp = client.post(f"/chalan/propuesta/{prop.pk}/descartar")
    assert resp.status_code in (302, 303)
    prop.refresh_from_db()
    assert prop.estado == "descartada"


def test_home_muestra_propuesta(client, monkeypatch, usuario_factory):
    from apps.el_dictado.proactivo import proponer
    _mute_push(monkeypatch)
    _mock_ia(monkeypatch, {"texto": "Revisa esto.", "acciones": []})
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    proponer(destinatario=u, tipo="x", clave_dedup="k", titulo="Algo que revisar",
             hechos="h", permitir_acciones=False)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"El Chal" in resp.content and b"Algo que revisar" in resp.content


def test_aplicar_dictado_cierra_propuesta(monkeypatch, usuario_factory, proyecto_factory):
    from apps.el_dictado.proactivo import proponer
    from apps.el_dictado.services import aplicar
    _mute_push(monkeypatch)
    p = proyecto_factory()
    u = usuario_factory(rol="super_admin")
    _mock_ia(monkeypatch, {"texto": "seguimiento", "acciones": [
        {"tipo": "crear_tarea", "descripcion": "t",
         "payload": {"proyecto_slug": p.slug, "titulo": "seguir"}, "confianza": 0.9},
    ]})
    prop = proponer(destinatario=u, tipo="x", clave_dedup="k", titulo="t", hechos="h")
    d = prop.dictado
    d.acciones.update(confirmada=True)
    aplicar(dictado=d, usuario=u)
    prop.refresh_from_db()
    assert prop.estado == "aplicada"
