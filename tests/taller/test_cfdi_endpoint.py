"""La puerta por la que n8n empuja los CFDI (S-NUC-Servicios, 2026-08-24).

Del otro lado hay un robot, así que la puerta no tiene sesión, ni formulario,
ni CSRF. **La credencial es lo único que la sostiene**, y por eso es lo primero
que se prueba.

El criterio, copiado de El Celador: **se cierra, no se abre**. Sin token
configurado no pasa nadie. Un extremo que al faltarle la credencial deja entrar
a todos es peor que uno sin credencial, porque parece protegido.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

TOKEN = "un-token-largo-y-dificil-de-adivinar-2026"

CFDI = b"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Version="4.0" Serie="A" Folio="1" Fecha="2026-08-20T10:15:00"
  SubTotal="100.00" Total="116.00" Moneda="MXN">
  <cfdi:Emisor Rfc="LCE240101XYZ" Nombre="LEARNING CENTER"/>
  <cfdi:Receptor Rfc="OPT150505AB1" Nombre="OPTIMIST"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="11111111-2222-3333-4444-555555555555"/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""


@pytest.fixture
def con_token(monkeypatch):
    from apps.facturacion import views_ingesta

    monkeypatch.setattr(views_ingesta, "_tokens", lambda: [TOKEN])


@pytest.fixture(autouse=True)
def _sin_drive(monkeypatch):
    from apps.facturacion import ingesta_cfdi

    monkeypatch.setattr(ingesta_cfdi, "_guardar_archivo", lambda *a, **k: None)


# ── La credencial, que es lo único que sostiene esta puerta ────────────────


def test_sin_token_configurado_no_pasa_nadie(client, monkeypatch):
    """Se cierra, no se abre. Es el caso que importa: si al faltar la
    credencial se abriera, la puerta estaría de adorno."""
    from apps.facturacion import views_ingesta

    monkeypatch.setattr(views_ingesta, "_tokens", list)
    r = client.post(reverse("facturacion:cfdi-entrante"), data=CFDI,
                    content_type="application/xml",
                    headers={"x-cfdi-token": "lo-que-sea"})
    assert r.status_code == 404


def test_con_token_equivocado_no_pasa(client, con_token):
    r = client.post(reverse("facturacion:cfdi-entrante"), data=CFDI,
                    content_type="application/xml",
                    headers={"x-cfdi-token": "otro-token"})
    assert r.status_code == 404


def test_sin_cabecera_no_pasa(client, con_token):
    r = client.post(reverse("facturacion:cfdi-entrante"), data=CFDI,
                    content_type="application/xml")
    assert r.status_code == 404


def test_a_quien_no_trae_credencial_no_se_le_confirma_que_existe(client, con_token):
    """404 y no 403: un 403 le diría a quien sondea que aquí hay algo."""
    r = client.post(reverse("facturacion:cfdi-entrante"), data=CFDI,
                    content_type="application/xml")
    assert r.status_code == 404
    assert b"cfdi" not in r.content.lower(), "la respuesta delata de qué es la puerta"


def test_con_el_token_bueno_entra(client, con_token):
    r = client.post(reverse("facturacion:cfdi-entrante"), data=CFDI,
                    content_type="application/xml",
                    headers={"x-cfdi-token": TOKEN})
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── Que al robot se le conteste, no se le tire una traza ───────────────────


def test_basura_devuelve_json_y_no_una_pagina_de_error(client, con_token):
    r = client.post(reverse("facturacion:cfdi-entrante"), data=b"no soy xml",
                    content_type="application/xml",
                    headers={"x-cfdi-token": TOKEN})
    assert r.status_code == 422
    assert r["Content-Type"].startswith("application/json")
    assert r.json()["ok"] is False


def test_un_cuerpo_vacio_se_avisa(client, con_token):
    r = client.post(reverse("facturacion:cfdi-entrante"), data=b"",
                    content_type="application/xml",
                    headers={"x-cfdi-token": TOKEN})
    assert r.status_code == 400
    assert "archivo" in r.json()["error"]


def test_un_archivo_gigante_se_rechaza_por_tamano(client, con_token):
    """Rechazar por tamaño cuesta nada y evita hasta leer lo que venga."""
    from apps.facturacion import views_ingesta

    grande = b"x" * (views_ingesta.MAX_CUERPO + 10)
    r = client.post(reverse("facturacion:cfdi-entrante"), data=grande,
                    content_type="application/xml",
                    headers={"x-cfdi-token": TOKEN})
    assert r.status_code == 413


def test_solo_acepta_post(client, con_token):
    r = client.get(reverse("facturacion:cfdi-entrante"),
                   headers={"x-cfdi-token": TOKEN})
    assert r.status_code == 405


def test_tambien_acepta_el_xml_como_archivo_subido(client, con_token):
    """n8n puede mandarlo de las dos formas."""
    import io

    archivo = io.BytesIO(CFDI)
    archivo.name = "factura.xml"
    r = client.post(reverse("facturacion:cfdi-entrante"), data={"archivo": archivo},
                    headers={"x-cfdi-token": TOKEN})
    assert r.status_code == 200
    assert r.json()["ok"] is True
