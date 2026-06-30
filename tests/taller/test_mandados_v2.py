"""S-Mandados-V2 — ejecutor crear_mandado del Chalán, push a involucrados y
gating del item/widget de Mandados (solo runners)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _accion(payload):
    return SimpleNamespace(payload=payload, entidad_tipo=None, entidad_id=None)


def _runner(usuario_factory):
    from cuentas.models.rol import Rol
    u = usuario_factory(rol="disenador", email="run@lc.mx")
    u.roles_extra.add(Rol.objects.get(clave="runner"))
    return u


# ── Ejecutor crear_mandado ────────────────────────────────────────────────────

def test_crear_mandado_con_coords(proyecto_factory, usuario_factory, _on_commit_inmediato):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.el_pizarron.models import Mandado, Tarea
    p = proyecto_factory(estado="en_proceso_diseno")
    admin = usuario_factory(rol="super_admin")
    accion = _accion({
        "proyecto_slug": p.slug, "titulo": "Recoger lonas", "tipo": "recoger",
        "destino_lat": 19.43, "destino_lng": -99.13, "destino_texto": "Bodega",
    })
    EJECUTORES["crear_mandado"](accion, admin, {})
    t = Tarea.objects.get(pk=accion.entidad_id)
    assert t.tipo == "recoger"
    assert t.destino_lat == 19.43 and t.destino_lng == -99.13
    assert t.destino_etiqueta == "Bodega"
    assert Mandado.objects.filter(tarea=t).exists()


def test_crear_mandado_por_direccion(proyecto_factory, usuario_factory, monkeypatch, _on_commit_inmediato):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.el_pizarron.models import Tarea

    import lib.geocoding as geo
    monkeypatch.setattr(geo, "primer_resultado",
                        lambda t: {"lat": 20.0, "lng": -100.0, "nombre": "Av X 123"})
    p = proyecto_factory(estado="en_proceso_diseno")
    admin = usuario_factory(rol="super_admin")
    accion = _accion({"proyecto_slug": p.slug, "titulo": "Entrega", "tipo": "entrega",
                      "destino_texto": "Av X 123, CDMX"})
    EJECUTORES["crear_mandado"](accion, admin, {})
    t = Tarea.objects.get(pk=accion.entidad_id)
    assert t.destino_lat == 20.0 and t.destino_lng == -100.0


def test_crear_mandado_por_poi(proyecto_factory, usuario_factory, monkeypatch, _on_commit_inmediato):
    import apps.el_pizarron.poi as poi
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.el_pizarron.models import Tarea
    monkeypatch.setattr(poi, "resolver_poi",
                        lambda txt: {"lat": 19.5, "lng": -99.2, "label": "Sucursal Centro"})
    p = proyecto_factory(estado="en_proceso_diseno")
    admin = usuario_factory(rol="super_admin")
    accion = _accion({"proyecto_slug": p.slug, "titulo": "Recoger", "poi": "Sucursal Centro"})
    EJECUTORES["crear_mandado"](accion, admin, {})
    t = Tarea.objects.get(pk=accion.entidad_id)
    assert t.destino_lat == 19.5 and t.destino_etiqueta == "Sucursal Centro"


def test_crear_mandado_sin_titulo_falla(proyecto_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    p = proyecto_factory(estado="en_proceso_diseno")
    admin = usuario_factory(rol="super_admin")
    with pytest.raises(ValueError, match="titulo"):
        EJECUTORES["crear_mandado"](_accion({"proyecto_slug": p.slug, "titulo": ""}), admin, {})


# ── Push a involucrados ───────────────────────────────────────────────────────

def test_completar_tarea_notifica_involucrados(proyecto_factory, usuario_factory, monkeypatch, _on_commit_inmediato):
    from apps.el_pizarron.models import Mandado, Tarea
    enviados = []
    import lib.interfono as interfono
    monkeypatch.setattr(interfono, "enviar_a_usuario",
                        lambda usuario, **kw: enviados.append((usuario.pk, kw.get("categoria"))))
    p = proyecto_factory(estado="en_proceso_diseno")
    creador = usuario_factory(rol="super_admin", email="creador@lc.mx")
    t = Tarea.objects.create(proyecto=p, titulo="Entrega", tipo="entrega",
                             estado="pendiente", creado_por=creador)
    Mandado.objects.get(tarea=t)
    t.estado = "completada"
    t.save()  # dispara sync → entregado → push
    assert any(cat == "mandados" for (_pk, cat) in enviados)
    assert any(pk == creador.pk for (pk, _cat) in enviados)


# ── S-LC-Feedback-V13: Mandados se fusionó en Tareas (ya no es item del menú) ──

def test_sidebar_mandados_fusionado_en_tareas(client, usuario_factory):
    # El atajo a /mandados/ desaparece del sidebar: ahora se llega vía Tareas
    # (filtro [Mandados]). El item de Tareas sí está visible para todos.
    u = usuario_factory(rol="disenador", email="nrunner@lc.mx")
    client.force_login(u)
    body = client.get("/").content.decode()
    assert 'href="/mandados/"' not in body
    assert 'href="/tareas/"' in body
