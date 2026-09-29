"""La Caja — links de pago con Stripe y MercadoPago (2026-09-29).

Todo con las pasarelas SIMULADAS: `lib.pasarelas._pedir` es lo único que toca
la red, y aquí se sustituye. Las firmas de los webhooks se calculan de verdad
(HMAC-SHA256 con el secreto de prueba), igual que las calcularía la pasarela.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import time
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

WHSEC = "whsec_de_prueba"
MPSEC = "secreto_mp_de_prueba"


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture(autouse=True)
def _sin_limite(monkeypatch):
    """El límite por IP vive en Redis; aquí no se prueba (tiene su propio test)."""
    from lib import ratelimit
    monkeypatch.setattr(ratelimit, "intentar", lambda *a, **k: 1)


class RedFalsa:
    """Las pasarelas de mentiras. Guarda cada llamada para poder contarlas."""

    def __init__(self):
        self.llamadas: list[tuple[str, str, dict]] = []
        self.pagos_mp: dict[str, dict] = {}
        self.sesiones = 0

    def __call__(self, metodo, url, **kw):
        self.llamadas.append((metodo, url, kw))
        if url.endswith("/checkout/sessions") and metodo == "POST":
            self.sesiones += 1
            n = self.sesiones
            return 200, {"id": f"cs_test_{n}", "url": f"https://checkout.stripe.com/c/pay/cs_test_{n}",
                         "expires_at": int(time.time()) + 86400}
        if url.endswith("/expire"):
            return 200, {}
        if url.endswith("/checkout/preferences") and metodo == "POST":
            return 201, {"id": "pref_1", "init_point": "https://www.mercadopago.com.mx/checkout/v1/redirect?pref_id=1",
                         "sandbox_init_point": "https://sandbox.mercadopago.com.mx/checkout/v1/redirect?pref_id=1"}
        if "/checkout/preferences/" in url:
            return 200, {}
        if "/v1/payments/" in url:
            pid = url.rsplit("/", 1)[-1]
            if pid in self.pagos_mp:
                return 200, self.pagos_mp[pid]
            return 404, {"message": "not found"}
        if url.endswith("/balance") or url.endswith("/users/me"):
            return 200, {}
        return 500, {"message": f"inesperado {metodo} {url}"}

    def a(self, trozo: str) -> list:
        return [c for c in self.llamadas if trozo in c[1]]


@pytest.fixture
def red(monkeypatch):
    from lib import pasarelas
    falsa = RedFalsa()
    monkeypatch.setattr(pasarelas, "_pedir", falsa)
    return falsa


@pytest.fixture
def llaves(db):
    from ajustes.models.credencial import Credencial

    def _poner(*, stripe=True, mp=True, prueba=True):
        if stripe:
            Credencial.guardar("stripe_secret_key", "sk_test_123" if prueba else "sk_live_123")
            Credencial.guardar("stripe_webhook_secret", WHSEC)
        if mp:
            Credencial.guardar("mercadopago_access_token", "TEST-123" if prueba else "APP_USR-123")
            Credencial.guardar("mercadopago_webhook_secret", MPSEC)
    return _poner


@pytest.fixture
def eventos(monkeypatch):
    """Lo que La Caja le manda al Portavoz."""
    from apps.caja import services
    vistos: list = []
    monkeypatch.setattr(services, "emitir", lambda ev: vistos.append(ev))
    return vistos


def _factura(cliente, autor, *, monto="1000.00", estado="emitida"):
    from apps.facturacion.models import Factura, FacturaItem
    fac = Factura.objects.create(
        cliente=cliente, titulo="Tazas", concepto="Tazas", estado=estado, regimen_fiscal="exento",
        fecha_emision=date.today(), fecha_vencimiento=date.today() + timedelta(days=30), creado_por=autor,
    )
    FacturaItem.objects.create(factura=fac, orden=0, descripcion="Tazas", cantidad=Decimal("1"),
                               precio_unitario=Decimal(monto))
    return fac


def _cotizacion(cliente, autor, *, anticipo="500.00"):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    cot = Cotizacion.objects.create(
        cliente=cliente, titulo="Gorras", estado="aprobada", moneda="MXN", regimen_fiscal="iva",
        anticipo_porcentaje=Decimal("50"), anticipo_monto_override=Decimal(anticipo), creado_por=autor,
        aprobada_en=timezone.now(),
    )
    CotizacionItem.objects.create(cotizacion=cot, orden=0, descripcion="Gorra", cantidad=Decimal("1"),
                                  unidad="servicio", precio_unitario=Decimal("1000"),
                                  descuento_porcentaje=Decimal("0"))
    return cot


@pytest.fixture
def jefe(usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.fixture
def cliente(cliente_factory, jefe):
    return cliente_factory(creado_por=jefe, email_contacto="pagos@cliente.mx")


def _firma_stripe(cuerpo: bytes, *, secreto=WHSEC, t=None) -> str:
    t = int(time.time()) if t is None else t
    sig = hmac.new(secreto.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return f"t={t},v1={sig}"


def _evento_stripe(link, *, monto=None, pi="pi_1", tipo="checkout.session.completed",
                   estado="paid", livemode=False, moneda="mxn") -> bytes:
    from lib.pasarelas import centavos
    return json.dumps({
        "id": f"evt_{pi}", "type": tipo, "livemode": livemode, "created": int(time.time()),
        "data": {"object": {
            "id": f"cs_{pi}", "payment_intent": pi, "payment_status": estado,
            "amount_total": centavos(link.monto if monto is None else monto), "currency": moneda,
            "client_reference_id": link.token, "metadata": {"link_id": str(link.pk)},
        }},
    }).encode()


def _post_stripe(client, cuerpo: bytes, firma: str | None = None):
    return client.post(reverse("caja:webhook-stripe"), data=cuerpo, content_type="application/json",
                       HTTP_STRIPE_SIGNATURE=firma if firma is not None else _firma_stripe(cuerpo))


def _post_mp(client, pago_id: str, *, secreto=MPSEC, rid="req-1", ts="1700000000"):
    manifiesto = f"id:{pago_id.lower()};request-id:{rid};ts:{ts};"
    v1 = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return client.post(f"{reverse('caja:webhook-mercadopago')}?data.id={pago_id}&type=payment",
                       data=json.dumps({"type": "payment", "data": {"id": pago_id}}),
                       content_type="application/json",
                       HTTP_X_SIGNATURE=f"ts={ts},v1={v1}", HTTP_X_REQUEST_ID=rid)


# ── lib.pasarelas: estado y firmas ───────────────────────────────────────────


class TestPasarelas:
    def test_sin_llaves_esta_apagada(self):
        from lib import pasarelas
        e = pasarelas.estado()
        assert e["encendida"] is False and e["pasarelas"] == []

    def test_llave_sin_secreto_del_webhook_no_enciende(self):
        from ajustes.models.credencial import Credencial
        from lib import pasarelas
        Credencial.guardar("stripe_secret_key", "sk_live_x")
        e = pasarelas.estado()
        assert e["encendida"] is False
        assert e["stripe"]["faltan"] == ["stripe_webhook_secret"]
        assert "APAGADA" in pasarelas.resumen_para_ajustes()["texto"]

    def test_modo_prueba_por_prefijo(self, llaves):
        from lib import pasarelas
        llaves(prueba=True)
        e = pasarelas.estado()
        assert e["encendida"] and e["prueba"] and e["stripe"]["prueba"] and e["mercadopago"]["prueba"]
        assert pasarelas.resumen_para_ajustes()["tono"] == "ambar"

    def test_llaves_reales_no_son_prueba(self, llaves):
        from lib import pasarelas
        llaves(prueba=False)
        assert pasarelas.estado()["prueba"] is False
        assert pasarelas.resumen_para_ajustes()["tono"] == "verde"

    def test_firma_stripe(self):
        from lib.pasarelas import stripe_firma_valida
        cuerpo = b'{"a":1}'
        assert stripe_firma_valida(cuerpo, _firma_stripe(cuerpo), WHSEC)
        assert not stripe_firma_valida(cuerpo, _firma_stripe(cuerpo, secreto="otro"), WHSEC)
        assert not stripe_firma_valida(b'{"a":2}', _firma_stripe(cuerpo), WHSEC)
        assert not stripe_firma_valida(cuerpo, _firma_stripe(cuerpo, t=int(time.time()) - 3600), WHSEC)
        assert not stripe_firma_valida(cuerpo, "", WHSEC)
        assert not stripe_firma_valida(cuerpo, _firma_stripe(cuerpo), "")

    def test_firma_mercadopago(self):
        from lib.pasarelas import mp_firma_valida
        manifiesto = "id:abc123;request-id:r1;ts:17;"
        v1 = hmac.new(MPSEC.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
        ok = dict(cabecera=f"ts=17,v1={v1}", request_id="r1", secreto=MPSEC)
        assert mp_firma_valida(data_id="abc123", **ok)
        # MercadoPago firma el id alfanumérico en minúsculas.
        assert mp_firma_valida(data_id="ABC123", **ok)
        assert not mp_firma_valida(data_id="abc124", **ok)
        assert not mp_firma_valida(data_id="abc123", cabecera=f"ts=18,v1={v1}", request_id="r1", secreto=MPSEC)
        assert not mp_firma_valida(data_id="abc123", cabecera=f"ts=17,v1={v1}", request_id="r1", secreto="otro")

    def test_el_site_dice_no_configurada_sin_llaves(self):
        from lib.site import registry
        assert registry.chequear("stripe")["estado"] == "no_configurada"
        assert registry.chequear("mercadopago")["estado"] == "no_configurada"

    def test_el_site_dice_ok_con_llaves(self, llaves, red):
        from lib.site import registry
        llaves()
        assert registry.chequear("stripe")["estado"] == "ok"
        assert registry.chequear("mercadopago")["estado"] == "ok"


# ── url_pago y los links ─────────────────────────────────────────────────────


class TestUrlPago:
    def test_apagada_devuelve_none_y_no_crea_nada(self, cliente, jefe):
        from apps.caja.models import LinkPago
        from apps.caja.services import url_pago
        fac = _factura(cliente, jefe)
        assert url_pago(fac) is None
        assert LinkPago.objects.count() == 0

    def test_factura_emitida_da_url_absoluta_y_se_reusa(self, llaves, cliente, jefe):
        from apps.caja.models import LinkPago
        from apps.caja.services import url_pago
        llaves()
        fac = _factura(cliente, jefe, monto="1160.00")
        url = url_pago(fac)
        assert url.startswith("https://taller.learningcenter.mx/pagar/")
        assert url_pago(fac) == url
        link = LinkPago.objects.get()
        assert link.tipo == "factura" and link.monto == Decimal("1160.00") and link.factura == fac

    @pytest.mark.parametrize("estado", ["borrador", "cobrada_total", "cancelada"])
    def test_sin_nada_que_cobrar_devuelve_none(self, llaves, cliente, jefe, estado):
        from apps.caja.services import url_pago
        llaves()
        assert url_pago(_factura(cliente, jefe, estado=estado)) is None

    def test_si_el_saldo_cambia_el_link_viejo_se_anula(self, llaves, cliente, jefe):
        from apps.caja.models import LinkPago
        from apps.caja.services import url_pago
        from apps.facturacion.services import registrar_cobro
        llaves()
        fac = _factura(cliente, jefe)
        vieja = url_pago(fac)
        registrar_cobro(fac, monto=Decimal("400"), fecha=date.today(), metodo="transferencia", actor=jefe)
        viejo = LinkPago.objects.get(tipo="factura", monto=Decimal("1000.00"))
        # La señal lo anuló al registrar el cobro a mano.
        assert viejo.estado == "anulado"
        nueva = url_pago(fac)
        assert nueva != vieja
        assert LinkPago.objects.get(estado="vigente").monto == Decimal("600.00")

    def test_cotizacion_con_anticipo(self, llaves, cliente, jefe):
        from apps.caja.models import LinkPago
        from apps.caja.services import url_pago
        llaves()
        cot = _cotizacion(cliente, jefe)
        assert url_pago(cot)
        link = LinkPago.objects.get()
        assert link.tipo == "anticipo" and link.monto == Decimal("500.00") and link.cotizacion == cot

    def test_nunca_lanza(self, llaves, monkeypatch, cliente, jefe):
        from apps.caja import services
        llaves()
        monkeypatch.setattr(services, "que_cobrar", lambda o: 1 / 0)
        assert services.url_pago(_factura(cliente, jefe)) is None

    def test_link_libre_valida(self, llaves, cliente, jefe):
        from apps.caja.services import crear_link_libre
        llaves()
        with pytest.raises(ValueError):
            crear_link_libre(monto="0", concepto="Muestras", actor=jefe, cliente=cliente)
        with pytest.raises(ValueError):
            crear_link_libre(monto="100", concepto="", actor=jefe, cliente=cliente)
        with pytest.raises(ValueError):
            crear_link_libre(monto="100", concepto="Muestras", actor=jefe)
        link = crear_link_libre(monto="350.50", concepto="<script>x</script>Muestras", actor=jefe, cliente=cliente)
        assert link.monto == Decimal("350.50") and "<script" not in link.concepto

    def test_link_libre_apagada(self, cliente, jefe):
        from apps.caja.services import crear_link_libre
        with pytest.raises(ValueError, match="apagada"):
            crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)


# ── Página pública ───────────────────────────────────────────────────────────


class TestPaginaPublica:
    def _link(self, llaves, cliente, jefe, **kw):
        from apps.caja.services import link_para
        llaves(**kw)
        return link_para(_factura(cliente, jefe))

    def test_sin_sesion_se_ve_con_footer_y_noindex(self, client, llaves, cliente, jefe):
        link = self._link(llaves, cliente, jefe)
        r = client.get(link.ruta_publica())
        assert r.status_code == 200
        html = r.content.decode()
        assert "Pagar con tarjeta" in html and "Pagar con MercadoPago" in html
        assert 'href="https://devs.noko.mx"' in html and "NoKo Devs" in html
        assert 'name="robots" content="noindex' in html
        assert r["X-Robots-Tag"].startswith("noindex")
        assert r["Referrer-Policy"] == "no-referrer"
        assert "Modo prueba" in html
        assert "despacho-tema" in html  # anti-FOUC del tema propio

    def test_solo_las_pasarelas_configuradas(self, client, llaves, cliente, jefe):
        link = self._link(llaves, cliente, jefe, mp=False, prueba=False)
        html = client.get(link.ruta_publica()).content.decode()
        assert "Pagar con tarjeta" in html
        assert "Pagar con MercadoPago" not in html
        assert "Modo prueba" not in html

    def test_token_falso_es_404(self, client, llaves, cliente, jefe):
        link = self._link(llaves, cliente, jefe)
        assert client.get("/pagar/inventado/").status_code == 404
        # El token crudo, sin firma, tampoco entra.
        assert client.get(f"/pagar/{link.token}/").status_code == 404
        # Firma de otro token.
        firmado = link.token_firmado
        alterado = ("A" if firmado[0] != "A" else "B") + firmado[1:]
        assert client.get(f"/pagar/{alterado}/").status_code == 404

    def test_apagada_la_pagina_no_existe(self, client, llaves, cliente, jefe):
        from ajustes.models.credencial import Credencial
        link = self._link(llaves, cliente, jefe)
        for clave in ("stripe_secret_key", "mercadopago_access_token"):
            Credencial.guardar(clave, "")
        assert client.get(link.ruta_publica()).status_code == 404

    def test_boton_stripe_lleva_a_checkout_y_reusa_la_sesion(self, client, llaves, red, cliente, jefe):
        link = self._link(llaves, cliente, jefe)
        r = client.post(link.ruta_publica("stripe"))
        assert r.status_code == 303 and r["Location"].startswith("https://checkout.stripe.com/")
        client.post(link.ruta_publica("stripe"))
        assert red.sesiones == 1  # dos clics, un solo cobro abierto
        _, _, kw = red.a("/checkout/sessions")[0]
        assert kw["data"]["line_items[0][price_data][unit_amount]"] == "100000"
        assert kw["data"]["client_reference_id"] == link.token

    def test_boton_mercadopago_en_prueba_usa_sandbox(self, client, llaves, red, cliente, jefe):
        link = self._link(llaves, cliente, jefe)
        r = client.post(link.ruta_publica("mercadopago"))
        assert r.status_code == 303 and "sandbox.mercadopago.com.mx" in r["Location"]
        _, _, kw = red.a("/checkout/preferences")[0]
        assert kw["json"]["external_reference"] == link.token
        assert kw["json"]["items"][0]["unit_price"] == 1000.0

    def test_una_url_fuera_de_la_pasarela_no_se_sigue(self, client, llaves, red, monkeypatch, cliente, jefe):
        from lib import pasarelas
        link = self._link(llaves, cliente, jefe)
        monkeypatch.setattr(pasarelas, "_pedir", lambda *a, **k: (200, {"id": "cs_x", "url": "https://evil.example/stripe.com"}))
        r = client.post(link.ruta_publica("stripe"))
        assert r.status_code == 502 and "Location" not in r

    def test_pasarela_no_configurada_no_abre(self, client, llaves, red, cliente, jefe):
        link = self._link(llaves, cliente, jefe, mp=False)
        assert client.post(link.ruta_publica("mercadopago")).status_code == 400
        assert not red.a("/checkout/preferences")

    def test_link_anulado_no_cobra(self, client, llaves, red, cliente, jefe):
        from apps.caja.services import anular
        link = self._link(llaves, cliente, jefe)
        anular(link, actor=jefe, motivo="prueba")
        html = client.get(link.ruta_publica()).content.decode()
        assert "ya no es válido" in html and "Pagar con tarjeta" not in html
        assert client.post(link.ruta_publica("stripe")).status_code == 400

    def test_link_vencido(self, client, llaves, cliente, jefe):
        from apps.caja.models import LinkPago
        link = self._link(llaves, cliente, jefe)
        LinkPago.objects.filter(pk=link.pk).update(vence_en=timezone.now() - timedelta(minutes=1))
        html = client.get(link.ruta_publica()).content.decode()
        assert "venció" in html
        link.refresh_from_db()
        assert link.estado == "vencido"

    def test_gracias_y_cancelado(self, client, llaves, cliente, jefe):
        link = self._link(llaves, cliente, jefe)
        assert "Gracias" in client.get(link.ruta_publica("gracias")).content.decode()
        assert "ningún cargo" in client.get(link.ruta_publica("cancelado")).content.decode()

    def test_limite_por_ip(self, client, llaves, cliente, jefe, monkeypatch):
        from lib import ratelimit
        from lib.errors import RateLimitExcedido
        link = self._link(llaves, cliente, jefe)

        def _excedido(*a, **k):
            raise RateLimitExcedido("demasiados")
        monkeypatch.setattr(ratelimit, "intentar", _excedido)
        assert client.get(link.ruta_publica()).status_code == 429


# ── Webhooks ─────────────────────────────────────────────────────────────────


class TestWebhookStripe:
    def test_firma_invalida_no_toca_nada(self, client, llaves, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import link_para
        llaves()
        link = link_para(_factura(cliente, jefe))
        cuerpo = _evento_stripe(link)
        assert _post_stripe(client, cuerpo, _firma_stripe(cuerpo, secreto="otro")).status_code == 400
        assert _post_stripe(client, cuerpo, "").status_code == 400
        assert PagoRecibido.objects.count() == 0

    def test_sin_llaves_no_existe(self, client, cliente, jefe):
        assert client.post(reverse("caja:webhook-stripe"), data=b"{}",
                           content_type="application/json").status_code == 404

    def test_pago_de_factura_se_registra_solo(self, client, llaves, eventos, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import link_para
        from apps.tesoreria.models import Ingreso
        llaves()
        fac = _factura(cliente, jefe)
        link = link_para(fac)
        r = _post_stripe(client, _evento_stripe(link))
        assert r.status_code == 200
        fac.refresh_from_db()
        link.refresh_from_db()
        pago = PagoRecibido.objects.get()
        assert fac.estado == "cobrada_total"
        assert link.estado == "pagado" and link.pasarela == "stripe"
        assert pago.estado == "registrado" and pago.ingreso.metodo == "stripe"
        ing = Ingreso.objects.get()
        assert ing.factura == fac and ing.monto == Decimal("1000.00") and ing.referencia_externa == "pi_1"
        assert "pago.recibido" in [e.tipo for e in eventos]
        # Nada de datos de tarjeta en lo guardado.
        assert set(pago.payload) <= {"evento_id", "evento_tipo", "sesion_id", "payment_intent",
                                     "estado", "monto", "moneda", "referencia"}

    def test_el_mismo_evento_dos_veces_no_duplica(self, client, llaves, cliente, jefe):
        from apps.caja.services import link_para
        from apps.tesoreria.models import Ingreso
        llaves()
        link = link_para(_factura(cliente, jefe))
        cuerpo = _evento_stripe(link)
        assert _post_stripe(client, cuerpo).status_code == 200
        assert _post_stripe(client, cuerpo).status_code == 200
        assert Ingreso.objects.count() == 1

    def test_monto_que_no_cuadra_queda_por_revisar(self, client, llaves, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import link_para
        from apps.tesoreria.models import Ingreso
        llaves()
        fac = _factura(cliente, jefe)
        link = link_para(fac)
        _post_stripe(client, _evento_stripe(link, monto="999.00"))
        pago = PagoRecibido.objects.get()
        assert pago.estado == "por_revisar"  # el motivo dice las dos cifras
        assert "999" in pago.motivo and "1,000" in pago.motivo
        assert Ingreso.objects.count() == 0
        fac.refresh_from_db()
        assert fac.estado == "emitida"

    def test_factura_ya_cobrada_queda_por_revisar(self, client, llaves, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import link_para
        from apps.facturacion.models import Factura
        from apps.tesoreria.models import Ingreso
        llaves()
        fac = _factura(cliente, jefe)
        link = link_para(fac)
        # Se marcó cobrada por fuera (sin pasar por la señal): el link sigue vigente.
        Factura.objects.filter(pk=fac.pk).update(estado="cobrada_total")
        _post_stripe(client, _evento_stripe(link))
        pago = PagoRecibido.objects.get()
        assert pago.estado == "por_revisar" and "ya no admite cobros" in pago.motivo
        assert Ingreso.objects.count() == 0

    def test_cobro_a_mano_antes_del_pago_lo_manda_a_revisar(self, client, llaves, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import link_para
        from apps.facturacion.services import registrar_cobro
        from apps.tesoreria.models import Ingreso
        llaves()
        fac = _factura(cliente, jefe)
        link = link_para(fac)
        registrar_cobro(fac, monto=Decimal("1000"), fecha=date.today(), metodo="transferencia", actor=jefe)
        _post_stripe(client, _evento_stripe(link))
        assert PagoRecibido.objects.get().estado == "por_revisar"
        assert Ingreso.objects.count() == 1  # sólo el de a mano

    def test_link_anulado_o_vencido_queda_por_revisar(self, client, llaves, cliente, jefe):
        from apps.caja.models import LinkPago, PagoRecibido
        from apps.caja.services import anular, crear_link_libre
        llaves()
        a = crear_link_libre(monto="100", concepto="Uno", actor=jefe, cliente=cliente)
        b = crear_link_libre(monto="100", concepto="Dos", actor=jefe, cliente=cliente)
        anular(a, actor=jefe, motivo="me equivoqué")
        LinkPago.objects.filter(pk=b.pk).update(vence_en=timezone.now() - timedelta(days=1))
        _post_stripe(client, _evento_stripe(a, pi="pi_a"))
        _post_stripe(client, _evento_stripe(b, pi="pi_b"))
        motivos = dict(PagoRecibido.objects.values_list("id_externo", "motivo"))
        assert "anulado" in motivos["pi_a"] and "vencido" in motivos["pi_b"]
        assert set(PagoRecibido.objects.values_list("estado", flat=True)) == {"por_revisar"}

    def test_segundo_pago_del_mismo_link_queda_por_revisar(self, client, llaves, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import crear_link_libre
        from apps.tesoreria.models import Ingreso
        llaves()
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        _post_stripe(client, _evento_stripe(link, pi="pi_1"))
        _post_stripe(client, _evento_stripe(link, pi="pi_2"))
        assert Ingreso.objects.count() == 1
        assert "pago doble" in PagoRecibido.objects.get(id_externo="pi_2").motivo

    def test_evento_de_prueba_con_llave_real_se_ignora(self, client, llaves, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import crear_link_libre
        llaves(prueba=False)
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        assert _post_stripe(client, _evento_stripe(link, livemode=False)).status_code == 200
        assert PagoRecibido.objects.count() == 0
        _post_stripe(client, _evento_stripe(link, livemode=True))
        assert PagoRecibido.objects.get().estado == "registrado"

    def test_pago_asincrono_pendiente_y_luego_acreditado(self, client, llaves, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import crear_link_libre
        from apps.tesoreria.models import Ingreso
        llaves()
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        _post_stripe(client, _evento_stripe(link, estado="unpaid"))
        assert PagoRecibido.objects.get().estado == "pendiente" and Ingreso.objects.count() == 0
        _post_stripe(client, _evento_stripe(link, tipo="checkout.session.async_payment_succeeded"))
        assert PagoRecibido.objects.get().estado == "registrado" and Ingreso.objects.count() == 1

    def test_anticipo_genera_emite_y_cobra_la_factura_del_anticipo(self, client, llaves, cliente, jefe):
        from apps.caja.services import link_para
        from apps.facturacion.models import Factura
        llaves()
        cot = _cotizacion(cliente, jefe)
        link = link_para(cot)
        _post_stripe(client, _evento_stripe(link))
        cot.refresh_from_db()
        assert cot.anticipo_facturado_en is not None
        fac = Factura.objects.get(cotizacion_origen=cot)
        assert fac.estado == "cobrada_total" and fac.saldo_pendiente == Decimal("0.00")
        link.refresh_from_db()
        assert link.factura == fac and link.estado == "pagado"

    def test_libre_entra_como_ingreso_del_cliente_y_proyecto(self, client, llaves, cliente, jefe, proyecto_factory):
        from apps.caja.services import crear_link_libre
        from apps.tesoreria.models import Ingreso
        llaves()
        proy = proyecto_factory(cliente=cliente)
        link = crear_link_libre(monto="250", concepto="Muestras", actor=jefe, proyecto=proy)
        _post_stripe(client, _evento_stripe(link))
        ing = Ingreso.objects.get()
        assert ing.factura is None and ing.cliente == cliente and ing.proyecto == proy
        assert ing.metodo == "stripe" and ing.monto == Decimal("250.00")

    def test_avisa_por_el_interfon_a_quien_ve_la_caja(self, client, llaves, cliente, jefe, usuario_factory):
        from apps.caja.services import crear_link_libre

        from interfono.models import InterfonoEntrega
        llaves()
        disenador = usuario_factory(rol="disenador")
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        _post_stripe(client, _evento_stripe(link))
        destinatarios = set(InterfonoEntrega.objects.filter(categoria="caja").values_list("usuario_id", flat=True))
        assert jefe.pk in destinatarios and disenador.pk not in destinatarios


class TestWebhookMercadoPago:
    def _pago(self, red, link, pid="123", *, status="approved", monto=None, moneda="MXN", live=False):
        red.pagos_mp[pid] = {"id": int(pid), "status": status, "status_detail": "accredited",
                             "transaction_amount": float(link.monto if monto is None else monto),
                             "currency_id": moneda, "external_reference": link.token,
                             "payment_method_id": "visa", "payment_type_id": "credit_card",
                             "live_mode": live, "date_approved": "2026-09-29T10:00:00.000-06:00"}

    def test_firma_invalida(self, client, llaves, red, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import crear_link_libre
        llaves()
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        self._pago(red, link)
        assert _post_mp(client, "123", secreto="otro").status_code == 401
        assert not red.a("/v1/payments/")  # ni siquiera se consultó
        assert PagoRecibido.objects.count() == 0

    def test_aprobado_se_consulta_y_se_registra(self, client, llaves, red, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import link_para
        from apps.tesoreria.models import Ingreso
        llaves()
        fac = _factura(cliente, jefe)
        link = link_para(fac)
        self._pago(red, link)
        assert _post_mp(client, "123").status_code == 200
        assert red.a("/v1/payments/123")
        pago = PagoRecibido.objects.get()
        assert pago.estado == "registrado" and pago.pasarela == "mercadopago"
        assert Ingreso.objects.get().metodo == "mercadopago"
        fac.refresh_from_db()
        assert fac.estado == "cobrada_total"
        # Y dos veces el mismo aviso no crea otro ingreso.
        _post_mp(client, "123", rid="req-2")
        assert Ingreso.objects.count() == 1

    def test_el_monto_se_le_cree_a_la_api(self, client, llaves, red, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import crear_link_libre
        llaves()
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        self._pago(red, link, monto="10")
        _post_mp(client, "123")
        assert PagoRecibido.objects.get().estado == "por_revisar"

    def test_oxxo_pendiente_y_luego_aprobado(self, client, llaves, red, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import crear_link_libre
        from apps.tesoreria.models import Ingreso
        llaves()
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        self._pago(red, link, status="pending")
        _post_mp(client, "123")
        assert PagoRecibido.objects.get().estado == "pendiente" and Ingreso.objects.count() == 0
        self._pago(red, link, status="approved")
        _post_mp(client, "123", rid="req-2")
        assert PagoRecibido.objects.get().estado == "registrado" and Ingreso.objects.count() == 1

    def test_pago_que_la_api_no_confirma_es_502(self, client, llaves, red, cliente, jefe):
        llaves()
        assert _post_mp(client, "999").status_code == 502

    def test_moneda_distinta_queda_por_revisar(self, client, llaves, red, cliente, jefe):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import crear_link_libre
        llaves()
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        self._pago(red, link, moneda="USD")
        _post_mp(client, "123")
        assert "pesos" in PagoRecibido.objects.get().motivo


# ── Revisar a mano ───────────────────────────────────────────────────────────


class TestRevisar:
    def _por_revisar(self, client, llaves, cliente, jefe, monto="400"):
        from apps.caja.models import PagoRecibido
        from apps.caja.services import link_para
        llaves()
        fac = _factura(cliente, jefe)
        link = link_para(fac)
        _post_stripe(client, _evento_stripe(link, monto=monto))
        return fac, PagoRecibido.objects.get()

    def test_registrar_lo_aplica_a_la_factura(self, client, llaves, cliente, jefe):
        from apps.caja.services import revisar_pago
        fac, pago = self._por_revisar(client, llaves, cliente, jefe)
        revisar_pago(pago, accion="registrar", actor=jefe, nota="pagó de menos")
        fac.refresh_from_db()
        assert fac.estado == "cobrada_parcial" and fac.monto_cobrado == Decimal("400.00")
        assert pago.estado == "registrado" and pago.revisado_por == jefe

    def test_descartar_pide_nota(self, client, llaves, cliente, jefe):
        from apps.caja.services import revisar_pago
        _, pago = self._por_revisar(client, llaves, cliente, jefe)
        with pytest.raises(ValueError):
            revisar_pago(pago, accion="descartar", actor=jefe)
        revisar_pago(pago, accion="descartar", actor=jefe, nota="se devolvió")
        assert pago.estado == "descartado" and pago.ingreso is None
        with pytest.raises(ValueError):
            revisar_pago(pago, accion="registrar", actor=jefe)

    def test_la_vista_pide_permiso(self, client, llaves, cliente, jefe, usuario_factory):
        _, pago = self._por_revisar(client, llaves, cliente, jefe)
        client.force_login(usuario_factory(rol="disenador"))
        r = client.post(reverse("caja:pago-revisar", args=[pago.pk]), {"accion": "registrar"})
        assert r.status_code == 403
        pago.refresh_from_db()
        assert pago.estado == "por_revisar"


# ── Pantallas del equipo y permisos ──────────────────────────────────────────


class TestPantallas:
    def test_la_caja_apagada_lo_dice(self, client, jefe):
        client.force_login(jefe)
        r = client.get(reverse("caja:landing"))
        assert r.status_code == 200 and "La Caja está apagada" in r.content.decode()

    def test_sin_permiso_no_entra(self, client, usuario_factory, llaves, cliente, jefe):
        llaves()
        fac = _factura(cliente, jefe)
        client.force_login(usuario_factory(rol="disenador"))
        assert client.get(reverse("caja:landing")).status_code == 403
        assert client.post(reverse("caja:link-factura", args=[fac.pk])).status_code == 403

    def test_sin_sesion_manda_al_login(self, client):
        r = client.get(reverse("caja:landing"))
        assert r.status_code == 302 and "sign-in" in r["Location"]

    def test_contador_genera_el_link_de_la_factura(self, client, usuario_factory, llaves, cliente, jefe):
        from apps.caja.models import LinkPago
        llaves()
        fac = _factura(cliente, jefe)
        client.force_login(usuario_factory(rol="contador"))
        r = client.get(reverse("caja:link-factura", args=[fac.pk]), HTTP_HX_REQUEST="true")
        assert "Generar link" in r.content.decode() and LinkPago.objects.count() == 0
        r = client.post(reverse("caja:link-factura", args=[fac.pk]), HTTP_HX_REQUEST="true")
        link = LinkPago.objects.get()
        assert link.url_publica() in r.content.decode()
        assert "Copiar link" in r.content.decode()

    def test_boton_en_la_factura_solo_con_la_caja_encendida(self, client, llaves, cliente, jefe):
        fac = _factura(cliente, jefe)
        client.force_login(jefe)
        url = reverse("facturacion:detalle", args=[fac.pk])
        boton = reverse("caja:link-factura", args=[fac.pk])
        assert boton not in client.get(url).content.decode()
        llaves()
        assert boton in client.get(url).content.decode()

    def test_boton_libre_en_la_ficha_del_cliente(self, client, llaves, cliente, jefe):
        client.force_login(jefe)
        url = reverse("cartera-detalle", args=[cliente.pk])
        assert reverse("caja:link-libre") not in client.get(url).content.decode()
        llaves()
        assert reverse("caja:link-libre") in client.get(url).content.decode()

    def test_link_libre_desde_la_ficha(self, client, llaves, cliente, jefe):
        from apps.caja.models import LinkPago
        llaves()
        client.force_login(jefe)
        r = client.post(reverse("caja:link-libre"), {"cliente": cliente.pk, "monto": "abc", "concepto": "Muestras"},
                        HTTP_HX_REQUEST="true")
        assert r.status_code == 400
        r = client.post(reverse("caja:link-libre"), {"cliente": cliente.pk, "monto": "$1,250.00",
                                                     "concepto": "Muestras"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert LinkPago.objects.get().monto == Decimal("1250.00")

    def test_anular_pide_permiso(self, client, usuario_factory, llaves, cliente, jefe):
        from apps.caja.services import crear_link_libre

        from cuentas.models.permiso_usuario import PermisoUsuario
        from lib.permisos import invalidar_cache_permisos
        llaves()
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        contador = usuario_factory(rol="contador")
        PermisoUsuario.objects.filter(usuario=contador, modulo="caja", permiso="anular_link").update(activo=False)
        invalidar_cache_permisos()
        client.force_login(contador)
        assert client.post(reverse("caja:link-anular", args=[link.pk])).status_code == 403
        client.force_login(jefe)
        client.post(reverse("caja:link-anular", args=[link.pk]), {"motivo": "ya no"})
        link.refresh_from_db()
        assert link.estado == "anulado"

    def test_mandar_por_correo(self, client, llaves, monkeypatch, cliente, jefe):
        from apps.caja.services import crear_link_libre

        from lib import cartero
        llaves()
        enviados = []
        monkeypatch.setattr(cartero, "enviar", lambda **kw: enviados.append(kw) or cartero.ResultadoCorreo(ok=True))
        link = crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        client.force_login(jefe)
        client.post(reverse("caja:link-correo", args=[link.pk]), HTTP_HX_REQUEST="true")
        assert enviados and enviados[0]["destinatario"] == "pagos@cliente.mx"
        assert link.url_publica() in enviados[0]["html"]

    def test_menu_y_notificaciones(self, client, jefe, usuario_factory):
        client.force_login(jefe)
        html = client.get(reverse("tesoreria:landing")).content.decode()
        assert reverse("caja:landing") in html
        html = client.get("/perfil/notificaciones/").content.decode()
        assert "La Caja · pagos en línea" in html
        client.force_login(usuario_factory(rol="disenador"))
        assert "La Caja · pagos en línea" not in client.get("/perfil/notificaciones/").content.decode()


# ── Cobranza y factura con link ──────────────────────────────────────────────


class TestCobranzaConLink:
    def _vencida(self, cliente, jefe):
        from apps.facturacion.models import Factura
        fac = _factura(cliente, jefe)
        Factura.objects.filter(pk=fac.pk).update(fecha_vencimiento=date.today() - timedelta(days=5))
        fac.refresh_from_db()
        return fac

    def test_el_recordatorio_lleva_el_boton(self, llaves, monkeypatch, cliente, jefe):
        from apps.caja.models import LinkPago
        from apps.facturacion import cobranza

        from lib import cartero
        enviados = []
        monkeypatch.setattr(cartero, "enviar", lambda **kw: enviados.append(kw) or cartero.ResultadoCorreo(ok=True))
        fac = self._vencida(cliente, jefe)
        cobranza.enviar_recordatorio(fac)
        assert "Pagar en línea" not in enviados[-1]["html"]
        llaves()
        cobranza.enviar_recordatorio(fac)
        assert LinkPago.objects.get().url_publica() in enviados[-1]["html"]
        assert "Pagar en línea" in enviados[-1]["html"]

    def test_plantilla_guardada_sin_boton_lo_recibe_anexado(self, llaves, monkeypatch, cliente, jefe):
        from apps.facturacion import cobranza

        from ajustes.models import PlantillaCorreo
        from lib import cartero
        llaves()
        enviados = []
        monkeypatch.setattr(cartero, "enviar", lambda **kw: enviados.append(kw) or cartero.ResultadoCorreo(ok=True))
        p = PlantillaCorreo.obtener("cobranza")
        p.cuerpo_html = "<p>Páguenos {{ saldo }}</p>"
        p.save()
        cobranza.enviar_recordatorio(self._vencida(cliente, jefe))
        assert "Pagar en línea" in enviados[-1]["html"]

    def test_la_vista_de_la_factura_lleva_el_link(self, llaves, cliente, jefe):
        from apps.facturacion.services import construir_html_pdf
        fac = _factura(cliente, jefe)
        assert "PAGO EN LÍNEA" not in construir_html_pdf(fac)
        llaves()
        assert "PAGO EN LÍNEA" in construir_html_pdf(fac)


# ── Permisos sembrados «como hoy» ────────────────────────────────────────────


class TestSiembraDePermisos:
    def test_catalogo_y_defaults(self):
        from lib.permisos_defaults import CATALOGO_PERMISOS, DEFAULTS_POR_ROL
        assert CATALOGO_PERMISOS["caja"] == ["ver", "crear_link", "anular_link", "revisar_pago"]
        assert set(DEFAULTS_POR_ROL["super_admin"]["caja"]) == set(CATALOGO_PERMISOS["caja"])
        assert "caja" not in DEFAULTS_POR_ROL["disenador"]

    def test_como_hoy(self, usuario_factory):
        from django.apps import apps as django_apps

        from cuentas.models.permiso_usuario import PermisoUsuario
        from cuentas.models.rol import Rol
        mig = importlib.import_module("apps.caja.migrations.0002_seed_permisos_caja")
        solo_ver = usuario_factory(rol="miembro")
        cobra = usuario_factory(rol="miembro")
        nada = usuario_factory(rol="miembro")
        sa = usuario_factory(rol="super_admin")
        PermisoUsuario.objects.filter(modulo="caja").delete()
        PermisoUsuario.objects.create(usuario=solo_ver, modulo="tesoreria", permiso="ver", activo=True)
        PermisoUsuario.objects.create(usuario=cobra, modulo="facturacion", permiso="cobrar", activo=True)
        PermisoUsuario.objects.create(usuario=nada, modulo="tesoreria", permiso="ver", activo=False)
        rol = Rol.objects.create(clave="administrativo_caja", nombre="Administrativo", permisos={"tesoreria": ["ver"]})
        mig.sembrar(django_apps, None)

        def caja_de(u):
            return set(PermisoUsuario.objects.filter(usuario=u, modulo="caja", activo=True)
                       .values_list("permiso", flat=True))
        assert caja_de(solo_ver) == {"ver"}
        assert caja_de(cobra) == {"ver", "crear_link", "anular_link", "revisar_pago"}
        assert caja_de(nada) == set()
        assert caja_de(sa) == {"ver", "crear_link", "anular_link", "revisar_pago"}
        rol.refresh_from_db()
        assert rol.permisos["caja"] == ["ver"]


# ── El Chalán ────────────────────────────────────────────────────────────────


class TestChalan:
    def test_lecturas_con_gating(self, llaves, cliente, jefe, usuario_factory):
        from apps.caja.services import crear_link_libre

        import capacidades
        llaves()
        crear_link_libre(monto="100", concepto="Muestras", actor=jefe, cliente=cliente)
        r = capacidades.ejecutar("links_de_pago", {"estado": "vigente"}, jefe)
        assert r["links_vigentes"] == 1 and r["links"][0]["url"].startswith("https://")
        assert "cobrado_en_linea_este_mes" in capacidades.ejecutar("pagos_recientes", {}, jefe)
        disenador = usuario_factory(rol="disenador")
        assert capacidades.ejecutar("pagos_recientes", {}, disenador)["error"] == "sin_permiso"
        assert "links_de_pago" not in {c.nombre for c in capacidades.listar(disenador)}

    def test_propuesta_registrada_y_gateada(self, jefe, usuario_factory):
        from apps.el_dictado.ejecutores import EJECUTORES
        from apps.el_dictado.prompt import SYSTEM_PROMPT

        from capacidades import CAPACIDADES
        from lib.dictado_catalogo import COMANDOS_DICTADO, CONSULTAS_CHAT, comandos_para
        assert "crear_link_pago" in {c["tipo"] for c in COMANDOS_DICTADO}
        assert "crear_link_pago" in EJECUTORES and "crear_link_pago" in SYSTEM_PROMPT
        assert CAPACIDADES["crear_link_pago"].modo == "propuesta"
        assert any("links_de_pago" in c["nombre"] for c in CONSULTAS_CHAT)
        assert "crear_link_pago" in {c["tipo"] for c in comandos_para(jefe)}
        assert "crear_link_pago" not in {c["tipo"] for c in comandos_para(usuario_factory(rol="disenador"))}

    def test_ejecutor(self, llaves, cliente, jefe, usuario_factory):
        from apps.caja.models import LinkPago
        from apps.el_dictado.ejecutores import EJECUTORES
        llaves()
        fac = _factura(cliente, jefe)
        r = EJECUTORES["crear_link_pago"]({"factura": fac.codigo}, jefe)
        assert r["entidad_tipo"] == "link_pago" and LinkPago.objects.get(pk=r["entidad_id"]).factura == fac
        with pytest.raises(ValueError, match="permiso"):
            EJECUTORES["crear_link_pago"]({"factura": fac.codigo}, usuario_factory(rol="disenador"))
        r = EJECUTORES["crear_link_pago"]({"cliente_slug": cliente.slug, "monto": "300",
                                           "concepto": "Muestras"}, jefe)
        assert LinkPago.objects.get(pk=r["entidad_id"]).tipo == "libre"

    def test_mcp_stdio(self, monkeypatch, llaves, jefe, usuario_factory):
        from mcp_despacho import herramientas
        llaves()
        monkeypatch.setenv(herramientas.ENV_USUARIO, jefe.email)
        assert "pagos" in herramientas.pagos_en_linea()
        assert "links" in herramientas.links_de_pago()
        otro = usuario_factory(rol="disenador")
        from cuentas.models.permiso_usuario import PermisoUsuario
        PermisoUsuario.objects.create(usuario=otro, modulo="mcp", permiso="usar", activo=True)
        monkeypatch.setenv(herramientas.ENV_USUARIO, otro.email)
        with pytest.raises(herramientas.ErrorAccesoMCP):
            herramientas.pagos_en_linea()
