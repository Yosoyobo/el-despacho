"""Tests de La Tesorería (S2b.3).

Cubre: modelos (códigos correlativos, soft delete), forms, CRUD views,
permisos, eventos Portavoz, exports CSV, queries CxC/CxP/reembolsos,
ejecutor `registrar_egreso` desde El Dictado.

NO cubre: OCR (S2b.3b — requiere Drive), export Sheets (S2b.3b — requiere
wrapper Sheets). Esos llegan junto con la activación de los wrappers.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture
def centro(db):
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.get(slug="insumos-de-proyecto")


@pytest.fixture
def make_ingreso(db, usuario_factory):
    from apps.tesoreria.models import Ingreso
    def _crear(**kwargs):
        defaults = {
            "monto": Decimal("100.00"), "fecha": date.today(),
            "descripcion": "Pago de prueba",
            "creado_por": kwargs.pop("creado_por", None) or usuario_factory(rol="dueno"),
        }
        defaults.update(kwargs)
        return Ingreso.objects.create(**defaults)
    return _crear


@pytest.fixture
def make_egreso(db, usuario_factory, centro):
    from apps.tesoreria.models import Egreso
    def _crear(**kwargs):
        defaults = {
            "monto": Decimal("50.00"), "fecha": date.today(),
            "descripcion": "Gasto de prueba", "centro_de_costo": centro,
            "creado_por": kwargs.pop("creado_por", None) or usuario_factory(rol="dueno"),
        }
        defaults.update(kwargs)
        return Egreso.objects.create(**defaults)
    return _crear


# ── Modelos ──────────────────────────────────────────────────────────────


def test_seed_centros_carga_diez():
    from apps.tesoreria.models import CentroDeCosto
    assert CentroDeCosto.objects.filter(activo=True).count() >= 10
    assert CentroDeCosto.objects.filter(slug="otros").exists()


def test_codigo_correlativo_ingreso(make_ingreso):
    anio = date.today().year
    i1 = make_ingreso()
    i2 = make_ingreso()
    assert i1.codigo == f"ING-{anio}-0001"
    assert i2.codigo == f"ING-{anio}-0002"


def test_codigo_correlativo_egreso(make_egreso):
    anio = date.today().year
    e1 = make_egreso()
    e2 = make_egreso()
    assert e1.codigo == f"EGR-{anio}-0001"
    assert e2.codigo == f"EGR-{anio}-0002"


def test_egreso_centro_protect(centro, make_egreso):
    """No se puede borrar un centro de costo con egresos asociados."""
    from django.db.models import ProtectedError
    make_egreso()
    with pytest.raises(ProtectedError):
        centro.delete()


def test_anular_marca_anulado_y_motivo(make_ingreso, usuario_factory):
    from apps.tesoreria.services import anular_ingreso
    i = make_ingreso()
    actor = usuario_factory(rol="super_admin")
    anular_ingreso(i, actor, "duplicado")
    i.refresh_from_db()
    assert i.anulado is True
    assert i.anulado_por_id == actor.pk
    assert i.motivo_anulacion == "duplicado"


def test_manager_vigentes_omite_anulados(make_ingreso, usuario_factory):
    from apps.tesoreria.models import Ingreso
    from apps.tesoreria.services import anular_ingreso
    a = make_ingreso()
    make_ingreso()
    anular_ingreso(a, usuario_factory(rol="super_admin"), "test")
    assert Ingreso.vigentes.count() == 1
    assert Ingreso.objects.count() == 2


# ── Forms ────────────────────────────────────────────────────────────────


def test_form_ingreso_rechaza_monto_cero():
    from apps.tesoreria.forms import IngresoForm
    form = IngresoForm(data={"subtotal": "0", "fecha": "2026-05-19",
                              "descripcion": "x", "moneda": "MXN",
                              "metodo": "tarjeta"})
    assert not form.is_valid()
    assert "subtotal" in form.errors


def test_form_egreso_tarjeta_personal_fuerza_reembolso(centro):
    """LC 2026-07: método personal muta el estado a «Por reembolsar» solo
    (coerción defensiva), sin error."""
    from apps.el_catalogo.models import Proveedor
    from apps.tesoreria.forms import EgresoForm
    prov = Proveedor.objects.create(razon_social="Insumos SA", activo=True)
    form = EgresoForm(data={
        "subtotal": "100", "fecha": "2026-05-19", "descripcion": "x",
        "moneda": "MXN", "proveedor": prov.pk, "centro_de_costo": centro.pk,
        "estado_pago": "pagado", "metodo": "tarjeta_personal",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["estado_pago"] == "por_reembolsar"


def test_egreso_con_iva_calcula_total(client, usuario_factory, centro):
    """incluye_iva → monto = subtotal×1.16. LC 2026-07: proveedor obligatorio."""
    from apps.el_catalogo.models import Proveedor
    actor = usuario_factory(rol="dueno")
    client.force_login(actor)
    prov = Proveedor.objects.create(razon_social="Papelería SA", creado_por=actor)
    resp = client.post("/tesoreria/egresos/nuevo/", {
        "subtotal": "100", "incluye_iva": "on", "fecha": "2026-05-19",
        "descripcion": "Con IVA", "proveedor": prov.pk,
        "centro_de_costo": centro.pk, "proyecto": "",
        "pagado_por": actor.pk, "solicitado_por": "",
        "estado_pago": "pagado", "metodo": "transferencia", "moneda": "MXN",
    })
    assert resp.status_code == 302
    from apps.tesoreria.models import Egreso
    e = Egreso.objects.get()
    assert e.subtotal == Decimal("100")
    assert e.incluye_iva is True
    assert e.monto == Decimal("116.00")
    assert e.proveedor_nombre == "Papelería SA"


def test_egreso_sin_proveedor_rechazado(client, usuario_factory, centro):
    """LC 2026-07: un egreso sin proveedor ya no se acepta (form inválido)."""
    actor = usuario_factory(rol="dueno")
    client.force_login(actor)
    resp = client.post("/tesoreria/egresos/nuevo/", {
        "subtotal": "100", "fecha": "2026-05-19", "descripcion": "Sin prov",
        "proveedor": "", "centro_de_costo": centro.pk, "proyecto": "",
        "pagado_por": actor.pk, "solicitado_por": "",
        "estado_pago": "pagado", "metodo": "transferencia", "moneda": "MXN",
    })
    assert resp.status_code == 200  # re-render con error, no redirect
    from apps.tesoreria.models import Egreso
    assert Egreso.objects.count() == 0


def test_egreso_desde_proyecto_liga_y_asigna_proveedor(client, usuario_factory, centro, cliente_factory):
    """Egreso creado con ?proyecto&next se liga al proyecto, asigna el proveedor
    y redirige de vuelta al proyecto (commit 11)."""
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.models import Proyecto
    from apps.los_proyectos.models.proveedor_proyecto import ProyectoProveedor
    actor = usuario_factory(rol="dueno")
    client.force_login(actor)
    proy = Proyecto.objects.create(nombre="Demo", cliente=cliente_factory(), creado_por=actor)
    prov = Proveedor.objects.create(razon_social="Maquilas SA", creado_por=actor)
    resp = client.post(
        f"/tesoreria/egresos/nuevo/?proyecto={proy.pk}&next=/proyectos/{proy.pk}/",
        {
            "subtotal": "200", "fecha": "2026-05-19", "descripcion": "Maquila",
            "proveedor": prov.pk, "centro_de_costo": centro.pk, "proyecto": proy.pk,
            "pagado_por": actor.pk, "solicitado_por": "",
            "estado_pago": "pagado", "metodo": "transferencia", "moneda": "MXN",
        },
    )
    assert resp.status_code == 302
    assert resp.url == f"/proyectos/{proy.pk}/"
    from apps.tesoreria.models import Egreso
    e = Egreso.objects.get()
    assert e.proyecto_id == proy.pk
    assert e.proveedor_id == prov.pk
    assert e.proveedor_nombre == "Maquilas SA"
    assert ProyectoProveedor.objects.filter(proyecto=proy, proveedor=prov).exists()


def test_get_forms_renderizan(client, usuario_factory):
    """Smoke: los forms de ingreso/egreso (mini-cal, IVA, semáforo) renderizan."""
    client.force_login(usuario_factory(rol="dueno"))
    assert client.get("/tesoreria/ingresos/nuevo/").status_code == 200
    assert client.get("/tesoreria/egresos/nuevo/").status_code == 200


# ── Permisos ─────────────────────────────────────────────────────────────


def test_disenador_no_ve_tesoreria(client, usuario_factory):
    client.force_login(usuario_factory(rol="disenador"))
    resp = client.get("/tesoreria/")
    assert resp.status_code == 403


def test_contador_ve_tesoreria(client, usuario_factory):
    client.force_login(usuario_factory(rol="contador"))
    resp = client.get("/tesoreria/")
    assert resp.status_code == 200


def test_dueno_ve_tesoreria(client, usuario_factory):
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.get("/tesoreria/")
    assert resp.status_code == 200


# ── Views CRUD ───────────────────────────────────────────────────────────


def test_crear_ingreso_genera_codigo_y_evento(client, usuario_factory, cliente_factory):
    client.force_login(usuario_factory(rol="dueno"))
    cli = cliente_factory()
    resp = client.post("/tesoreria/ingresos/nuevo/", {
        "subtotal": "1500", "fecha": "2026-05-19",
        "descripcion": "Anticipo proyecto", "cliente": cli.pk,
        "proyecto": "", "moneda": "MXN", "metodo": "transferencia",
        "referencia_externa": "",
    })
    assert resp.status_code == 302
    from apps.tesoreria.models import Ingreso
    i = Ingreso.objects.get()
    assert i.codigo.startswith("ING-")
    assert i.creado_por_id is not None
    assert i.monto == Decimal("1500")  # sin IVA → total = subtotal


def test_crear_egreso_por_reembolsar_dispara_evento(
    client, usuario_factory, centro, monkeypatch,
):
    """Estado por_reembolsar emite evento `tesoreria.reembolso_pendiente`."""
    emisiones = []
    import lib.portavoz as _portavoz
    monkeypatch.setattr(
        _portavoz, "emitir", lambda evt: emisiones.append(evt),
    )
    # Forzar que vista lo lea desde apps.tesoreria.views también
    import apps.tesoreria.views as _views
    monkeypatch.setattr(_views, "emitir", lambda evt: emisiones.append(evt))

    from apps.el_catalogo.models import Proveedor
    actor = usuario_factory(rol="dueno")
    client.force_login(actor)
    prov = Proveedor.objects.create(razon_social="Insumos SA", creado_por=actor)
    resp = client.post("/tesoreria/egresos/nuevo/", {
        "subtotal": "300", "fecha": "2026-05-19",
        "descripcion": "Insumos", "proveedor": prov.pk,
        "centro_de_costo": centro.pk, "proyecto": "",
        "pagado_por": actor.pk, "solicitado_por": "",
        "estado_pago": "por_reembolsar", "metodo": "tarjeta_personal",
        "moneda": "MXN",
    })
    assert resp.status_code == 302
    tipos = [e.tipo for e in emisiones]
    assert "tesoreria.egreso_registrado" in tipos
    assert "tesoreria.reembolso_pendiente" in tipos


def test_anular_requiere_motivo(client, usuario_factory, make_ingreso):
    client.force_login(usuario_factory(rol="super_admin"))
    i = make_ingreso()
    resp = client.post(f"/tesoreria/ingresos/{i.pk}/anular/", {"motivo": "no"})
    assert resp.status_code == 200  # form se re-renderiza con error
    i.refresh_from_db()
    assert i.anulado is False


def test_anular_con_motivo_valido(client, usuario_factory, make_egreso):
    client.force_login(usuario_factory(rol="super_admin"))
    e = make_egreso()
    resp = client.post(f"/tesoreria/egresos/{e.pk}/anular/",
                       {"motivo": "egreso duplicado, error de captura"})
    assert resp.status_code == 302
    e.refresh_from_db()
    assert e.anulado is True


# ── CxP / reembolsos ─────────────────────────────────────────────────────


def test_cxp_query_solo_no_pagados(make_egreso):
    from apps.tesoreria.services import cuentas_por_pagar_qs
    make_egreso(estado_pago="pagado")
    make_egreso(estado_pago="por_reembolsar")
    make_egreso(estado_pago="pendiente")
    assert cuentas_por_pagar_qs().count() == 2


def test_reembolsos_pendientes_agrupa_por_empleado(make_egreso, usuario_factory):
    from apps.tesoreria.services import reembolsos_pendientes
    maria = usuario_factory(rol="disenador")
    juan = usuario_factory(rol="disenador")
    make_egreso(pagado_por=maria, estado_pago="por_reembolsar", monto=Decimal("100"))
    make_egreso(pagado_por=maria, estado_pago="por_reembolsar", monto=Decimal("200"))
    make_egreso(pagado_por=juan, estado_pago="por_reembolsar", monto=Decimal("50"))
    res = reembolsos_pendientes()
    montos = {r["pagado_por"]: r["total"] for r in res}
    assert montos[maria.pk] == Decimal("300")
    assert montos[juan.pk] == Decimal("50")


# ── Reporte mensual ──────────────────────────────────────────────────────


def test_reporte_mensual_suma_ingresos_y_egresos(make_ingreso, make_egreso):
    from apps.tesoreria.services import reporte_mes
    hoy = date.today()
    make_ingreso(monto=Decimal("1000"))
    make_ingreso(monto=Decimal("500"))
    make_egreso(monto=Decimal("300"))
    r = reporte_mes(hoy.year, hoy.month)
    assert r["ingresos_total"] == Decimal("1500")
    assert r["egresos_total"] == Decimal("300")


# ── Export CSV ───────────────────────────────────────────────────────────


def test_export_csv_ingresos_encoding_y_bom(client, usuario_factory, make_ingreso):
    client.force_login(usuario_factory(rol="dueno"))
    make_ingreso(descripcion="Pago con acento á é í ó ú")
    resp = client.get("/tesoreria/exportar/ingresos.csv")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    body = resp.content
    # UTF-8 BOM (﻿ serializado como 3 bytes EF BB BF)
    assert body.startswith(b"\xef\xbb\xbf")
    # Encabezado localizado
    assert "Código".encode() in body
    # Acentos sobreviven
    assert "Pago con acento á é í ó ú".encode() in body


def test_export_csv_fechas_iso(client, usuario_factory, make_ingreso):
    client.force_login(usuario_factory(rol="dueno"))
    make_ingreso(fecha=date(2026, 3, 15))
    resp = client.get("/tesoreria/exportar/ingresos.csv")
    assert b"2026-03-15" in resp.content
    assert b"15/03/2026" not in resp.content


def test_export_csv_montos_decimal_punto(client, usuario_factory, make_ingreso):
    client.force_login(usuario_factory(rol="dueno"))
    make_ingreso(monto=Decimal("1234.56"))
    resp = client.get("/tesoreria/exportar/ingresos.csv")
    assert b"1234.56" in resp.content


def test_export_csv_egresos_respeta_filtro_centro(
    client, usuario_factory, make_egreso,
):
    from apps.tesoreria.models import CentroDeCosto
    otro = CentroDeCosto.objects.get(slug="nomina")
    client.force_login(usuario_factory(rol="dueno"))
    make_egreso(descripcion="Compra insumos")
    make_egreso(centro_de_costo=otro, descripcion="Sueldos quincena")
    resp = client.get("/tesoreria/exportar/egresos.csv?centro=insumos-de-proyecto")
    body = resp.content
    assert b"Compra insumos" in body
    assert b"Sueldos quincena" not in body


def test_export_movimientos_unifica_ingresos_egresos(
    client, usuario_factory, make_ingreso, make_egreso,
):
    client.force_login(usuario_factory(rol="dueno"))
    make_ingreso(descripcion="entrada A")
    make_egreso(descripcion="salida B")
    resp = client.get("/tesoreria/exportar/movimientos.csv")
    body = resp.content
    assert b"Ingreso" in body
    assert b"Egreso" in body
    assert b"entrada A" in body
    assert b"salida B" in body


def test_export_emite_telemetry(client, usuario_factory, monkeypatch):
    eventos = []
    import apps.tesoreria.views as _views
    monkeypatch.setattr(_views, "emitir", lambda evt: eventos.append(evt))
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.get("/tesoreria/exportar/ingresos.csv")
    assert resp.status_code == 200
    tipos = [e.tipo for e in eventos]
    assert "tesoreria.exportado" in tipos


def test_disenador_no_exporta(client, usuario_factory):
    client.force_login(usuario_factory(rol="disenador"))
    resp = client.get("/tesoreria/exportar/egresos.csv")
    assert resp.status_code == 403


# ── Centros de costo (Gerencia) ──────────────────────────────────────────


def test_centro_costo_super_admin_crea(client, usuario_factory, settings):
    from apps.tesoreria.models import CentroDeCosto
    settings.ROOT_URLCONF = "tests.urls_gerencia"
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/catalogos/centros-costo/nuevo/", {
        "nombre": "Insumos especiales", "descripcion": "x",
        "naturaleza": "operativo", "activo": "on",
    })
    assert resp.status_code == 302
    assert CentroDeCosto.objects.filter(slug="insumos-especiales").exists()


def test_centro_costo_dueno_no_administra(client, usuario_factory, settings):
    settings.ROOT_URLCONF = "tests.urls_gerencia"
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.get("/catalogos/centros-costo/")
    assert resp.status_code == 403
