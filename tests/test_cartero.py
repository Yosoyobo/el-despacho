"""El Cartero — envío de correo con canal intercambiable (SMTP / n8n).

No pega a servidores reales: mockea el send SMTP y la emisión Portavoz.
"""

from __future__ import annotations

import base64

import pytest

pytestmark = pytest.mark.django_db


def _set_cred(clave, valor):
    from ajustes.models.credencial import Credencial
    Credencial.guardar(clave, valor)


def _set_proveedor(prov):
    from ajustes.models import ConfiguracionCorreo
    cfg = ConfiguracionCorreo.obtener()
    cfg.proveedor = prov
    cfg.save()


def test_proveedor_default_es_n8n():
    from lib import cartero
    assert cartero.proveedor_activo() == "n8n"


def test_esta_configurado_n8n_requiere_webhook():
    from lib import cartero
    _set_proveedor("n8n")
    assert cartero.esta_configurado() is False
    _set_cred("n8n_webhook_url", "https://n8n.example/webhook")
    assert cartero.esta_configurado() is True


def test_esta_configurado_smtp_requiere_host_y_remitente():
    from lib import cartero
    _set_proveedor("smtp")
    assert cartero.esta_configurado() is False
    _set_cred("smtp_host", "smtp.example.com")
    _set_cred("smtp_from_email", "envia@example.com")
    assert cartero.esta_configurado() is True


def test_enviar_sin_destinatario_falla():
    from lib import cartero
    res = cartero.enviar(destinatario="", asunto="x", html="<p>x</p>")
    assert res.ok is False
    assert "destinatario" in res.error.lower()


def test_enviar_n8n_emite_evento_con_adjunto_base64(monkeypatch):
    from lib import cartero
    _set_proveedor("n8n")
    _set_cred("n8n_webhook_url", "https://n8n.example/webhook")

    capturado = {}
    import lib.portavoz as pv
    monkeypatch.setattr(pv, "emitir", lambda ev: capturado.update(ev=ev))

    pdf = b"%PDF-fake"
    res = cartero.enviar(
        destinatario="cliente@x.com", asunto="Cotización", html="<p>hola</p>",
        adjuntos=[cartero.Adjunto(nombre="COT-1.pdf", contenido=pdf)],
    )
    assert res.ok and res.proveedor == "n8n"
    ev = capturado["ev"]
    assert ev.tipo == "correo.solicitado"
    assert ev.payload["destinatario"] == "cliente@x.com"
    adj = ev.payload["adjuntos"][0]
    assert adj["nombre"] == "COT-1.pdf"
    assert base64.b64decode(adj["base64"]) == pdf


def test_enviar_smtp_usa_email_message(monkeypatch):
    from django.core.mail import EmailMultiAlternatives

    from lib import cartero
    _set_proveedor("smtp")
    _set_cred("smtp_host", "smtp.example.com")
    _set_cred("smtp_from_email", "envia@example.com")
    _set_cred("smtp_port", "587")

    enviados = {}

    def fake_send(self):
        enviados["asunto"] = self.subject
        enviados["to"] = self.to
        enviados["adjuntos"] = len(self.attachments)
        return 1

    monkeypatch.setattr(EmailMultiAlternatives, "send", fake_send)
    res = cartero.enviar(
        destinatario="cliente@x.com", asunto="Factura FAC-1", html="<p>x</p>",
        adjuntos=[cartero.Adjunto(nombre="FAC-1.pdf", contenido=b"%PDF")],
    )
    assert res.ok and res.proveedor == "smtp"
    assert enviados["to"] == ["cliente@x.com"]
    assert enviados["adjuntos"] == 1


def test_enviar_smtp_sin_config_falla():
    from lib import cartero
    _set_proveedor("smtp")
    res = cartero.enviar(destinatario="c@x.com", asunto="x", html="<p>x</p>")
    assert res.ok is False
    assert "SMTP" in res.error


def test_enviar_nunca_lanza(monkeypatch):
    from django.core.mail import EmailMultiAlternatives

    from lib import cartero
    _set_proveedor("smtp")
    _set_cred("smtp_host", "smtp.example.com")
    _set_cred("smtp_from_email", "envia@example.com")
    monkeypatch.setattr(EmailMultiAlternatives, "send",
                        lambda self: (_ for _ in ()).throw(OSError("conexión rechazada")))
    res = cartero.enviar(destinatario="c@x.com", asunto="x", html="<p>x</p>")
    assert res.ok is False  # capturó la excepción, no la propagó
