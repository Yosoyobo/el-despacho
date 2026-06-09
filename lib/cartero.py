"""El Cartero — envío de correo con canal intercambiable (SMTP / n8n).

El Cartero COMPONE el correo (asunto, cuerpo HTML, adjuntos) y DECIDE; el canal
solo entrega. El canal activo se elige en La Gerencia (`ajustes.ConfiguracionCorreo`):

- `smtp`  → Django `EmailMessage` con una conexión armada al vuelo desde La
            Bóveda (slots `smtp_host`, `smtp_port`, `smtp_user`,
            `smtp_password`, `smtp_use_tls`, `smtp_from_email`).
- `n8n`   → emite el evento Portavoz `correo.solicitado` con el correo YA
            armado (adjuntos en base64); el workflow de n8n solo lo manda.

Diseño defensivo: `enviar()` NUNCA lanza — devuelve `ResultadoCorreo(ok=False,
error=...)` y el caller decide (p.ej. marcar la cotización como enviada aunque
el correo falle, y avisar). Todas las credenciales viven cifradas en La Bóveda.

Slots SMTP (claves en `ajustes.Credencial`):
    smtp_host · smtp_port · smtp_user · smtp_password · smtp_use_tls · smtp_from_email
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field

SLOTS_SMTP = [
    ("smtp_host", "Servidor (host)", "Ej. smtp.gmail.com o mail.tudominio.mx", "text"),
    ("smtp_port", "Puerto", "587 (TLS) o 465 (SSL)", "text"),
    ("smtp_user", "Usuario", "Usuario/cuenta de autenticación.", "text"),
    ("smtp_password", "Contraseña", "Contraseña o app password.", "password"),
    ("smtp_from_email", "Correo remitente", "Ej. cotizaciones@tudominio.mx", "text"),
    ("smtp_use_tls", "Usar TLS", "1 = sí (recomendado), 0 = no.", "text"),
]


@dataclass
class Adjunto:
    nombre: str
    contenido: bytes
    mime: str = "application/pdf"


@dataclass
class ResultadoCorreo:
    ok: bool
    proveedor: str = ""
    error: str = ""
    detalle: str = ""


@dataclass
class _Mensaje:
    destinatario: str
    asunto: str
    html: str
    texto: str = ""
    adjuntos: list[Adjunto] = field(default_factory=list)


def _cred(clave: str) -> str:
    from ajustes.models.credencial import Credencial
    return (Credencial.obtener(clave) or "").strip()


def proveedor_activo() -> str:
    """Canal de correo elegido en La Gerencia. Default 'n8n'."""
    try:
        from ajustes.models import ConfiguracionCorreo
        return ConfiguracionCorreo.obtener().proveedor
    except Exception:  # noqa: BLE001 — sin DB/migración → default seguro
        return "n8n"


def esta_configurado() -> bool:
    """True si el canal activo tiene lo mínimo para entregar."""
    prov = proveedor_activo()
    if prov == "smtp":
        return bool(_cred("smtp_host") and _cred("smtp_from_email"))
    return bool(_cred("n8n_webhook_url"))


def enviar(
    *, destinatario: str, asunto: str, html: str, texto: str = "",
    adjuntos: list[Adjunto] | None = None,
) -> ResultadoCorreo:
    """Envía un correo por el canal activo. Nunca lanza."""
    destinatario = (destinatario or "").strip()
    if not destinatario:
        return ResultadoCorreo(ok=False, error="Sin destinatario.")
    msg = _Mensaje(
        destinatario=destinatario, asunto=asunto or "(sin asunto)",
        html=html or "", texto=texto or "", adjuntos=list(adjuntos or []),
    )
    prov = proveedor_activo()
    try:
        if prov == "smtp":
            return _enviar_smtp(msg)
        return _enviar_n8n(msg)
    except Exception as exc:  # noqa: BLE001 — fallback gracioso
        return ResultadoCorreo(ok=False, proveedor=prov, error=f"El Cartero falló: {exc}")


def _remitente() -> str:
    """`Nombre <correo>` para el From, con el nombre de ConfiguracionCorreo."""
    correo = _cred("smtp_from_email") or _cred("smtp_user")
    try:
        from ajustes.models import ConfiguracionCorreo
        nombre = (ConfiguracionCorreo.obtener().remitente_nombre or "").strip()
    except Exception:  # noqa: BLE001
        nombre = ""
    if nombre and correo:
        return f"{nombre} <{correo}>"
    return correo or "noreply@localhost"


def _enviar_smtp(msg: _Mensaje) -> ResultadoCorreo:
    from django.core.mail import EmailMultiAlternatives, get_connection

    host = _cred("smtp_host")
    from_email = _cred("smtp_from_email") or _cred("smtp_user")
    if not host or not from_email:
        return ResultadoCorreo(
            ok=False, proveedor="smtp",
            error="SMTP sin configurar (faltan host o correo remitente en Ajustes → El Cartero).",
        )
    try:
        puerto = int(_cred("smtp_port") or 587)
    except ValueError:
        puerto = 587
    usa_tls = _cred("smtp_use_tls") not in ("0", "false", "no", "")
    conexion = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=host, port=puerto,
        username=_cred("smtp_user") or None,
        password=_cred("smtp_password") or None,
        use_tls=usa_tls, use_ssl=(not usa_tls and puerto == 465),
        timeout=20,
    )
    correo = EmailMultiAlternatives(
        subject=msg.asunto, body=(msg.texto or _html_a_texto(msg.html)),
        from_email=_remitente(), to=[msg.destinatario], connection=conexion,
    )
    correo.attach_alternative(msg.html, "text/html")
    for a in msg.adjuntos:
        correo.attach(a.nombre, a.contenido, a.mime)
    enviados = correo.send()
    if enviados:
        return ResultadoCorreo(ok=True, proveedor="smtp", detalle=f"Enviado a {msg.destinatario}.")
    return ResultadoCorreo(ok=False, proveedor="smtp", error="El servidor SMTP no aceptó el correo.")


def _enviar_n8n(msg: _Mensaje) -> ResultadoCorreo:
    """Emite el correo YA armado como evento Portavoz; n8n solo lo entrega."""
    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz

    if not _cred("n8n_webhook_url"):
        return ResultadoCorreo(
            ok=False, proveedor="n8n",
            error="n8n sin configurar (falta el Webhook URL en Ajustes).",
        )
    adjuntos = [
        {"nombre": a.nombre, "mime": a.mime,
         "base64": base64.b64encode(a.contenido).decode("ascii")}
        for a in msg.adjuntos
    ]
    emitir(EventoPortavoz(
        tipo="correo.solicitado",
        actor_id=None,
        actor_email=None,
        payload={
            "destinatario": msg.destinatario,
            "asunto": msg.asunto,
            "html": msg.html,
            "texto": msg.texto,
            "remitente": _remitente(),
            "adjuntos": adjuntos,
        },
    ))
    # El Portavoz encola en Redis; la entrega real la hace el worker → n8n.
    return ResultadoCorreo(ok=True, proveedor="n8n",
                           detalle="Encolado para entrega por n8n.")


def _html_a_texto(html: str) -> str:
    """Fallback de texto plano muy simple para el cuerpo del correo."""
    import re
    sin_tags = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", sin_tags).strip()


def probar(destinatario: str) -> ResultadoCorreo:
    """Manda un correo de prueba por el canal activo."""
    return enviar(
        destinatario=destinatario,
        asunto="Prueba de El Cartero · El Despacho",
        html="<p>¡Funciona! Este es un correo de prueba enviado por "
             "<strong>El Cartero</strong> de El Despacho.</p>",
        texto="¡Funciona! Correo de prueba de El Cartero.",
    )


__all__ = ["Adjunto", "ResultadoCorreo", "enviar", "probar",
           "proveedor_activo", "esta_configurado", "SLOTS_SMTP"]
