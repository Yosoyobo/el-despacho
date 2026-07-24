"""Tests de S-Ajustes-Jul23 (VERSION 2026.07.23).

Cubre:
- Bloque A — Clientes: edición rápida por celda (nombre/teléfono/estado),
  teléfono sincroniza al contacto principal, razón social fiscal en el form,
  lista ?editar=1 renderiza filas editables + columna Teléfono.
- Bloque C — Factura: `cancelar` auto-sana el monto_cobrado fantasma,
  `cancelar_con_cobros` (cascada) anula los cobros y cancela, el detalle expone
  los movimientos ligados incluyendo anulados.
- Bloque D — Calculadora de costos: fórmula, gating por proveedor
  "Simil Cuero Plymouth", el POST de editar guarda insumos y alimenta el precio,
  y el fix de `save_m2m` persiste los proveedores marcados.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(
        _tx, "on_commit", lambda fn, using=None, robust=False: fn(),
    )


# ── Bloque A — Clientes ─────────────────────────────────────────────────


def test_celda_actualiza_nombre_en_mayusculas(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, razon_social="ACME")
    client.force_login(admin)
    r = client.post(reverse("cartera-cliente-celda", args=[cli.pk]),
                    {"campo": "razon_social", "valor": "nuevo nombre"})
    assert r.status_code == 204
    cli.refresh_from_db()
    assert cli.razon_social == "NUEVO NOMBRE"


def test_celda_telefono_sincroniza_contacto_principal(client, cliente_factory, usuario_factory):
    from apps.la_cartera.models import ClienteContacto
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    cp = ClienteContacto.objects.create(cliente=cli, nombre="Juan", telefono="000", principal=True)
    client.force_login(admin)
    r = client.post(reverse("cartera-cliente-celda", args=[cli.pk]),
                    {"campo": "telefono", "valor": "5551234"})
    assert r.status_code == 204
    cli.refresh_from_db()
    cp.refresh_from_db()
    assert cli.telefono == "5551234"
    assert cp.telefono == "5551234"  # el contacto principal (fuente de verdad) también


def test_celda_estado_invalido_rechaza(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    client.force_login(admin)
    r = client.post(reverse("cartera-cliente-celda", args=[cli.pk]),
                    {"campo": "estado", "valor": "inexistente"})
    assert r.status_code == 400
    r2 = client.post(reverse("cartera-cliente-celda", args=[cli.pk]),
                     {"campo": "estado", "valor": "inactivo"})
    assert r2.status_code == 204
    cli.refresh_from_db()
    assert cli.estado == "inactivo"


def test_celda_campo_no_editable_rechaza(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    client.force_login(admin)
    r = client.post(reverse("cartera-cliente-celda", args=[cli.pk]),
                    {"campo": "rfc", "valor": "XAXX010101000"})
    assert r.status_code == 400


def test_lista_editar_inline_renderiza_filas_editables(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cliente_factory(creado_por=admin)
    client.force_login(admin)
    r = client.get(reverse("cartera-lista") + "?editar=1")
    assert r.status_code == 200
    html = r.content.decode()
    assert "cartera-cliente-celda" not in html or "hx-post" in html  # hay endpoints de celda
    assert 'hx-vals=\'{"campo": "razon_social"}\'' in html
    assert "Salir de edición" in html


def test_lista_normal_tiene_columna_telefono(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cliente_factory(creado_por=admin)
    client.force_login(admin)
    r = client.get(reverse("cartera-lista"))
    assert r.status_code == 200
    assert "Teléfono" in r.content.decode()


def test_form_cliente_razon_social_fiscal_mayusculas():
    from apps.la_cartera.forms import ClienteForm
    form = ClienteForm(data={
        "razon_social": "acme comercial",
        "razon_social_fiscal": "acme sa de cv",
        "estado": "activo",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["razon_social_fiscal"] == "ACME SA DE CV"


def test_detalle_muestra_razon_social_fiscal(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, razon_social_fiscal="LEARNING CENTER SA")
    client.force_login(admin)
    r = client.get(reverse("cartera-detalle", args=[cli.pk]))
    assert r.status_code == 200
    assert "LEARNING CENTER SA" in r.content.decode()


# ── Bloque C — Factura ──────────────────────────────────────────────────


def _factura_emitida(cliente, autor, precio=Decimal("1000.00")):
    from apps.facturacion import services
    from apps.facturacion.models import Factura, FacturaItem
    fac = Factura.objects.create(cliente=cliente, titulo="F", creado_por=autor)
    FacturaItem.objects.create(factura=fac, orden=0, descripcion="X",
                               cantidad=Decimal("1"), unidad="pieza",
                               precio_unitario=precio, descuento_porcentaje=Decimal("0"))
    services.emitir_factura(fac, autor)
    return fac


def test_cancelar_autosana_monto_cobrado_fantasma(cliente_factory, usuario_factory):
    """Un Ingreso anulado sin recalcular deja monto_cobrado > 0 (fantasma). El
    nuevo `cancelar` recalcula desde vigentes y sí permite cancelar."""
    from apps.facturacion import services
    from apps.tesoreria.services import anular_ingreso

    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura_emitida(cli, autor)
    services.registrar_cobro(fac, monto=Decimal("500"), fecha=date.today(),
                             metodo="transferencia", actor=autor)
    cobro = fac.cobros.first()
    # Anulamos el Ingreso SIN recalcular la factura → monto_cobrado queda stale.
    anular_ingreso(cobro, autor, "prueba")
    fac.refresh_from_db()
    assert fac.monto_cobrado == Decimal("500.00")  # fantasma
    # Antes tronaba con "Anula primero los cobros"; ahora se auto-sana y cancela.
    services.cancelar(fac, autor, "limpieza")
    fac.refresh_from_db()
    assert fac.estado == "cancelada"
    assert fac.monto_cobrado == Decimal("0.00")


def test_cancelar_con_cobros_vigentes_sigue_bloqueando(cliente_factory, usuario_factory):
    """Con un cobro VIGENTE, `cancelar` (sin cascada) sigue bloqueando."""
    from apps.facturacion import services
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura_emitida(cli, autor)
    services.registrar_cobro(fac, monto=Decimal("100"), fecha=date.today(),
                             metodo="transferencia", actor=autor)
    fac.refresh_from_db()
    with pytest.raises(ValueError):
        services.cancelar(fac, autor, "intento")


def test_cancelar_con_cobros_cascada(cliente_factory, usuario_factory):
    """La cascada anula los cobros vigentes y cancela la factura de un jalón."""
    from apps.facturacion import services
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura_emitida(cli, autor)
    services.registrar_cobro(fac, monto=Decimal("300"), fecha=date.today(),
                             metodo="transferencia", actor=autor)
    cobro = fac.cobros.first()
    services.cancelar_con_cobros(fac, autor, "cliente canceló")
    fac.refresh_from_db()
    cobro.refresh_from_db()
    assert fac.estado == "cancelada"
    assert fac.monto_cobrado == Decimal("0.00")
    assert cobro.anulado is True


def test_modal_cancelar_con_cobros_ofrece_cascada(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    from apps.facturacion import services
    fac = _factura_emitida(cli, autor)
    services.registrar_cobro(fac, monto=Decimal("100"), fecha=date.today(),
                             metodo="transferencia", actor=autor)
    client.force_login(autor)
    r = client.get(reverse("facturacion:cancelar", args=[fac.pk]), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert 'name="forzar"' in html  # ofrece la cancelación en cascada
    assert "Cancelar y anular los cobros" in html


def test_detalle_muestra_movimientos_ligados_anulados(client, cliente_factory, usuario_factory):
    from apps.facturacion import services
    from apps.tesoreria.services import anular_ingreso
    from django.urls import reverse
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    fac = _factura_emitida(cli, autor)
    services.registrar_cobro(fac, monto=Decimal("200"), fecha=date.today(),
                             metodo="transferencia", actor=autor)
    cobro = fac.cobros.first()
    codigo = cobro.codigo
    anular_ingreso(cobro, autor, "prueba")
    client.force_login(autor)
    r = client.get(reverse("facturacion:detalle", args=[fac.pk]))
    assert r.status_code == 200
    html = r.content.decode()
    # El cobro anulado sigue visible (ya no "no lo encuentro").
    assert codigo in html
    assert "anulado" in html


# ── Bloque D — Calculadora de costos ────────────────────────────────────


def test_calculadora_formula():
    from apps.el_catalogo.calculadora import calcular
    det = {"materiales": ["10", "20"], "sublimacion": ["5", "5"],
           "mano_obra": "50", "factor": "2.2"}
    res = calcular(det, Decimal("16"))
    assert res["m1"] == Decimal("30")
    assert res["m2"] == Decimal("10")
    # Subtotal = (10 + 50) × 2.2 + 30 = 162
    assert res["subtotal"] == Decimal("162.00")
    assert res["iva"] == Decimal("25.92")
    assert res["total"] == Decimal("187.92")


def test_calculadora_material_no_multiplica():
    from apps.el_catalogo.calculadora import calcular
    # Solo material: nunca se multiplica por el factor.
    res = calcular({"materiales": ["100"], "sublimacion": [], "mano_obra": "0"}, Decimal("16"))
    assert res["subtotal"] == Decimal("100.00")


def _cat_prov_servicio(razon_prov="Simil Cuero Plymouth"):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat = CategoriaServicio.objects.create(nombre=f"Cat de {razon_prov}", orden=1)
    prov = Proveedor.objects.create(razon_social=razon_prov)
    srv = Servicio.objects.create(nombre="Portafolios", precio_base=Decimal("0"), categoria=cat)
    srv.proveedores.add(prov)
    return srv, prov


def test_servicio_usa_calculadora_gating():
    from apps.el_catalogo.calculadora import servicio_usa_calculadora
    srv, _ = _cat_prov_servicio("Simil Cuero Plymouth")
    assert servicio_usa_calculadora(srv) is True
    srv2, _ = _cat_prov_servicio("Otro Proveedor")
    assert servicio_usa_calculadora(srv2) is False


def test_editar_guarda_insumos_y_alimenta_precio(client, usuario_factory):
    from django.urls import reverse
    srv, prov = _cat_prov_servicio()
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    data = {
        "nombre": "Portafolios", "descripcion_default": "",
        "costo": "0", "precio_base": "500", "categoria": str(srv.categoria_id),
        "proveedores": str(prov.pk),  # el vínculo debe ir en el POST (save_m2m)
        "calc_material_0": "30", "calc_material_1": "", "calc_material_2": "", "calc_material_3": "",
        "calc_sublimacion_0": "10", "calc_sublimacion_1": "", "calc_sublimacion_2": "", "calc_sublimacion_3": "",
        "calc_mano_obra": "50",
    }
    r = client.post(reverse("catalogo-editar", args=[srv.pk]), data)
    assert r.status_code in (302, 200)
    srv.refresh_from_db()
    # Subtotal = (10 + 50) × 2.2 + 30 = 162 → alimenta el COSTO (R2).
    assert srv.costo == Decimal("162.00")
    # El PRECIO lo pone el usuario y NO se sobreescribe.
    assert srv.precio_base == Decimal("500.00")
    assert srv.detalles_costo.get("mano_obra") == "50"
    assert srv.detalles_costo.get("sublimacion")[0] == "10"


def test_editar_save_m2m_persiste_proveedores(client, usuario_factory):
    """Fix: el form completo antes NO guardaba los proveedores (faltaba save_m2m)."""
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from django.urls import reverse
    cat = CategoriaServicio.objects.create(nombre="Cat", orden=1)
    prov = Proveedor.objects.create(razon_social="Proveedor X")
    srv = Servicio.objects.create(nombre="P", precio_base=Decimal("100"), categoria=cat)
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    data = {
        "nombre": "P", "descripcion_default": "", "costo": "0",
        "precio_base": "100", "categoria": str(cat.pk), "proveedores": str(prov.pk),
    }
    r = client.post(reverse("catalogo-editar", args=[srv.pk]), data)
    assert r.status_code in (302, 200)
    srv.refresh_from_db()
    assert list(srv.proveedores.values_list("pk", flat=True)) == [prov.pk]


# ── R2 — refinamientos ───────────────────────────────────────────────────


def test_celda_razon_social_fiscal(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    client.force_login(admin)
    r = client.post(reverse("cartera-cliente-celda", args=[cli.pk]),
                    {"campo": "razon_social_fiscal", "valor": "acme sa de cv"})
    assert r.status_code == 204
    cli.refresh_from_db()
    assert cli.razon_social_fiscal == "ACME SA DE CV"


def test_edicion_rapida_columnas_y_pills(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cliente_factory(creado_por=admin)
    client.force_login(admin)
    html = client.get(reverse("cartera-lista") + "?editar=1").content.decode()
    assert "Razón social" in html          # columna nueva
    assert "Contacto" in html              # se recuperó
    assert "data-estado-pill" in html      # estado como pastillas de color
    assert 'hx-vals=\'{"campo": "razon_social_fiscal"}\'' in html
    assert "Ver →" not in html             # botón "Ver" removido


def test_lista_normal_sin_boton_ver(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cliente_factory(creado_por=admin)
    client.force_login(admin)
    html = client.get(reverse("cartera-lista")).content.decode()
    assert "Ver →" not in html


def test_eliminar_archivado_sin_proyectos(client, cliente_factory, usuario_factory):
    from apps.la_cartera.models import Cliente
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, activo=False)
    client.force_login(admin)
    r = client.post(reverse("cartera-cliente-eliminar", args=[cli.pk]))
    assert r.status_code == 302
    assert not Cliente.objects.filter(pk=cli.pk).exists()


def test_eliminar_activo_bloqueado(client, cliente_factory, usuario_factory):
    from apps.la_cartera.models import Cliente
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, activo=True)
    client.force_login(admin)
    r = client.post(reverse("cartera-cliente-eliminar", args=[cli.pk]))
    assert r.status_code == 302
    assert Cliente.objects.filter(pk=cli.pk).exists()  # no se borró (hay que archivar antes)


def test_eliminar_con_proyectos_bloqueado(client, cliente_factory, proyecto_factory, usuario_factory):
    from apps.la_cartera.models import Cliente
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, activo=False)
    proyecto_factory(cliente=cli, creado_por=admin)
    client.force_login(admin)
    r = client.post(reverse("cartera-cliente-eliminar", args=[cli.pk]))
    assert r.status_code == 302
    assert Cliente.objects.filter(pk=cli.pk).exists()  # bloqueado por proyecto ligado


def test_eliminar_sin_permiso_403(client, cliente_factory, usuario_factory):
    from django.urls import reverse
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, activo=False)
    disenador = usuario_factory(rol="disenador")
    client.force_login(disenador)
    r = client.post(reverse("cartera-cliente-eliminar", args=[cli.pk]))
    assert r.status_code == 403
