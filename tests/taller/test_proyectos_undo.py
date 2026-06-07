"""Render-V2 — Undo del proyecto (snapshot/restaurar + pila coalescida en Redis).

La pila vive en Redis; aquí usamos un fake en memoria para no depender de un
Redis real en local. La lógica de restauración (lo riesgoso) se prueba directo
sobre la DB.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def catalogo(db):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción Undo Test")
    serv = Servicio.objects.create(nombre="Lonas", categoria=cat, precio_base=Decimal("100.00"), costo=Decimal("40.00"), activo=True)
    prov = Proveedor.objects.create(razon_social="Impresos Undo", activo=True)
    return {"cat": cat, "serv": serv, "prov": prov}


class _FakeRedis:
    """Subset mínimo de Redis usado por services_undo (decode_responses=True)."""

    def __init__(self):
        self.kv = {}
        self.lists = {}

    def get(self, k):
        return self.kv.get(k)

    def set(self, k, v, ex=None):
        self.kv[k] = str(v)

    def lpush(self, k, v):
        self.lists.setdefault(k, []).insert(0, v)

    def ltrim(self, k, a, b):
        if k in self.lists:
            self.lists[k] = self.lists[k][a:b + 1]

    def expire(self, k, t):
        pass

    def llen(self, k):
        return len(self.lists.get(k, []))

    def lpop(self, k):
        lst = self.lists.get(k, [])
        return lst.pop(0) if lst else None

    def delete(self, *ks):
        for k in ks:
            self.kv.pop(k, None)
            self.lists.pop(k, None)

    def pipeline(self):
        return self

    def execute(self):
        return []


@pytest.fixture
def fake_redis(monkeypatch):
    from apps.los_proyectos import services_undo
    fake = _FakeRedis()
    monkeypatch.setattr(services_undo, "_redis_client", fake)
    return fake


def _producto(proyecto, catalogo, **kw):
    from apps.los_proyectos.models import ProyectoProducto
    defaults = dict(servicio=catalogo["serv"], cantidad=2,
                    precio_unitario=Decimal("100.00"), costo_unitario=Decimal("40.00"),
                    incluir_en_calculo=True)
    defaults.update(kw)
    return ProyectoProducto.objects.create(proyecto=proyecto, **defaults)


# ── Snapshot / restauración (DB pura, sin Redis) ─────────────────────────────

def test_snapshot_captura_productos_procesos_equipo(proyecto_factory, catalogo, usuario_factory):
    from apps.los_proyectos import services_undo
    from apps.los_proyectos.models import ProyectoAsignacion, ProyectoProductoProceso
    p = proyecto_factory(nombre="Antes")
    pp = _producto(p, catalogo, cantidad=3)
    ProyectoProductoProceso.objects.create(producto=pp, tipo="impresion", proveedor=catalogo["prov"], costo=Decimal("50.00"))
    u = usuario_factory(rol="disenador")
    ProyectoAsignacion.objects.create(proyecto=p, usuario=u, rol_en_proyecto="lider")

    snap = services_undo.snapshot_estado(p)
    assert snap["proyecto"]["nombre"] == "Antes"
    assert len(snap["productos"]) == 1
    assert snap["productos"][0]["cantidad"] == 3
    assert len(snap["productos"][0]["procesos"]) == 1
    assert len(snap["equipo"]) == 1
    assert snap["equipo"][0]["rol_en_proyecto"] == "lider"


def test_restaurar_revierte_cambios(proyecto_factory, catalogo):
    from apps.los_proyectos import services_undo
    p = proyecto_factory(nombre="Original")
    _producto(p, catalogo, cantidad=2)
    snap = services_undo.snapshot_estado(p)

    # Mutamos: nombre + agregamos un producto.
    p.nombre = "Cambiado"
    p.save()
    _producto(p, catalogo, cantidad=9, precio_unitario=Decimal("5.00"))
    assert p.productos.count() == 2

    services_undo._restaurar(p, snap)
    p.refresh_from_db()
    assert p.nombre == "Original"
    assert p.productos.count() == 1
    assert p.productos.first().cantidad == 2


# ── Pila coalescida (Redis fake) ─────────────────────────────────────────────

def test_registrar_frame_coalesce(proyecto_factory, catalogo, fake_redis):
    from apps.los_proyectos import services_undo
    p = proyecto_factory()
    _producto(p, catalogo)
    services_undo.registrar_frame(p, ahora_ts=1000.0)
    # Dentro de la ventana de coalesce → NO agrega otro frame.
    services_undo.registrar_frame(p, ahora_ts=1005.0)
    assert services_undo.pasos_disponibles(p) == 1
    # Fuera de la ventana → SÍ agrega.
    services_undo.registrar_frame(p, ahora_ts=1100.0)
    assert services_undo.pasos_disponibles(p) == 2


def test_registrar_frame_tope_5(proyecto_factory, catalogo, fake_redis):
    from apps.los_proyectos import services_undo
    p = proyecto_factory()
    _producto(p, catalogo)
    for i in range(8):
        services_undo.registrar_frame(p, ahora_ts=1000.0 + i * 100)
    assert services_undo.pasos_disponibles(p) == 5


def test_deshacer_restaura_y_consume_frame(proyecto_factory, catalogo, fake_redis):
    from apps.los_proyectos import services_undo
    p = proyecto_factory(nombre="V1")
    _producto(p, catalogo, cantidad=2)
    services_undo.registrar_frame(p, ahora_ts=1000.0)

    p.nombre = "V2"
    p.save()
    _producto(p, catalogo, cantidad=7)
    assert p.productos.count() == 2

    assert services_undo.deshacer(p) is True
    p.refresh_from_db()
    assert p.nombre == "V1"
    assert p.productos.count() == 1
    # El frame se consumió.
    assert services_undo.pasos_disponibles(p) == 0


def test_deshacer_sin_frames_devuelve_false(proyecto_factory, fake_redis):
    from apps.los_proyectos import services_undo
    p = proyecto_factory()
    assert services_undo.deshacer(p) is False


# ── Render del detalle (smoke del rediseño Render-V2) ─────────────────────────

def test_detalle_render_v2_smoke(client, usuario_factory, proyecto_factory, catalogo, fake_redis):
    """El detalle rediseñado renderiza con productos: encabezado nombre+código,
    desglose económico, indicador de guardado y botón Deshacer."""
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Exte")
    _producto(p, catalogo, cantidad=2)
    client.force_login(admin)
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert p.codigo in html            # código junto al nombre
    assert "Exte" in html
    assert "guardado-indicador" in html  # indicador permanente
    assert "Deshacer" in html            # botón de undo
    assert "Productos involucrados" in html
    # Ya no existe el botón "Asignar" ni el título "Datos del proyecto".
    assert "Datos del proyecto" not in html


def test_deshacer_endpoint_post(client, usuario_factory, proyecto_factory, catalogo, fake_redis):
    from apps.los_proyectos import services_undo
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="V1")
    _producto(p, catalogo, cantidad=2)
    services_undo.registrar_frame(p, ahora_ts=1000.0)
    p.nombre = "V2"
    p.save()
    client.force_login(admin)
    resp = client.post(f"/proyectos/{p.pk}/deshacer", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect")
    p.refresh_from_db()
    assert p.nombre == "V1"
