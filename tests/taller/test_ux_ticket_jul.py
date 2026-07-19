"""Ticket UX 2026-07 (Kanban, tarjetas, gastos @proveedor, dashboard, calendario).

Cubre las mejoras de UX del ticket:
- Kanban muestra SOLO productos incluidos (toggle On) con su cantidad.
- Gastos operativos pueden ligar un proveedor (@) → suma a su deuda; deja de
  contarse en gastos_operativos (sin doble conteo).
- Endpoint de autocompletar proveedores para el disparador @.
- Calendario: el selector de color del modal rellena el swatch y persiste HEX.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _servicio(nombre="Producto X"):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat UX")
    return Servicio.objects.create(
        nombre=nombre, categoria=cat, precio_base=Decimal("100.00"),
        costo=Decimal("40.00"), activo=True,
    )


# ── #3: gasto operativo con proveedor (@) ────────────────────────────────


def test_operativo_liga_proveedor_suma_a_deuda(proyecto_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_procesos

    prov = Proveedor.objects.create(razon_social="Fletes MX", activo=True)
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=1, incluir_en_calculo=True,
    )
    sincronizar_procesos(pp, json.dumps([
        {"tipo": "operativo", "descripcion": "Fletes", "costo": "300.00",
         "por_pieza": False, "proveedor_id": prov.pk},
    ]))
    procs = list(pp.procesos.all())
    assert len(procs) == 1
    assert procs[0].proveedor_id == prov.pk
    # El costo suma a la deuda del proveedor…
    deuda = p.deuda_por_proveedor()
    assert any(d["proveedor"].pk == prov.pk and d["total"] == Decimal("300.00") for d in deuda)
    # …y ya NO aparece en gastos_operativos (sin doble conteo).
    assert all("Fletes" not in g["descripcion"] for g in p.gastos_operativos())


def test_proveedor_arroba_aparece_en_panel_del_proyecto(client, proyecto_factory, usuario_factory):
    """El proveedor ligado por @ a un gasto operativo aparece en el recuadro de
    Proveedores del proyecto (con su costo), no solo en la deuda."""
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_procesos

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    prov = Proveedor.objects.create(razon_social="Empaques ARROBA", activo=True)
    p = proyecto_factory(creado_por=u)
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=1, incluir_en_calculo=True,
    )
    sincronizar_procesos(pp, json.dumps([
        {"tipo": "operativo", "descripcion": "Embalaje", "costo": "200.00",
         "por_pieza": False, "proveedor_id": prov.pk},
    ]))
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    assert b"Empaques ARROBA" in resp.content
    # Y ya NO existe el recuadro "Proveedores aplicables".
    assert b"Proveedores aplicables" not in resp.content


def test_operativo_sin_proveedor_sigue_en_gastos_operativos(proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.services_procesos import sincronizar_procesos

    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=1, incluir_en_calculo=True,
    )
    sincronizar_procesos(pp, json.dumps([
        {"tipo": "operativo", "descripcion": "Clavos", "costo": "50.00", "por_pieza": False},
    ]))
    assert any("Clavos" in g["descripcion"] for g in p.gastos_operativos())
    assert p.deuda_por_proveedor() == []


def test_proveedor_buscar_endpoint(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    Proveedor.objects.create(razon_social="Karhim Textil", activo=True)
    Proveedor.objects.create(razon_social="Otro Distinto", activo=True)
    resp = client.get("/catalogo/proveedores/buscar/?q=kar")
    assert resp.status_code == 200
    nombres = [r["nombre"] for r in resp.json()["resultados"]]
    assert "Karhim Textil" in nombres
    assert "Otro Distinto" not in nombres


# ── Tabla de tareas: estado inline + archivar (ticket UX 2026-07) ────────


def test_tabla_tareas_estado_inline_y_boton_archivar(client, proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = proyecto_factory(creado_por=u)
    t = Tarea.objects.create(proyecto=p, titulo="Diseñar logo", creado_por=u)
    body = client.get(f"/proyectos/{p.pk}/").content.decode()
    assert f"/tareas/{t.pk}/cambiar-estado" in body   # pastilla-select inline
    assert "estado-chip" in body
    assert f"/tareas/{t.pk}/archivar" in body          # botón X archivar


def test_archivar_tarea_htmx_quita_fila(client, proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = proyecto_factory(creado_por=u)
    t = Tarea.objects.create(proyecto=p, titulo="Archívame", creado_por=u)
    resp = client.post(f"/tareas/{t.pk}/archivar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert resp.content == b""  # cuerpo vacío → HTMX quita la fila
    t.refresh_from_db()
    assert t.archivada is True
    # Ya no aparece en el detalle del proyecto.
    assert "Archívame" not in client.get(f"/proyectos/{p.pk}/").content.decode()


# ── #1: Kanban muestra solo productos incluidos con cantidad ─────────────


def test_kanban_solo_productos_incluidos(client, proyecto_factory, usuario_factory):
    from apps.los_proyectos.models import ProyectoProducto

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = proyecto_factory(creado_por=u, estado="por_cotizar")
    ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio("PlayeraIncluida"), cantidad=3, incluir_en_calculo=True,
    )
    ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio("GorraExcluida"), cantidad=1, incluir_en_calculo=False,
    )
    resp = client.get("/proyectos/kanban/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "PlayeraIncluida" in body
    assert "GorraExcluida" not in body
    assert "3×" in body  # cantidad visible en el chip


# ── #5: calendario color ──────────────────────────────────────────────────


def test_factura_fecha_render_iso():
    """El widget de fecha renderiza en ISO (%Y-%m-%d) para que <input type=date>
    muestre el valor al editar (antes salía en blanco por el formato es-mx →
    daba la impresión de que "las fechas no se guardaban")."""
    import datetime

    from apps.facturacion.forms import FacturaForm
    from apps.facturacion.models import Factura

    f = FacturaForm(instance=Factura(
        fecha_emision=datetime.date(2026, 7, 19),
        fecha_vencimiento=datetime.date(2026, 8, 18),
    ))
    assert 'value="2026-07-19"' in str(f["fecha_emision"])
    assert 'value="2026-08-18"' in str(f["fecha_vencimiento"])


def test_evento_form_clean_color_lowercase():
    from apps.calendario.forms import EventoForm

    form = EventoForm(data={
        "titulo": "Feriado", "fecha_inicio": "2026-07-20", "fecha_fin": "",
        "color": "#12b76a", "descripcion": "",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["color"] == "#12b76a"


def test_evento_modal_swatches_con_color(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/calendario/evento/nuevo/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    # Antes el swatch salía sin color (radio.choice_value no existe en Django 5).
    assert "background: #465fff" in resp.content.decode()


def test_evento_crear_guarda_color(client, usuario_factory):
    from apps.el_pizarron.models import Evento

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/calendario/evento/nuevo/", {
        "titulo": "Inventario UX", "fecha_inicio": "2026-07-25", "fecha_fin": "",
        "color": "#f04438", "descripcion": "",
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code in (204, 302)
    ev = Evento.objects.get(titulo="Inventario UX")
    assert ev.color == "#f04438"
