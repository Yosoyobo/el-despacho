"""Segunda ronda del 2026-07-25 (clientes que no se podían eliminar + notas de LC).

- Cotizaciones: borrado permanente de anuladas/borradores (destraba al cliente).
- Campañas: el envío conserva al cliente como TEXTO (ya no bloquea el borrado).
- Cliente: el aviso enlista qué lo bloquea; la ficha muestra TODO lo ligado.
- Proyectos terminados: sin «vencido hace N días»; kanban «entregado {fecha}».
- Tesorería: botones de periodo (mes / año en curso).
- CxC y CxP: nombre del proyecto en vez del código.
- Detalle de ingreso/egreso: el proyecto es hipervínculo.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _cotizacion(cliente, autor, *, estado="anulada", proyecto=None, codigo="COT-2026-9001"):
    from apps.cotizaciones.models import Cotizacion
    return Cotizacion.objects.create(
        codigo=codigo, cliente=cliente, proyecto=proyecto, titulo="Propuesta",
        estado=estado, creado_por=autor, fecha_emision=dt.date(2026, 7, 1),
    )


def _factura(cliente, proyecto=None, estado="emitida"):
    from apps.facturacion.models import Factura
    return Factura.objects.create(
        cliente=cliente, proyecto=proyecto, estado=estado, concepto="Servicios",
        fecha_emision=dt.date(2026, 7, 1), fecha_vencimiento=dt.date(2026, 7, 31),
    )


# ── Cotizaciones: borrado permanente ─────────────────────────────────────


def test_super_admin_elimina_cotizacion_anulada(client, usuario_factory, cliente_factory):
    from apps.cotizaciones.models import Cotizacion
    autor = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=autor), autor, estado="anulada")
    client.force_login(autor)
    resp = client.post(f"/cotizaciones/{cot.pk}/eliminar/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == "/cotizaciones/"
    assert not Cotizacion.objects.filter(pk=cot.pk).exists()


def test_cotizacion_vigente_no_se_elimina(client, usuario_factory, cliente_factory):
    from apps.cotizaciones.models import Cotizacion
    autor = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=autor), autor, estado="aprobada")
    client.force_login(autor)
    modal = client.get(f"/cotizaciones/{cot.pk}/eliminar/", HTTP_HX_REQUEST="true")
    assert modal.status_code == 200
    assert "anúlala primero" in modal.content.decode()
    resp = client.post(f"/cotizaciones/{cot.pk}/eliminar/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204  # 204 + HX-Redirect al detalle, con el error
    assert Cotizacion.objects.filter(pk=cot.pk).exists()


def test_cotizacion_con_factura_no_se_elimina(client, usuario_factory, cliente_factory):
    from apps.cotizaciones.models import Cotizacion
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cot = _cotizacion(cli, autor, estado="anulada")
    fac = _factura(cli)
    fac.cotizacion_origen = cot
    fac.save(update_fields=["cotizacion_origen"])
    client.force_login(autor)
    client.post(f"/cotizaciones/{cot.pk}/eliminar/", HTTP_HX_REQUEST="true")
    assert Cotizacion.objects.filter(pk=cot.pk).exists()


def test_sin_permiso_no_elimina_cotizacion(client, usuario_factory, cliente_factory):
    autor = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=autor), autor)
    client.force_login(usuario_factory(rol="contador"))
    resp = client.post(f"/cotizaciones/{cot.pk}/eliminar/")
    assert resp.status_code == 403


def test_boton_eliminar_visible_solo_en_anulada(client, usuario_factory, cliente_factory):
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    anulada = _cotizacion(cli, autor, estado="anulada", codigo="COT-2026-9010")
    aprobada = _cotizacion(cli, autor, estado="aprobada", codigo="COT-2026-9011")
    client.force_login(autor)
    html_anulada = client.get(f"/cotizaciones/{anulada.pk}/").content.decode()
    html_aprobada = client.get(f"/cotizaciones/{aprobada.pk}/").content.decode()
    assert f"/cotizaciones/{anulada.pk}/eliminar/" in html_anulada
    assert f"/cotizaciones/{aprobada.pk}/eliminar/" not in html_aprobada


# ── Campañas: el envío sobrevive al borrado del cliente ──────────────────


def test_envio_de_campana_conserva_nombre_y_no_bloquea(usuario_factory, cliente_factory):
    from apps.la_cartera.models import Cliente

    from campanas.models import CampanaCorreo, CampanaEnvio
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor, razon_social="PXNDX")
    camp = CampanaCorreo.objects.create(plantilla_slug="generico", total_destinatarios=1)
    envio = CampanaEnvio.objects.create(
        campana=camp, cliente=cli, cliente_nombre=cli.razon_social,
        email="a@b.com", estado="enviado",
    )
    cli.delete()  # antes truchaba con ProtectedError
    envio.refresh_from_db()
    assert envio.cliente_id is None
    assert envio.cliente_nombre == "PXNDX"
    assert not Cliente.objects.filter(pk=cli.pk).exists()


# ── Cliente: bloqueos explícitos + ficha con todo lo ligado ──────────────


def test_cliente_bloqueado_por_cotizacion_lo_dice(client, usuario_factory, cliente_factory):
    """El caso reportado: no había facturas ni proyectos, pero la cotización
    (PROTECT) bloqueaba y el mensaje decía «facturas u otros movimientos»."""
    from apps.la_cartera.models import Cliente
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor, razon_social="LEARNING CENTER")
    cot = _cotizacion(cli, autor, estado="anulada")
    cli.activo = False
    cli.save(update_fields=["activo"])
    client.force_login(autor)
    resp = client.post(f"/cartera/{cli.pk}/eliminar", follow=True)
    assert Cliente.objects.filter(pk=cli.pk).exists()
    texto = " ".join(str(m) for m in resp.context["messages"])
    assert "Cotización" in texto and cot.codigo in texto


def test_cliente_sin_ligados_se_elimina(client, usuario_factory, cliente_factory):
    from apps.la_cartera.models import Cliente
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    cli.activo = False
    cli.save(update_fields=["activo"])
    client.force_login(autor)
    client.post(f"/cartera/{cli.pk}/eliminar")
    assert not Cliente.objects.filter(pk=cli.pk).exists()


def test_ficha_cliente_muestra_cotizaciones_facturas_ingresos(
        client, usuario_factory, cliente_factory, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = proyecto_factory(cliente=cli, creado_por=autor, nombre="Campaña verano")
    cot = _cotizacion(cli, autor, estado="enviada", proyecto=proy)
    fac = _factura(cli, proyecto=proy)
    ing = Ingreso.objects.create(
        codigo="ING-2026-9500", cliente=cli, proyecto=proy, monto=Decimal("500.00"),
        subtotal=Decimal("500.00"), descripcion="Anticipo", fecha=dt.date(2026, 7, 2),
    )
    client.force_login(autor)
    resp = client.get(f"/cartera/{cli.pk}/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert cot.codigo in html
    assert f"/facturacion/{fac.pk}/" in html
    assert ing.codigo in html
    ligado = resp.context["ligado"]
    assert len(ligado["cotizaciones"]) == 1
    assert len(ligado["facturas"]) == 1
    assert len(ligado["ingresos"]) == 1


# ── Proyectos terminados: sin «vencido hace N días» ──────────────────────


def test_proyecto_entregado_no_dice_vencido(proyecto_factory):
    from apps.los_proyectos.templatetags.proyectos_extras import (
        compromiso_clase,
        compromiso_kanban,
        compromiso_nota,
    )
    p = proyecto_factory(estado="entregado", fecha_compromiso=dt.date(2026, 7, 1))
    assert compromiso_nota(p) == ""              # la lista solo muestra la fecha
    assert "vencido" not in compromiso_kanban(p)
    assert compromiso_kanban(p).startswith("entregado ")
    assert "error" not in compromiso_clase(p)    # sin rojo de alarma


def test_proyecto_cancelado_solo_fecha(proyecto_factory):
    from apps.los_proyectos.templatetags.proyectos_extras import (
        compromiso_kanban,
        compromiso_nota,
    )
    p = proyecto_factory(estado="cancelado", fecha_compromiso=dt.date(2026, 7, 1))
    assert compromiso_nota(p) == ""
    assert "vencido" not in compromiso_kanban(p) and "entregado" not in compromiso_kanban(p)


def test_proyecto_activo_sigue_avisando_vencido(proyecto_factory):
    from apps.los_proyectos.templatetags.proyectos_extras import (
        compromiso_clase,
        compromiso_nota,
    )
    ayer = dt.date.today() - dt.timedelta(days=5)
    p = proyecto_factory(estado="en_proceso_produccion", fecha_compromiso=ayer)
    assert "vencido hace" in compromiso_nota(p)
    assert "error" in compromiso_clase(p)


# ── Tesorería: periodos ──────────────────────────────────────────────────


def test_resolver_periodo_mes_anio_y_default():
    from apps.tesoreria.services import resolver_periodo
    hoy = dt.date.today()
    mes = resolver_periodo("2026-05")
    assert mes["desde"] == dt.date(2026, 5, 1) and mes["hasta"] == dt.date(2026, 6, 1)
    anio = resolver_periodo("2026")
    assert anio["desde"] == dt.date(2026, 1, 1) and anio["hasta"] == dt.date(2027, 1, 1)
    default = resolver_periodo(None)
    assert default["desde"] == hoy.replace(day=1) and default["es_mes_actual"]
    # Basura → mes en curso (nunca revienta).
    assert resolver_periodo("no-es-fecha")["es_mes_actual"]
    assert resolver_periodo("1800-13")["es_mes_actual"]


def test_kpis_landing_respeta_el_rango(usuario_factory):
    from apps.tesoreria.models import Ingreso
    from apps.tesoreria.services import kpis_landing
    Ingreso.objects.create(codigo="ING-2026-9601", monto=Decimal("100.00"),
                           subtotal=Decimal("100.00"), descripcion="Mayo",
                           fecha=dt.date(2026, 5, 10))
    Ingreso.objects.create(codigo="ING-2026-9602", monto=Decimal("700.00"),
                           subtotal=Decimal("700.00"), descripcion="Junio",
                           fecha=dt.date(2026, 6, 10))
    u = usuario_factory(rol="super_admin")
    mayo = kpis_landing(u, desde=dt.date(2026, 5, 1), hasta=dt.date(2026, 6, 1))
    assert mayo["ingresos_mes"] == Decimal("100.00")
    anio = kpis_landing(u, desde=dt.date(2026, 1, 1), hasta=dt.date(2027, 1, 1))
    assert anio["ingresos_mes"] == Decimal("800.00")


def test_landing_pinta_botones_de_periodo(client, usuario_factory):
    from apps.tesoreria.models import Ingreso
    Ingreso.objects.create(codigo="ING-2026-9603", monto=Decimal("10.00"),
                           subtotal=Decimal("10.00"), descripcion="Viejo",
                           fecha=dt.date(2026, 5, 10))
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/tesoreria/")
    assert resp.status_code == 200
    claves = [p["clave"] for p in resp.context["periodos"]]
    assert claves[0] == str(dt.date.today().year)  # el año va primero
    assert "2026-05" in claves


# ── CxC / CxP / detalles: nombre del proyecto ───────────────────────────


def test_cxc_expone_nombre_y_url_del_proyecto(usuario_factory, cliente_factory,
                                              proyecto_factory):
    from apps.tesoreria.services import cxc_unificado
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = proyecto_factory(cliente=cli, creado_por=autor, nombre="Correas para las perras")
    fac = _factura(cli, proyecto=proy)
    from apps.facturacion.models import FacturaItem
    FacturaItem.objects.create(factura=fac, descripcion="Servicio", cantidad=1,
                               precio_unitario=Decimal("1000.00"))
    filas = [f for f in cxc_unificado() if f["tipo"] == "factura"]
    assert filas, "la factura emitida con saldo debe salir en CxC"
    assert filas[0]["proyecto_nombre"] == "Correas para las perras"
    assert filas[0]["proyecto_url"] == f"/proyectos/{proy.pk}/"


def test_por_pagar_muestra_nombre_del_proyecto(client, usuario_factory, cliente_factory,
                                               proyecto_factory):
    from apps.el_catalogo.models import Proveedor
    from apps.tesoreria.models import CentroDeCosto, Egreso
    autor = usuario_factory(rol="super_admin")
    proy = proyecto_factory(cliente=cliente_factory(creado_por=autor), creado_por=autor,
                            nombre="Playeras Heladería")
    centro = CentroDeCosto.objects.filter(activo=True).first() or CentroDeCosto.objects.create(
        nombre="Insumos", slug="insumos-jul25")
    Egreso.objects.create(
        codigo="EGR-2026-9700", monto=Decimal("300.00"), subtotal=Decimal("300.00"),
        descripcion="Maquila", fecha=dt.date(2026, 7, 3), centro_de_costo=centro,
        proyecto=proy, estado_pago="pendiente",
        proveedor=Proveedor.objects.create(razon_social="Maquilas SA", activo=True),
    )
    client.force_login(autor)
    html = client.get("/tesoreria/por-pagar/").content.decode()
    assert "Playeras Heladería" in html
    assert f"/proyectos/{proy.pk}/" in html


def test_detalle_ingreso_y_egreso_enlazan_al_proyecto(client, usuario_factory,
                                                      cliente_factory, proyecto_factory):
    from apps.tesoreria.models import CentroDeCosto, Egreso, Ingreso
    autor = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=autor)
    proy = proyecto_factory(cliente=cli, creado_por=autor, nombre="Mandiles Infantiles")
    ing = Ingreso.objects.create(codigo="ING-2026-9800", cliente=cli, proyecto=proy,
                                 monto=Decimal("100.00"), subtotal=Decimal("100.00"),
                                 descripcion="Cobro", fecha=dt.date(2026, 7, 4))
    centro = CentroDeCosto.objects.filter(activo=True).first() or CentroDeCosto.objects.create(
        nombre="Insumos", slug="insumos-jul25b")
    egr = Egreso.objects.create(codigo="EGR-2026-9800", monto=Decimal("50.00"),
                                subtotal=Decimal("50.00"), descripcion="Tela",
                                fecha=dt.date(2026, 7, 4), centro_de_costo=centro,
                                proyecto=proy)
    client.force_login(autor)
    for url in (f"/tesoreria/ingresos/{ing.pk}/", f"/tesoreria/egresos/{egr.pk}/"):
        html = client.get(url).content.decode()
        assert f'href="/proyectos/{proy.pk}/"' in html
        assert "Mandiles Infantiles" in html
