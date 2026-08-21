"""Canal Gmail API de El Cartero — el que sí puede salir del Droplet.

Contexto (para que nadie lo «simplifique» de vuelta a SMTP): DigitalOcean tiene
bloqueada la salida SMTP del Droplet de La Sede. Se comprobó desde el host y
desde el contenedor: los puertos 25, 465, 587 y 2525 se caen por **timeout**
mientras el 443 va perfecto. Así que `smtp.gmail.com` es inalcanzable y
`smtp-relay.gmail.com` lo sería igual — no es el sabor de SMTP, es que este
Droplet no puede hablar SMTP con nadie. La API de Gmail va por HTTPS/443.

Detalle que confundió el diagnóstico y vale recordar: el error que reportaba la
app era `[Errno 101] Network is unreachable`, no un timeout. Es porque el DNS de
`smtp.gmail.com` devuelve IPv6 primero, el contenedor no tiene ruta IPv6 y falla
al instante — tapando el timeout real de IPv4.

No pega a Google: se mockea `httpx`.
"""

from __future__ import annotations

import base64

import pytest

pytestmark = pytest.mark.django_db


def _cred(clave, valor):
    from ajustes.models.credencial import Credencial
    Credencial.guardar(clave, valor)


def _cliente_oauth_listo():
    _cred("google_oauth_client_id", "cid.apps.googleusercontent.com")
    _cred("google_oauth_client_secret", "secreto")


def _conectado(remitente="hola@learningcenter.mx"):
    _cliente_oauth_listo()
    _cred("gmail_api_oauth_refresh_token", "1//refresh")
    if remitente:
        _cred("gmail_api_remitente", remitente)


class _Resp:
    """Respuesta mínima estilo httpx."""

    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _Cli:
    """Cliente httpx de mentiras que apunta lo que se le pidió."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, **kw):
        self.llamadas.append(("POST", url, kw))
        return self.respuestas.pop(0)

    def get(self, url, **kw):
        self.llamadas.append(("GET", url, kw))
        return self.respuestas.pop(0)


def _mock_httpx(monkeypatch, respuestas):
    from lib import gmail_api
    cli = _Cli(respuestas)
    monkeypatch.setattr(gmail_api.httpx, "Client", lambda **kw: cli)
    return cli


# ── Configuración ────────────────────────────────────────────────────────────


def test_no_configurado_sin_refresh_token():
    from lib import gmail_api
    _cliente_oauth_listo()
    assert gmail_api.esta_configurado() is False
    assert gmail_api.esta_conectado() is False


def test_conectado_pero_sin_remitente_no_esta_listo():
    """Sin remitente Gmail escribiría desde quien sabe dónde: no cuenta como listo."""
    from lib import gmail_api
    _conectado(remitente=None)
    assert gmail_api.esta_conectado() is True
    assert gmail_api.esta_configurado() is False


def test_configurado_completo():
    from lib import gmail_api
    _conectado()
    assert gmail_api.esta_configurado() is True
    assert gmail_api.remitente() == "hola@learningcenter.mx"


def test_sin_cliente_oauth_el_consentimiento_falla():
    from lib import gmail_api
    with pytest.raises(gmail_api.NoConfiguradoError):
        gmail_api.construir_url_consentimiento("https://x/cb", "st")


# ── Consentimiento ───────────────────────────────────────────────────────────


def test_url_de_consentimiento_pide_solo_enviar_y_offline():
    from lib import gmail_api
    _cliente_oauth_listo()
    url = gmail_api.construir_url_consentimiento("https://taller.example/cb", "st4te")

    assert "gmail.send" in url
    # Sin refresh token no se puede mandar correo mañana sin volver a pedir permiso.
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "state=st4te" in url
    # NO acumular scopes: si no, este token también serviría para Drive y se
    # perdería la separación por servicio.
    assert "include_granted_scopes" not in url
    # El scope de lectura NUNCA debe aparecer.
    assert "gmail.readonly" not in url
    assert "mail.google.com" not in url


def test_intercambio_devuelve_refresh_token(monkeypatch):
    from lib import gmail_api
    _cliente_oauth_listo()
    cli = _mock_httpx(monkeypatch, [_Resp(200, {"refresh_token": "1//nuevo"})])

    assert gmail_api.intercambiar_codigo_por_refresh_token("code", "https://x/cb") == "1//nuevo"
    _, url, kw = cli.llamadas[0]
    assert url == gmail_api.TOKEN_URL
    assert kw["data"]["grant_type"] == "authorization_code"


def test_intercambio_sin_refresh_token_avisa_que_hay_que_revocar(monkeypatch):
    """Google omite el refresh token si ya se había consentido: hay que revocar."""
    from lib import gmail_api
    _cliente_oauth_listo()
    _mock_httpx(monkeypatch, [_Resp(200, {"access_token": "solo-este"})])

    with pytest.raises(gmail_api.NoConfiguradoError) as exc:
        gmail_api.intercambiar_codigo_por_refresh_token("code", "https://x/cb")
    assert "revoca" in str(exc.value).lower()


# ── Envío ────────────────────────────────────────────────────────────────────


def test_enviar_mime_usa_base64_urlsafe_y_bearer(monkeypatch):
    from lib import gmail_api
    _conectado()
    cli = _mock_httpx(monkeypatch, [
        _Resp(200, {"access_token": "at"}),      # refresh → access token
        _Resp(200, {"id": "18f0abc"}),           # send
    ])

    # Bytes que en base64 estándar producen '+' y '/', justo lo que Gmail rechaza.
    crudo = bytes([251, 255, 190, 255])
    assert gmail_api.enviar_mime(crudo) == "18f0abc"

    _, url, kw = cli.llamadas[1]
    assert url == gmail_api.SEND_URL
    assert kw["headers"]["Authorization"] == "Bearer at"
    raw = kw["json"]["raw"]
    assert "+" not in raw and "/" not in raw, "Gmail necesita base64 URL-safe"
    assert base64.urlsafe_b64decode(raw) == crudo


def test_enviar_mime_traduce_el_error_de_gmail(monkeypatch):
    from lib import gmail_api
    _conectado()
    _mock_httpx(monkeypatch, [
        _Resp(200, {"access_token": "at"}),
        _Resp(403, {"error": {"message": "Delegation denied for hola@learningcenter.mx"}}),
    ])

    with pytest.raises(gmail_api.GmailApiError) as exc:
        gmail_api.enviar_mime(b"algo")
    assert "Delegation denied" in str(exc.value)


def test_token_revocado_pide_reconectar(monkeypatch):
    from lib import gmail_api
    _conectado()
    _mock_httpx(monkeypatch, [_Resp(400, {"error": "invalid_grant"})])

    with pytest.raises(gmail_api.NoConfiguradoError) as exc:
        gmail_api.enviar_mime(b"algo")
    assert "reconecta" in str(exc.value).lower()


def test_probar_cuenta_403_como_exito(monkeypatch):
    """`gmail.send` no autoriza leer el perfil: un 403 confirma scope mínimo."""
    from lib import gmail_api
    _conectado()
    _mock_httpx(monkeypatch, [_Resp(200, {"access_token": "at"}), _Resp(403, {})])

    res = gmail_api.probar()
    assert res["ok"] is True
    assert "mínimo" in res["detalle"]


def test_probar_401_es_falla(monkeypatch):
    from lib import gmail_api
    _conectado()
    _mock_httpx(monkeypatch, [_Resp(200, {"access_token": "at"}), _Resp(401, {})])

    res = gmail_api.probar()
    assert res["ok"] is False


# ── Integración con El Cartero ───────────────────────────────────────────────


def _set_proveedor(prov):
    from ajustes.models import ConfiguracionCorreo
    cfg = ConfiguracionCorreo.obtener()
    cfg.proveedor = prov
    cfg.save()


def test_cartero_esta_configurado_con_gmail():
    from lib import cartero
    _set_proveedor("gmail_api")
    assert cartero.esta_configurado() is False
    _conectado()
    assert cartero.esta_configurado() is True


def test_cartero_manda_por_gmail_con_adjunto(monkeypatch):
    """El MIME se arma con Django, así que adjuntos y HTML salen como por SMTP."""
    from lib import cartero, gmail_api
    _set_proveedor("gmail_api")
    _conectado()

    capturado = {}

    def _fake(mensaje_bytes):
        capturado["mime"] = mensaje_bytes
        return "id-1"

    monkeypatch.setattr(gmail_api, "enviar_mime", _fake)

    res = cartero.enviar(
        destinatario="cliente@example.com", asunto="Tu cotización",
        html="<p>Hola</p>",
        adjuntos=[cartero.Adjunto(nombre="cot.pdf", contenido=b"%PDF-1.4 x")],
    )

    assert res.ok is True
    assert res.proveedor == "gmail_api"
    mime = capturado["mime"].decode("utf-8", errors="replace")
    assert "cliente@example.com" in mime
    assert "Tu cotización" in mime or "=?utf-8?" in mime  # el asunto puede ir codificado
    assert "cot.pdf" in mime
    # El remitente sale del slot de Gmail, no del de SMTP.
    assert "hola@learningcenter.mx" in mime


def test_cartero_sin_conectar_no_intenta_mandar():
    from lib import cartero
    _set_proveedor("gmail_api")
    _cliente_oauth_listo()  # falta el refresh token

    res = cartero.enviar(destinatario="x@example.com", asunto="a", html="<p>b</p>")
    assert res.ok is False
    assert res.proveedor == "gmail_api"
    assert "conectar" in res.error.lower()


def test_remitente_de_gmail_gana_sobre_el_de_smtp():
    """Con el canal Gmail activo, el From es el suyo aunque haya slots SMTP."""
    from lib import cartero
    _set_proveedor("gmail_api")
    _conectado(remitente="cotizaciones@learningcenter.mx")
    _cred("smtp_from_email", "viejo@otrodominio.mx")

    assert "cotizaciones@learningcenter.mx" in cartero._remitente()
    assert "viejo@otrodominio.mx" not in cartero._remitente()


def test_el_canal_gmail_existe_en_los_choices():
    from ajustes.models.cartero import PROVEEDORES_CORREO
    claves = [c for c, _ in PROVEEDORES_CORREO]
    assert "gmail_api" in claves
    # `max_length=10` en el modelo: si la clave creciera, la migración rompería.
    assert len("gmail_api") <= 10
