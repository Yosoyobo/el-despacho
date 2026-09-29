"""El botón «Pagar» del portal con La Caja DE VERDAD (no un doble).

Con llaves simuladas en Los Ajustes, el portal enseña la URL pública de El
Taller (`/pagar/<token firmado>/`); sin llaves, no hay botón. Y la URL se arma
igual desde La Recepción —cuyo urlconf no tiene las rutas de La Caja— que desde
El Taller: ése fue el hueco que dejaba al portal siempre sin botón.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def llaves(db):
    from ajustes.models.credencial import Credencial

    def _poner():
        Credencial.guardar("stripe_secret_key", "sk_test_123")
        Credencial.guardar("stripe_webhook_secret", "whsec_prueba")
    return _poner


@pytest.fixture
def adentro(armar_cliente, acceso_de, entrar_como, client, monkeypatch, settings):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())
    settings.TALLER_URL = "https://taller.ejemplo.mx/"
    d = armar_cliente("AAA", "ana@a.mx")
    d["acceso"] = acceso_de(d)
    entrar_como(d["acceso"])
    d["http"] = client
    return d


_BOTON = re.compile(r'href="(https://taller\.ejemplo\.mx/pagar/[^"/]+/)"')


def test_sin_llaves_no_hay_boton(adentro):
    from apps.caja.models import LinkPago

    html = adentro["http"].get(f"/facturas/{adentro['factura'].pk}/").content.decode()
    assert not _BOTON.search(html) and "Pagar en l" not in html
    assert LinkPago.objects.count() == 0


def test_con_llaves_la_factura_trae_la_url_publica_de_el_taller(adentro, llaves):
    from apps.caja.models import LinkPago

    llaves()
    fac = adentro["factura"]
    html = adentro["http"].get(f"/facturas/{fac.pk}/").content.decode()
    m = _BOTON.search(html)
    assert m, "con La Caja encendida el portal debe enseñar «Pagar»"
    link = LinkPago.objects.get()
    assert link.factura_id == fac.pk and link.estado == "vigente"
    assert m.group(1) == link.url_publica()
    # Volver a abrir la factura reusa el mismo link: no se apilan.
    adentro["http"].get(f"/facturas/{fac.pk}/")
    assert LinkPago.objects.count() == 1


def test_la_url_del_portal_es_la_misma_que_arma_el_taller(adentro, llaves, settings):
    """Mismo link, dos urlconf: el de La Recepción y el de El Taller."""
    from apps.caja.models import LinkPago
    from django.urls import reverse

    llaves()
    adentro["http"].get(f"/facturas/{adentro['factura'].pk}/")
    link = LinkPago.objects.get()
    en_recepcion = link.ruta_publica()
    settings.ROOT_URLCONF = "tests.urls_taller"
    assert en_recepcion == reverse("caja:pagar", args=[link.token_firmado])


def test_factura_pagada_no_trae_boton_aunque_haya_llaves(adentro, llaves):
    llaves()
    fac = adentro["factura"]
    fac.monto_cobrado = Decimal("100000.00")
    fac.save()
    assert not _BOTON.search(adentro["http"].get(f"/facturas/{fac.pk}/").content.decode())


def test_el_anticipo_de_una_aprobada_trae_su_boton(adentro, llaves):
    from apps.caja.models import LinkPago

    llaves()
    cot = adentro["cotizacion"]
    cot.anticipo_porcentaje = Decimal("50")
    cot.save()
    adentro["http"].post(f"/cotizaciones/{cot.pk}/aprobar/", {"nombre": "Ana", "acepto": "1"})
    html = adentro["http"].get(f"/cotizaciones/{cot.pk}/").content.decode()
    assert _BOTON.search(html) and "Pagar el anticipo" in html
    assert LinkPago.objects.get(cotizacion=cot).tipo == "anticipo"


def test_la_recepcion_instala_la_caja_cuando_existe():
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    assert (raiz / "el-taller/apps/caja/apps.py").exists()
    assert 'find_spec("apps.caja.apps")' in (raiz / "la-recepcion/la_recepcion/settings.py").read_text()
    gerencia = (raiz / "la-gerencia/la_gerencia/settings.py").read_text()
    assert '"apps.caja.apps.CajaConfig"' in gerencia, "La Gerencia es la que migra (Bug B)"
    assert "COPY el-taller/apps/caja/ /app/apps/caja/" in (raiz / "la-gerencia/Dockerfile").read_text()
