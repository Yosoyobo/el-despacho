"""Aprobar / rechazar una cotización desde el portal, y el botón «Pagar» de La Caja."""

from __future__ import annotations

import datetime as dt
import sys
import types
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def adentro(armar_cliente, acceso_de, entrar_como, client, monkeypatch):
    from django.db import transaction

    # §14 Bug E: los avisos van en `on_commit`, que en pruebas no corre solo.
    monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())
    d = armar_cliente("AAA", "ana@a.mx")
    d["acceso"] = acceso_de(d)
    entrar_como(d["acceso"])
    d["http"] = client
    return d


@pytest.fixture
def pushes(monkeypatch):
    enviados = []
    monkeypatch.setattr("lib.interfono.enviar_a_usuario",
                        lambda u, **kw: enviados.append((u.email, kw)) or {})
    return enviados


def test_aprobar_registra_nombre_correo_y_que_fue_por_el_portal(adentro, pushes, usuario_factory):
    from apps.cotizaciones.embudo import fase_efectiva

    from portal.models import EventoPortal

    usuario_factory(rol="contador", email="ventas@lc.mx")      # trae cotizaciones.ver
    usuario_factory(rol="disenador", email="diseno@lc.mx")     # no lo trae

    cot = adentro["cotizacion"]
    r = adentro["http"].post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "Ana Pérez", "acepto": "1"})
    assert r.status_code == 302
    cot.refresh_from_db()
    assert fase_efectiva(cot) == "ganada"
    assert cot.aprobada_por_nombre == "Ana Pérez"
    assert cot.aprobada_por_email == "ana@a.mx"
    assert cot.referencia_aprobacion.startswith("Portal de clientes")
    assert "IP" in cot.referencia_aprobacion
    assert EventoPortal.objects.filter(tipo="aprobacion", acceso=adentro["acceso"]).exists()
    # El equipo se entera por El Interfón.
    destinos = {e for e, _ in pushes}
    assert "ventas@lc.mx" in destinos and "diseno@lc.mx" not in destinos
    assert all(kw["categoria"] == "portal" for _, kw in pushes)
    assert "aprobó" in pushes[0][1]["cuerpo"] and "EMPRESA-AAA" in pushes[0][1]["cuerpo"]


def test_aprobar_sin_nombre_o_sin_confirmar_no_hace_nada(adentro):
    cot = adentro["cotizacion"]
    adentro["http"].post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "", "acepto": "1"})
    adentro["http"].post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "Ana"})
    cot.refresh_from_db()
    assert cot.estado == "enviada" and not cot.aprobada_por_nombre


def test_rechazar_pide_motivo_y_lo_guarda_con_el_nombre(adentro, pushes):
    from apps.cotizaciones.embudo import fase_efectiva

    cot = adentro["cotizacion"]
    adentro["http"].post(f"/cotizaciones/{cot.pk}/rechazar/", {"nombre": "Ana", "motivo": ""})
    cot.refresh_from_db()
    assert cot.estado == "enviada"
    adentro["http"].post(f"/cotizaciones/{cot.pk}/rechazar/",
                         {"nombre": "Ana Pérez", "motivo": "Nos quedó alto el precio"})
    cot.refresh_from_db()
    assert cot.rechazada_en is not None
    assert "Nos quedó alto el precio" in cot.motivo_rechazo
    assert "Ana Pérez" in cot.motivo_rechazo and "portal" in cot.motivo_rechazo
    # Y ya no sale como pendiente ni se puede aprobar después, aunque el catálogo
    # de estados no tenga uno de fase «perdida» (el de las pruebas no lo tiene).
    html = adentro["http"].get(f"/cotizaciones/{cot.pk}/").content.decode()
    assert "No se aprobó" in html and "Aprobar cotización" not in html
    adentro["http"].post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "Ana", "acepto": "1"})
    cot.refresh_from_db()
    assert fase_efectiva(cot) != "ganada" and not cot.aprobada_por_nombre


def test_no_se_aprueba_dos_veces_ni_se_rechaza_ya_aprobada(adentro):
    cot = adentro["cotizacion"]
    http = adentro["http"]
    http.post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "Ana", "acepto": "1"})
    cot.refresh_from_db()
    aprobada_en = cot.aprobada_en
    http.post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "Otro", "acepto": "1"})
    http.post(f"/cotizaciones/{cot.pk}/rechazar/", {"nombre": "Otro", "motivo": "x"})
    cot.refresh_from_db()
    assert cot.aprobada_por_nombre == "Ana" and cot.aprobada_en == aprobada_en
    assert not cot.motivo_rechazo


def test_una_cotizacion_vencida_no_se_aprueba_desde_el_portal(adentro):
    cot = adentro["cotizacion"]
    cot.fecha_validez = dt.date.today() - dt.timedelta(days=1)
    cot.save()
    r = adentro["http"].get(f"/cotizaciones/{cot.pk}/")
    assert b"Aprobar cotizaci" not in r.content and "venció".encode() in r.content
    adentro["http"].post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "Ana", "acepto": "1"})
    cot.refresh_from_db()
    assert cot.estado == "enviada"


def test_una_version_vieja_no_se_aprueba(adentro):
    from apps.cotizaciones.models import Cotizacion

    vieja = adentro["cotizacion"]
    Cotizacion.objects.create(cliente=vieja.cliente, proyecto=vieja.proyecto, titulo="Nueva",
                              estado="enviada", version=vieja.version + 1,
                              enviada_en=vieja.enviada_en)
    adentro["http"].post(f"/cotizaciones/{vieja.pk}/aprobar/", {"nombre": "Ana", "acepto": "1"})
    vieja.refresh_from_db()
    assert vieja.estado == "enviada"


def test_sin_pdf_no_hay_boton_de_descarga(adentro):
    cot = adentro["cotizacion"]
    cot.pdf_file_id = ""
    cot.save()
    r = adentro["http"].get(f"/cotizaciones/{cot.pk}/")
    assert b"Descargar la cotizaci" not in r.content
    assert adentro["http"].get(f"/cotizaciones/{cot.pk}/pdf/").status_code == 404


# ── Pagar: `apps.caja.services.url_pago`, importado de forma defensiva ─────


@pytest.fixture
def caja(monkeypatch):
    """Un `apps.caja.services` de mentiras con el contrato del sprint."""
    respuesta = {"url": "https://taller.learningcenter.mx/pagar/tok123/", "llamadas": []}

    def url_pago(objeto):
        respuesta["llamadas"].append(objeto)
        if isinstance(respuesta["url"], Exception):
            raise respuesta["url"]
        return respuesta["url"]

    paquete = types.ModuleType("apps.caja")
    paquete.__path__ = []
    servicios = types.ModuleType("apps.caja.services")
    servicios.url_pago = url_pago
    monkeypatch.setitem(sys.modules, "apps.caja", paquete)
    monkeypatch.setitem(sys.modules, "apps.caja.services", servicios)
    return respuesta


def test_sin_la_caja_no_hay_boton_pagar(adentro, monkeypatch):
    # Así se ve «La Caja no está en esta imagen»: su import truena. (Con `None`
    # en sys.modules el import lanza ImportError, esté o no la app en el repo.)
    monkeypatch.setitem(sys.modules, "apps.caja.services", None)
    r = adentro["http"].get(f"/facturas/{adentro['factura'].pk}/")
    assert r.status_code == 200
    assert b"/pagar/" not in r.content and b"Pagar en l" not in r.content


def test_con_la_caja_la_factura_con_saldo_trae_su_boton(adentro, caja):
    fac = adentro["factura"]
    r = adentro["http"].get(f"/facturas/{fac.pk}/")
    assert b"https://taller.learningcenter.mx/pagar/tok123/" in r.content
    assert caja["llamadas"] == [fac]


def test_si_la_caja_dice_none_o_truena_no_hay_boton(adentro, caja):
    fac = adentro["factura"]
    caja["url"] = None
    assert b"/pagar/" not in adentro["http"].get(f"/facturas/{fac.pk}/").content
    caja["url"] = RuntimeError("sin llaves")
    r = adentro["http"].get(f"/facturas/{fac.pk}/")
    assert r.status_code == 200 and b"/pagar/" not in r.content
    caja["url"] = "javascript:alert(1)"
    assert b"javascript:" not in adentro["http"].get(f"/facturas/{fac.pk}/").content


def test_factura_pagada_no_pregunta_a_la_caja(adentro, caja):
    fac = adentro["factura"]
    fac.monto_cobrado = Decimal("100000.00")
    fac.save()
    r = adentro["http"].get(f"/facturas/{fac.pk}/")
    assert b"/pagar/" not in r.content and caja["llamadas"] == []


def test_anticipo_de_cotizacion_aprobada_trae_su_boton(adentro, caja):
    cot = adentro["cotizacion"]
    cot.anticipo_porcentaje = Decimal("50")
    cot.save()
    adentro["http"].post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "Ana", "acepto": "1"})
    r = adentro["http"].get(f"/cotizaciones/{cot.pk}/")
    assert b"Pagar el anticipo" in r.content
    assert caja["llamadas"][-1].pk == cot.pk


def test_historial_de_pagos_de_la_factura(adentro, usuario_factory):
    from apps.tesoreria.models import Ingreso

    fac = adentro["factura"]
    Ingreso.objects.create(monto=Decimal("300.00"), descripcion="REF-BANCO-SECRETA", fecha=dt.date.today(),
                           metodo="transferencia", cliente=fac.cliente, factura=fac,
                           creado_por=usuario_factory(rol="super_admin"))
    Ingreso.objects.create(monto=Decimal("999.00"), descripcion="anulado", fecha=dt.date.today(),
                           metodo="transferencia", cliente=fac.cliente, factura=fac, anulado=True,
                           creado_por=usuario_factory(rol="super_admin"))
    html = adentro["http"].get(f"/facturas/{fac.pk}/").content.decode()
    assert "$300.00" in html
    assert "$999.00" not in html
    assert "REF-BANCO-SECRETA" not in html
