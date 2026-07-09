"""S-LC-Proyecto-Render-V1: proveedor por producto + procesos (impresión +
gastos operativos), toggle de IVA, barra de status, sincronización de procesos.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def catalogo(db):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción Render Test")
    serv = Servicio.objects.create(nombre="Vasos PET", categoria=cat, precio_base=Decimal("100.00"), costo=Decimal("40.00"), activo=True)
    prov_a = Proveedor.objects.create(razon_social="Vasos Impresos", activo=True)
    prov_b = Proveedor.objects.create(razon_social="Marmotta Print", activo=True)
    return {"cat": cat, "serv": serv, "prov_a": prov_a, "prov_b": prov_b}


def _producto(proyecto, catalogo, **kw):
    from apps.los_proyectos.models import ProyectoProducto
    defaults = dict(
        servicio=catalogo["serv"], cantidad=2,
        precio_unitario=Decimal("100.00"), costo_unitario=Decimal("40.00"),
        incluir_en_calculo=True,
    )
    defaults.update(kw)
    return ProyectoProducto.objects.create(proyecto=proyecto, **defaults)


# ── Procesos: costos fijos que suman al costo de producción ──────────────────

def test_proceso_costo_es_fijo_no_por_cantidad(proyecto_factory, catalogo):
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory()
    pp = _producto(p, catalogo, cantidad=5)
    ProyectoProductoProceso.objects.create(producto=pp, tipo="impresion", proveedor=catalogo["prov_b"], costo=Decimal("50.00"))
    # cantidad=5 pero el costo del proceso NO se multiplica.
    assert pp.costo_procesos == Decimal("50.00")


def test_costo_produccion_incluye_procesos(proyecto_factory, catalogo):
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory()
    pp = _producto(p, catalogo, cantidad=2, costo_unitario=Decimal("40.00"))
    ProyectoProductoProceso.objects.create(producto=pp, tipo="impresion", proveedor=catalogo["prov_b"], costo=Decimal("50.00"))
    ProyectoProductoProceso.objects.create(producto=pp, tipo="operativo", descripcion="Clavos", costo=Decimal("30.00"))
    p.refresh_from_db()
    # costo_total_linea = 40 * 2 = 80; procesos = 50 + 30 = 80 → 160
    assert p.costo_produccion == Decimal("160.00")


def test_procesos_no_tocan_monto_calculado(proyecto_factory, catalogo):
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory()
    pp = _producto(p, catalogo, cantidad=2, precio_unitario=Decimal("100.00"))
    ProyectoProductoProceso.objects.create(producto=pp, tipo="impresion", proveedor=catalogo["prov_b"], costo=Decimal("999.00"))
    p.refresh_from_db()
    # Monto calculado = precio × cantidad, sin procesos.
    assert p.monto_calculado == Decimal("200.00")


def test_procesos_de_producto_excluido_no_cuentan(proyecto_factory, catalogo):
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory()
    pp = _producto(p, catalogo, incluir_en_calculo=False)
    ProyectoProductoProceso.objects.create(producto=pp, tipo="operativo", descripcion="X", costo=Decimal("500.00"))
    p.refresh_from_db()
    assert p.costo_produccion == Decimal("0.00")
    assert p.monto_calculado == Decimal("0.00")


# ── Deuda por proveedor + gastos operativos ──────────────────────────────────

def test_deuda_por_proveedor_suma_principal_e_impresion(proyecto_factory, catalogo):
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory()
    pp = _producto(p, catalogo, cantidad=2, costo_unitario=Decimal("40.00"), proveedor=catalogo["prov_a"])
    ProyectoProductoProceso.objects.create(producto=pp, tipo="impresion", proveedor=catalogo["prov_b"], costo=Decimal("50.00"))
    ProyectoProductoProceso.objects.create(producto=pp, tipo="operativo", descripcion="Embalaje", costo=Decimal("30.00"))
    p.refresh_from_db()
    deuda = {d["proveedor"].razon_social: d["total"] for d in p.deuda_por_proveedor()}
    assert deuda["Vasos Impresos"] == Decimal("80.00")   # 40 × 2
    assert deuda["Marmotta Print"] == Decimal("50.00")   # impresión
    # El gasto operativo (sin proveedor) NO aparece en la deuda.
    assert "Embalaje" not in deuda


def test_gastos_operativos_lista_con_descripcion(proyecto_factory, catalogo):
    from apps.los_proyectos.models import ProyectoProductoProceso
    p = proyecto_factory()
    pp = _producto(p, catalogo)
    ProyectoProductoProceso.objects.create(producto=pp, tipo="operativo", descripcion="Clavos", costo=Decimal("12.00"))
    ProyectoProductoProceso.objects.create(producto=pp, tipo="operativo", descripcion="Viáticos", costo=Decimal("88.00"))
    p.refresh_from_db()
    gastos = p.gastos_operativos()
    descripciones = {g["descripcion"] for g in gastos}
    assert descripciones == {"Clavos", "Viáticos"}
    assert p.gastos_operativos_total == Decimal("100.00")


# ── Sincronización de procesos desde JSON ────────────────────────────────────

def test_sincronizar_procesos_crea_impresion_y_operativos(proyecto_factory, catalogo):
    import json

    from apps.los_proyectos.services_procesos import sincronizar_procesos
    p = proyecto_factory()
    pp = _producto(p, catalogo)
    data = json.dumps([
        {"tipo": "impresion", "proveedor_id": catalogo["prov_b"].pk, "costo": 50},
        {"tipo": "operativo", "descripcion": "Pegamento", "costo": 25},
    ])
    sincronizar_procesos(pp, data)
    assert pp.procesos.count() == 2
    imp = pp.procesos.get(tipo="impresion")
    assert imp.proveedor_id == catalogo["prov_b"].pk
    assert imp.costo == Decimal("50.00")


def test_sincronizar_procesos_reemplaza_existentes(proyecto_factory, catalogo):
    import json

    from apps.los_proyectos.models import ProyectoProductoProceso
    from apps.los_proyectos.services_procesos import sincronizar_procesos
    p = proyecto_factory()
    pp = _producto(p, catalogo)
    ProyectoProductoProceso.objects.create(producto=pp, tipo="operativo", descripcion="viejo", costo=Decimal("1.00"))
    sincronizar_procesos(pp, json.dumps([{"tipo": "operativo", "descripcion": "nuevo", "costo": 9}]))
    assert pp.procesos.count() == 1
    assert pp.procesos.first().descripcion == "nuevo"


def test_sincronizar_procesos_descarta_proveedor_invalido(proyecto_factory, catalogo):
    import json

    from apps.los_proyectos.services_procesos import sincronizar_procesos
    p = proyecto_factory()
    pp = _producto(p, catalogo)
    sincronizar_procesos(pp, json.dumps([{"tipo": "impresion", "proveedor_id": 999999, "costo": 10}]))
    imp = pp.procesos.get(tipo="impresion")
    assert imp.proveedor_id is None  # id inválido → null, pero conserva el costo


def test_sincronizar_procesos_json_invalido_no_rompe(proyecto_factory, catalogo):
    from apps.los_proyectos.services_procesos import sincronizar_procesos
    p = proyecto_factory()
    pp = _producto(p, catalogo)
    sincronizar_procesos(pp, "{no es json")
    assert pp.procesos.count() == 0


# ── Régimen fiscal (LC 2026-07: reemplaza el toggle aplicar_iva) ─────────────

def test_form_inicial_regimen_refleja_instancia(proyecto_factory, catalogo):
    from apps.los_proyectos.forms import ProyectoForm
    p = proyecto_factory()
    p.regimen_fiscal = "honorarios"; p.save()
    assert ProyectoForm(instance=p).fields["regimen_fiscal"].initial == "honorarios"


def test_form_guarda_regimen_y_sincroniza_exento(proyecto_factory, catalogo):
    from apps.los_proyectos.forms import ProyectoForm
    p = proyecto_factory()
    data = {
        "nombre": p.nombre, "cliente": str(p.cliente_id),
        "descripcion": "", "estado": p.estado,
        "fecha_inicio_dia": "", "fecha_inicio_hora": "12:00",
        "fecha_compromiso_dia": "", "fecha_compromiso_hora": "12:00",
        "regimen_fiscal": "exento",
    }
    form = ProyectoForm(data, instance=p)
    assert form.is_valid(), form.errors
    form.save()
    p.refresh_from_db()
    assert p.regimen_fiscal == "exento"
    assert p.iva_exento is True
    assert p.iva_monto == Decimal("0.00")


def test_iva_monto_segun_exento(proyecto_factory, catalogo):
    p = proyecto_factory(iva_exento=False)
    _producto(p, catalogo, cantidad=1, precio_unitario=Decimal("100.00"))
    p.refresh_from_db()
    assert p.iva_monto == Decimal("16.00")
    p.iva_exento = True
    p.save(update_fields=["iva_exento"])
    p.refresh_from_db()
    assert p.iva_monto == Decimal("0.00")


# ── Barra de status ──────────────────────────────────────────────────────────

def test_barra_status_se_devuelve_en_cambio_inline(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="por_cotizar")
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/cambiar-estado",
        data={"estado": "en_proceso_produccion"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    p.refresh_from_db()
    assert p.estado == "en_proceso_produccion"
    assert f"proyecto-status-bar-{p.pk}".encode() in resp.content


def test_detalle_renderiza_barra_y_calendario(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="por_cotizar")
    client.force_login(admin)
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    assert f"proyecto-status-bar-{p.pk}".encode() in resp.content
    assert b"data-calendario" in resp.content
