"""S3 resto — cierre de periodo, ISR/PTU estimados, reconciliación
bancaria y export fiscal XML (Anexo 24, borrador).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _asiento_ingreso(monto, fecha):
    from apps.contaduria import services
    return services.crear_asiento(
        descripcion="Venta", fecha=fecha, origen="manual",
        partidas=[{"cuenta": "1.1.02", "cargo": Decimal(monto)},
                  {"cuenta": "4.1.01", "abono": Decimal(monto)}],
    )


def _asiento_egreso(monto, fecha):
    from apps.contaduria import services
    return services.crear_asiento(
        descripcion="Gasto", fecha=fecha, origen="manual",
        partidas=[{"cuenta": "5.1.01", "cargo": Decimal(monto)},
                  {"cuenta": "1.1.02", "abono": Decimal(monto)}],
    )


# ── E1: Cierre de periodo ────────────────────────────────────────────────

def test_cierre_genera_asiento_y_utilidad(usuario_factory):
    from apps.contaduria import services
    from apps.contaduria.models import CierrePeriodo
    u = usuario_factory(rol="dueno")
    desde, hasta = date(2026, 1, 1), date(2026, 1, 31)
    _asiento_ingreso("1000.00", date(2026, 1, 10))
    _asiento_egreso("400.00", date(2026, 1, 20))

    cierre = services.cerrar_periodo(desde=desde, hasta=hasta, actor=u)
    assert isinstance(cierre, CierrePeriodo)
    assert cierre.utilidad == Decimal("600.00")
    # El asiento de cierre cuadra (partida doble) y deja ingresos/egresos en 0.
    ast = cierre.asiento
    assert ast.origen == "cierre"
    cargos = sum((p.cargo for p in ast.partidas.all()), Decimal("0"))
    abonos = sum((p.abono for p in ast.partidas.all()), Decimal("0"))
    assert cargos == abonos
    cuenta_ingreso = services.cuenta_por_codigo("4.1.01")
    assert services.saldo_cuenta(cuenta_ingreso, desde=desde, hasta=hasta) == Decimal("0.00")
    # Utilidad fue a 3.2.02 (acreedora) como abono.
    util = services.cuenta_por_codigo("3.2.02")
    assert services.saldo_cuenta(util, hasta=hasta) == Decimal("600.00")


def test_cierre_idempotente(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    _asiento_ingreso("500.00", date(2026, 2, 5))
    a = services.cerrar_periodo(desde=date(2026, 2, 1), hasta=date(2026, 2, 28), actor=u)
    b = services.cerrar_periodo(desde=date(2026, 2, 1), hasta=date(2026, 2, 28), actor=u)
    assert a.pk == b.pk


def test_cierre_sin_movimiento_levanta(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    with pytest.raises(services.CierreInvalido):
        services.cerrar_periodo(desde=date(2030, 1, 1), hasta=date(2030, 1, 31), actor=u)


def test_reabrir_anula_y_permite_recerrar(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    _asiento_ingreso("800.00", date(2026, 3, 3))
    cierre = services.cerrar_periodo(desde=date(2026, 3, 1), hasta=date(2026, 3, 31), actor=u)
    asiento_id = cierre.asiento_id
    services.reabrir_periodo(cierre, actor=u, motivo="corregir captura")
    cierre.refresh_from_db()
    assert cierre.reabierto is True
    from apps.contaduria.models import Asiento
    assert Asiento.objects.get(pk=asiento_id).anulado is True
    # Tras reabrir se puede cerrar de nuevo (asiento nuevo, vigente).
    nuevo = services.cerrar_periodo(desde=date(2026, 3, 1), hasta=date(2026, 3, 31), actor=u)
    assert nuevo.pk != cierre.pk
    assert nuevo.asiento_id != asiento_id


def test_cierre_perdida_carga_utilidad(usuario_factory):
    from apps.contaduria import services
    u = usuario_factory(rol="dueno")
    _asiento_ingreso("200.00", date(2026, 4, 2))
    _asiento_egreso("500.00", date(2026, 4, 9))
    cierre = services.cerrar_periodo(desde=date(2026, 4, 1), hasta=date(2026, 4, 30), actor=u)
    assert cierre.utilidad == Decimal("-300.00")


# ── E2: ISR/PTU estimado ─────────────────────────────────────────────────

def _config_fiscal(**kw):
    """Fija la Configuración Fiscal (S-Finanzas-V3 la hizo editable)."""
    from ajustes.models import ConfiguracionFiscal
    cfg = ConfiguracionFiscal.obtener()
    for k, v in kw.items():
        setattr(cfg, k, v)
    cfg.save()
    return cfg


def test_estado_resultados_estima_isr_ptu():
    from apps.contaduria import reportes
    hoy = date.today()
    desde = hoy.replace(day=1)
    # Régimen general: ISR 30% sobre utilidad + PTU 10%.
    _config_fiscal(isr_base="utilidad", isr_tasa=Decimal("30.000"),
                   ptu_aplica=True, ptu_tasa=Decimal("10.000"))
    _asiento_ingreso("1000.00", hoy)
    _asiento_egreso("400.00", hoy)
    pl = reportes.estado_resultados(desde=desde, hasta=hoy)
    assert pl["utilidad_operativa"] == Decimal("600.00")
    assert pl["isr_estimado"] == Decimal("180.00")   # 30%
    assert pl["ptu_estimado"] == Decimal("60.00")     # 10%
    assert pl["utilidad_despues_impuestos"] == Decimal("360.00")


def test_estado_resultados_sin_impuestos_en_perdida():
    from apps.contaduria import reportes
    hoy = date.today()
    desde = hoy.replace(day=1)
    # ISR sobre utilidad: en pérdida no se estima nada.
    _config_fiscal(isr_base="utilidad", isr_tasa=Decimal("30.000"),
                   ptu_aplica=True, ptu_tasa=Decimal("10.000"))
    _asiento_ingreso("100.00", hoy)
    _asiento_egreso("500.00", hoy)
    pl = reportes.estado_resultados(desde=desde, hasta=hoy)
    assert pl["utilidad_operativa"] < 0
    assert pl["isr_estimado"] == Decimal("0.00")
    assert pl["ptu_estimado"] == Decimal("0.00")


# ── E3: Reconciliación bancaria ──────────────────────────────────────────

def _conc(usuario, saldo="0"):
    from apps.contaduria import conciliacion as cs
    cuenta = cs.cuentas_conciliables().get(codigo="1.1.02")
    return cs.crear_conciliacion(
        cuenta=cuenta, desde=date(2026, 5, 1), hasta=date(2026, 5, 31),
        saldo_estado_cuenta=Decimal(saldo), actor=usuario,
    )


def test_importar_csv_monto_firmado(usuario_factory):
    from apps.contaduria import conciliacion as cs
    u = usuario_factory(rol="dueno")
    conc = _conc(u)
    csv = "fecha,descripcion,monto\n2026-05-03,Depósito cliente,1500.00\n2026-05-10,Pago renta,-500.00\n"
    out = cs.importar_csv(conc, contenido=csv)
    assert out["creadas"] == 2 and not out["error"]
    montos = sorted(ln.monto for ln in conc.lineas.all())
    assert montos == [Decimal("-500.00"), Decimal("1500.00")]


def test_importar_csv_deposito_retiro(usuario_factory):
    from apps.contaduria import conciliacion as cs
    u = usuario_factory(rol="dueno")
    conc = _conc(u)
    csv = "fecha;deposito;retiro;concepto\n03/05/2026;1500;0;Depósito\n10/05/2026;0;500;Retiro\n"
    out = cs.importar_csv(conc, contenido=csv)
    assert out["creadas"] == 2
    montos = sorted(ln.monto for ln in conc.lineas.all())
    assert montos == [Decimal("-500.00"), Decimal("1500.00")]


def test_automatch_casa_por_monto_y_fecha(usuario_factory):
    from apps.contaduria import conciliacion as cs
    u = usuario_factory(rol="dueno")
    _asiento_ingreso("1500.00", date(2026, 5, 4))  # cargo a 1.1.02 = +1500
    conc = _conc(u)
    cs.importar_csv(conc, contenido="fecha,descripcion,monto\n2026-05-03,Depósito,1500.00\n")
    n = cs.automatch(conc)
    assert n == 1
    assert conc.lineas.get().conciliada is True


def test_match_y_desmatch_manual(usuario_factory):
    from apps.contaduria import conciliacion as cs
    from apps.contaduria.models import Partida
    u = usuario_factory(rol="dueno")
    ast = _asiento_ingreso("2000.00", date(2026, 5, 6))
    partida_banco = ast.partidas.get(cargo=Decimal("2000.00"))
    conc = _conc(u)
    cs.importar_csv(conc, contenido="fecha,descripcion,monto\n2026-05-06,Depósito,2000.00\n")
    linea = conc.lineas.get()
    cs.match_manual(linea, partida_banco)
    linea.refresh_from_db()
    assert linea.conciliada and linea.partida_id == partida_banco.pk
    cs.desmatch(linea)
    linea.refresh_from_db()
    assert not linea.conciliada and linea.partida_id is None
    assert isinstance(partida_banco, Partida)


def test_resumen_diferencia(usuario_factory):
    from apps.contaduria import conciliacion as cs
    u = usuario_factory(rol="dueno")
    _asiento_ingreso("1000.00", date(2026, 5, 2))  # saldo libros banco +1000
    conc = _conc(u, saldo="1000.00")
    res = cs.resumen(conc)
    assert res["saldo_libros"] == Decimal("1000.00")
    assert res["diferencia"] == Decimal("0.00")
    assert res["cuadrada"] is True


# ── E4: Export fiscal XML (Anexo 24, borrador) ───────────────────────────

def test_seed_agrupador_sat():
    from apps.contaduria.models import CuentaContable
    assert CuentaContable.objects.get(codigo="1.1.02").codigo_agrupador_sat == "102"
    assert CuentaContable.objects.get(codigo="4.1.01").codigo_agrupador_sat == "401"


def test_xml_polizas_bien_formado():
    from apps.contaduria import exports_xml
    _asiento_ingreso("1000.00", date(2026, 6, 5))
    xml = exports_xml.xml_polizas({"_desde": date(2026, 6, 1), "_hasta": date(2026, 6, 30)})
    root = ET.fromstring(xml)
    assert root.tag.endswith("Polizas")
    assert "RFC" in root.attrib


def test_xml_balanza_y_catalogo_parsean():
    from apps.contaduria import exports_xml
    _asiento_ingreso("500.00", date(2026, 6, 7))
    bal = exports_xml.xml_balanza({"_desde": date(2026, 6, 1), "_hasta": date(2026, 6, 30)})
    cat = exports_xml.xml_catalogo({"_hasta": date(2026, 6, 30)})
    assert ET.fromstring(bal).tag.endswith("Balanza")
    assert ET.fromstring(cat).tag.endswith("Catalogo")


def test_rfc_generico_si_falta_credencial():
    from apps.contaduria import exports_xml
    xml = exports_xml.xml_catalogo({"_hasta": date(2026, 6, 30)})
    assert "XAXX010101000" in xml


def test_responder_xml_content_type(usuario_factory):
    from apps.contaduria import exports_xml
    u = usuario_factory(rol="dueno")
    resp = exports_xml.responder_xml(
        "xml_catalogo", {"_hasta": date(2026, 6, 30)}, actor=u)
    assert resp["Content-Type"].startswith("application/xml")
    assert resp["Content-Disposition"].startswith("attachment")


# ── Smoke de vistas (renderizan los templates nuevos) ────────────────────

def test_cierre_lista_y_form_view(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    assert client.get("/contaduria/cierre/").status_code == 200
    assert client.get("/contaduria/cierre/nuevo/").status_code == 200


def test_conciliacion_views(client, usuario_factory):
    from apps.contaduria import conciliacion as cs
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    assert client.get("/contaduria/conciliacion/").status_code == 200
    assert client.get("/contaduria/conciliacion/nueva/").status_code == 200
    cuenta = cs.cuentas_conciliables().get(codigo="1.1.02")
    conc = cs.crear_conciliacion(
        cuenta=cuenta, desde=date(2026, 5, 1), hasta=date(2026, 5, 31), actor=u)
    assert client.get(f"/contaduria/conciliacion/{conc.pk}/").status_code == 200


def test_export_view_muestra_xml(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get("/contaduria/export/")
    assert resp.status_code == 200
    assert b"Export fiscal XML" in resp.content


def test_estado_resultados_view_renderiza_isr(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    _asiento_ingreso("1000.00", date.today())
    resp = client.get("/contaduria/estado-resultados/")
    assert resp.status_code == 200
    assert "ISR estimado" in resp.content.decode()


def test_descargar_xml_polizas_endpoint(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    _asiento_ingreso("500.00", date.today())
    resp = client.get("/contaduria/export/", {
        "descargar": "1", "formato": "xml_polizas",
        "desde": date.today().replace(day=1).isoformat(),
        "hasta": date.today().isoformat(),
    })
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/xml")
