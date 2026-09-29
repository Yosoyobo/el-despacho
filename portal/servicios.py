"""La lógica de los accesos a La Recepción — fuente única para las tres apps.

- **El Taller** invita y revoca desde la ficha del cliente (y El Chalán lo
  propone): `invitar()`, `revocar()`, `accesos_de()`.
- **La Recepción** deja entrar: `pedir_enlace()`, `canjear()`,
  `acceso_de_sesion()`, `abrir_sesion()`, `cerrar_sesion()`.

Nada de esto toca `cuentas.Usuario`: un cliente no es un usuario del equipo.

**La llave no caduca ni se gasta** (Oscar, 2026-09-29; el porqué completo en
`models/enlace.py`). Cada persona tiene UNA llave viva; invitar, reenviar y
«pedir mi enlace» mandan esa misma. Lo que la protege es el correo: el GET del
enlace sólo pinta la pantalla, y el POST abre la sesión únicamente si trae el
correo al que se mandó. Que el GET no haga nada sigue importando: los filtros de
correo (Outlook «Safe Links», antivirus corporativos) abren los enlaces antes que
la persona.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import (
    MOTIVO_ENTRADA,
    MOTIVO_INVITACION,
    AccesoCliente,
    EnlaceAcceso,
    EventoPortal,
)

logger = logging.getLogger(__name__)

#: Llaves de la sesión de La Recepción. Nada más se guarda ahí.
SESION_ACCESO = "portal_acceso"
SESION_GENERACION = "portal_generacion"

#: Cuánto dura la sesión de un cliente. Una semana: el enlace por correo es
#: fricción, y pedirlo cada día haría que nadie lo usara. Revocar la corta al
#: instante de todos modos (ver `generacion`).
DURACION_SESION_SEG = 7 * 24 * 3600


class ErrorPortal(ValueError):
    """Un error que se le puede enseñar tal cual a quien opera (español llano)."""


# ── Utilidades ───────────────────────────────────────────────────────────────


def hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def url_recepcion() -> str:
    """La dirección pública de La Recepción, sin diagonal final."""
    try:
        from django.conf import settings

        base = getattr(settings, "RECEPCION_URL", "") or ""
    except Exception:  # noqa: BLE001
        base = ""
    base = base or os.environ.get("RECEPCION_URL", "") or "https://recepcion.learningcenter.mx"
    return base.rstrip("/")


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def _ip(request) -> str:
    if request is None:
        return ""
    from lib.auditoria_acceso import ip_de

    return ip_de(request)


def registrar_evento(acceso, tipo: str, detalle: str = "", request=None) -> None:
    """Anota en la bitácora del portal. **Nunca lanza.**"""
    try:
        EventoPortal.objects.create(
            acceso=acceso, tipo=tipo, detalle=(detalle or "")[:300],
            ip=_ip(request),
            agente=((request.META.get("HTTP_USER_AGENT") or "") if request is not None else "")[:300],
        )
    except Exception:  # noqa: BLE001 — la bitácora no puede tumbar nada
        logger.warning("portal: no se pudo registrar el evento %s", tipo, exc_info=True)


def _emitir(tipo: str, acceso, actor=None, extra: dict | None = None) -> None:
    """Evento tipado al Portavoz. Best-effort: nunca tumba la acción."""
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        payload = {"acceso_id": acceso.pk, "cliente_id": acceso.cliente_id,
                   "email": acceso.email}
        payload.update(extra or {})
        emitir(EventoPortavoz(
            tipo=tipo,
            actor_id=getattr(actor, "pk", None) if getattr(actor, "is_authenticated", False) else None,
            actor_email=getattr(actor, "email", None) if getattr(actor, "is_authenticated", False) else None,
            payload=payload,
        ))
    except Exception:  # noqa: BLE001
        logger.warning("portal: no se pudo emitir %s", tipo, exc_info=True)


def _cifrar(token: str) -> str:
    try:
        from lib.boveda import cifrar

        return cifrar(token)
    except Exception:  # noqa: BLE001 — sin cifrar la llave sirve igual; sólo no se puede reenviar
        logger.warning("portal: no se pudo cifrar la llave", exc_info=True)
        return ""


def _descifrar(blob: str) -> str:
    if not blob:
        return ""
    try:
        from lib.boveda import descifrar

        return descifrar(blob)
    except Exception:  # noqa: BLE001 — manipulado o de otra llave maestra
        logger.warning("portal: no se pudo descifrar una llave", exc_info=True)
        return ""


def _anular_vivos(acceso, ahora=None) -> int:
    ahora = ahora or timezone.now()
    return EnlaceAcceso.objects.filter(acceso=acceso, anulado_en__isnull=True).update(anulado_en=ahora)


def _crear_enlace(acceso, motivo: str, ip: str = "") -> str:
    """Crea una llave NUEVA y devuelve el token en claro.

    Sólo una llave vive por persona: las anteriores se anulan aquí. No caduca.
    """
    token = secrets.token_urlsafe(32)
    ahora = timezone.now()
    _anular_vivos(acceso, ahora)
    EnlaceAcceso.objects.create(
        acceso=acceso, token_hash=hash_token(token), token_cifrado=_cifrar(token),
        motivo=motivo, creado_en=ahora, expira_en=None, ip_solicitud=(ip or "")[:64],
    )
    return token


def llave_viva(acceso) -> EnlaceAcceso | None:
    ahora = timezone.now()
    return (EnlaceAcceso.objects.filter(acceso=acceso, anulado_en__isnull=True)
            .filter(Q(expira_en__isnull=True) | Q(expira_en__gt=ahora))
            .order_by("-creado_en").first())


def llave_de(acceso, motivo: str = MOTIVO_ENTRADA, ip: str = "") -> str:
    """El token de la llave viva de la persona; si no tiene (o es de antes y no
    se puede reenviar), una nueva. Siempre devuelve un token que abre."""
    viva = llave_viva(acceso)
    if viva is not None:
        token = _descifrar(viva.token_cifrado)
        if token and hash_token(token) == viva.token_hash:
            return token
    return _crear_enlace(acceso, motivo, ip)


def url_de_enlace(token: str) -> str:
    return f"{url_recepcion()}/entrar/{token}/"


# ── Qué correos de un cliente se pueden invitar ─────────────────────────────


@dataclass
class Invitable:
    email: str
    nombre: str
    puesto: str
    contacto: object | None
    acceso: AccesoCliente | None


def invitables_de(cliente) -> list[Invitable]:
    """Los correos registrados del cliente, cada uno con su acceso (si tiene).

    Se invita sólo a correos que el cliente ya tiene capturados en su ficha: sus
    contactos y el correo «de siempre» (`email_contacto`). Así nadie —ni El
    Chalán— manda una invitación a un correo escrito al vuelo.
    """
    accesos = {a.email: a for a in AccesoCliente.objects.filter(cliente=cliente)}
    filas: list[Invitable] = []
    vistos: set[str] = set()
    for c in cliente.contactos.all():
        email = normalizar_email(c.email)
        if not email or email in vistos:
            continue
        vistos.add(email)
        filas.append(Invitable(email=email, nombre=c.nombre, puesto=c.puesto,
                               contacto=c, acceso=accesos.get(email)))
    legado = normalizar_email(getattr(cliente, "email_contacto", ""))
    if legado and legado not in vistos:
        vistos.add(legado)
        filas.append(Invitable(email=legado, nombre=cliente.nombre_contacto or "",
                               puesto="", contacto=None, acceso=accesos.get(legado)))
    # Accesos cuyo correo ya no está en la ficha (se editó el contacto): se
    # siguen enseñando para que se puedan revocar.
    for email, acceso in accesos.items():
        if email not in vistos:
            filas.append(Invitable(email=email, nombre=acceso.nombre, puesto="",
                                   contacto=acceso.contacto, acceso=acceso))
    return filas


def accesos_de(cliente) -> list[AccesoCliente]:
    return list(AccesoCliente.objects.filter(cliente=cliente)
                .select_related("invitado_por", "contacto").order_by("-activo", "nombre", "email"))


# ── Invitar / revocar (El Taller) ───────────────────────────────────────────


@dataclass
class ResultadoInvitacion:
    acceso: AccesoCliente
    correo_ok: bool
    error_correo: str = ""


def invitar(cliente, email: str, actor, request=None) -> ResultadoInvitacion:
    """Da de alta (o reactiva) el acceso y le manda su invitación por correo.

    Lanza `ErrorPortal` si no se puede: correo que no es del cliente, cliente
    archivado, o el correo ya entra al portal de OTRO cliente. Si el acceso
    quedó pero el correo no salió, NO lanza: lo dice en el resultado y se puede
    reenviar.
    """
    email = normalizar_email(email)
    try:
        validate_email(email)
    except ValidationError as exc:
        raise ErrorPortal("Ese correo no parece válido.") from exc
    if not getattr(cliente, "activo", True):
        raise ErrorPortal("El cliente está archivado: reactívalo antes de invitar a alguien.")
    fila = next((f for f in invitables_de(cliente) if f.email == email), None)
    if fila is None:
        raise ErrorPortal(
            "Ese correo no es de ningún contacto de este cliente. Agrégalo primero "
            "como contacto en su ficha.")
    otro = (AccesoCliente.objects.filter(email=email, activo=True)
            .exclude(cliente=cliente).select_related("cliente").first())
    if otro is not None:
        raise ErrorPortal(
            f"Ese correo ya entra al portal de «{otro.cliente.razon_social}». Un "
            "correo sólo puede abrir un cliente: revócalo allá primero.")

    ahora = timezone.now()
    try:
        with transaction.atomic():
            acceso = (AccesoCliente.objects.select_for_update()
                      .filter(cliente=cliente, email=email).first())
            if acceso is None:
                acceso = AccesoCliente(cliente=cliente, email=email)
            elif not acceso.activo:
                # Reactivar sube la generación: una sesión de antes de revocar no
                # revive con la nueva invitación.
                acceso.generacion = (acceso.generacion or 1) + 1
            acceso.activo = True
            acceso.nombre = (fila.nombre or acceso.nombre or "")[:200]
            acceso.contacto = fila.contacto if fila.contacto is not None else acceso.contacto
            acceso.invitado_por = actor if getattr(actor, "is_authenticated", False) else None
            acceso.invitado_en = ahora
            acceso.revocado_en = None
            acceso.revocado_por = None
            acceso.save()
            token = llave_de(acceso, MOTIVO_INVITACION, _ip(request))
    except IntegrityError as exc:  # carrera contra otra invitación del mismo correo
        raise ErrorPortal("Ese correo ya tiene un acceso activo en otro cliente.") from exc

    registrar_evento(acceso, "invitado",
                     f"por {getattr(actor, 'email', '') or 'el sistema'}", request)
    _emitir("portal.acceso_invitado", acceso, actor)
    res = _mandar_correo(acceso, token, invitacion=True)
    return ResultadoInvitacion(acceso=acceso, correo_ok=res.ok, error_correo=res.error)


def revocar(acceso: AccesoCliente, actor, request=None) -> AccesoCliente:
    """Quita el acceso. La sesión viva de esa persona muere en su siguiente clic
    y ningún enlace pendiente sirve ya."""
    ahora = timezone.now()
    with transaction.atomic():
        acceso = AccesoCliente.objects.select_for_update().get(pk=acceso.pk)
        if not acceso.activo:
            return acceso
        acceso.activo = False
        acceso.generacion = (acceso.generacion or 1) + 1
        acceso.revocado_en = ahora
        acceso.revocado_por = actor if getattr(actor, "is_authenticated", False) else None
        acceso.save()
        _anular_vivos(acceso, ahora)
    registrar_evento(acceso, "revocado",
                     f"por {getattr(actor, 'email', '') or 'el sistema'}", request)
    _emitir("portal.acceso_revocado", acceso, actor)
    return acceso


# ── Correo ───────────────────────────────────────────────────────────────────


def _mandar_correo(acceso: AccesoCliente, token: str, *, invitacion: bool, cambiado: bool = False):
    """Arma y manda el correo del enlace por El Cartero. Nunca lanza.

    La plantilla es de ARCHIVO y no editable en Gerencia a propósito: este
    correo es la llave del portal y el enlace no puede quedarse fuera por una
    edición. El texto se cambia en `portal/templates/portal/correo_enlace.html`.
    """
    from django.template.loader import render_to_string

    from lib import cartero

    contexto = {
        "nombre": acceso.nombre_visible,
        "empresa": acceso.cliente.razon_social,
        # El correo NO va en el cuerpo: es lo que se pide al abrir la llave, y un
        # correo reenviado lo llevaría junto con ella.
        "enlace": url_de_enlace(token),
        "portal": url_recepcion(),
        "invitacion": invitacion,
        "cambiado": cambiado,
    }
    if invitacion:
        asunto = "Te invitamos al portal de clientes de Learning Center"
    elif cambiado:
        asunto = "Tu nuevo enlace para entrar a Learning Center"
    else:
        asunto = "Tu enlace para entrar a Learning Center"
    try:
        html = render_to_string("portal/correo_enlace.html", contexto)
    except Exception as exc:  # noqa: BLE001
        logger.exception("portal: no se pudo armar el correo")
        return cartero.ResultadoCorreo(ok=False, error=f"No se pudo armar el correo: {exc}")
    return cartero.enviar(destinatario=acceso.email, asunto=asunto, html=html)


# ── Entrar (La Recepción) ────────────────────────────────────────────────────


def acceso_activo_por_email(email: str) -> AccesoCliente | None:
    email = normalizar_email(email)
    if not email:
        return None
    return (AccesoCliente.objects.filter(email=email, activo=True, cliente__activo=True)
            .select_related("cliente").first())


def pedir_enlace(email: str, request=None) -> None:
    """Si el correo tiene acceso, le reenvía SU llave (la misma). Si no, nada.

    **No devuelve nada a propósito**: quien llama responde lo mismo en los dos
    casos, así que nadie puede preguntar a La Recepción quién es cliente. El
    correo sale en el fondo para que tampoco lo delate cuánto tarda la
    respuesta.
    """
    acceso = acceso_activo_por_email(email)
    if acceso is None:
        return
    token = llave_de(acceso, MOTIVO_ENTRADA, _ip(request))
    registrar_evento(acceso, "enlace", "", request)

    from lib.tareas_fondo import ejecutar_en_fondo

    acceso_id = acceso.pk

    def _enviar():
        fresco = AccesoCliente.objects.select_related("cliente").get(pk=acceso_id)
        res = _mandar_correo(fresco, token, invitacion=False)
        if not res.ok:
            logger.warning("portal: no salió el enlace de acceso %s: %s", acceso_id, res.error)

    ejecutar_en_fondo(_enviar)


# Por qué no se pudo canjear un enlace. Van a la pantalla: la persona que tiene
# el enlace en la mano sí puede saber si se cambió o si su acceso se quitó.
CANJE_INVALIDO = "invalido"
CANJE_ANULADO = "anulado"
CANJE_EXPIRADO = "expirado"
CANJE_SIN_ACCESO = "sin_acceso"
CANJE_CORREO = "correo"


def buscar_enlace(token: str) -> tuple[EnlaceAcceso | None, str]:
    """El enlace del token y si sirve. (enlace, "") o (enlace|None, motivo)."""
    if not token or len(token) > 200:
        return None, CANJE_INVALIDO
    enlace = (EnlaceAcceso.objects.filter(token_hash=hash_token(token))
              .select_related("acceso", "acceso__cliente").first())
    if enlace is None:
        return None, CANJE_INVALIDO
    if not enlace.acceso.activo or not enlace.acceso.cliente.activo:
        return enlace, CANJE_SIN_ACCESO
    if enlace.anulado_en is not None:
        return enlace, CANJE_ANULADO
    if enlace.expira_en is not None and enlace.expira_en <= timezone.now():
        return enlace, CANJE_EXPIRADO
    return enlace, ""


def correo_coincide(acceso: AccesoCliente, email: str) -> bool:
    """En tiempo constante: la respuesta no delata cuántas letras acertó."""
    return hmac.compare_digest(normalizar_email(email).encode("utf-8"),
                               normalizar_email(acceso.email).encode("utf-8"))


def canjear(token: str, email: str, request=None) -> tuple[AccesoCliente | None, str]:
    """Abre la sesión con la llave si `email` es el correo al que se mandó.

    (acceso, "") si abre; (None, motivo) si no. La llave NO se gasta: sirve la
    próxima vez. Una llave de antes de 2026-09-29 (sólo hash) se cifra aquí,
    porque es el único momento en que el token viaja en claro, y desde entonces
    se puede reenviar.
    """
    enlace, motivo = buscar_enlace(token)
    if motivo:
        return None, motivo
    acceso = enlace.acceso
    if not correo_coincide(acceso, email):
        registrar_evento(acceso, "correo_mal", "", request)
        return None, CANJE_CORREO
    ahora = timezone.now()
    cambios = {"usos": F("usos") + 1, "ultimo_uso_en": ahora, "ip_uso": _ip(request)[:64]}
    if enlace.usado_en is None:
        cambios["usado_en"] = ahora
    if not enlace.token_cifrado:
        cifrado = _cifrar(token)
        if cifrado:
            cambios["token_cifrado"] = cifrado
    EnlaceAcceso.objects.filter(pk=enlace.pk).update(**cambios)
    acceso.ultima_entrada_en = ahora
    acceso.save(update_fields=["ultima_entrada_en", "actualizado_en"])
    registrar_evento(acceso, "entrada", "con su enlace", request)
    return acceso, ""


# ── La llave desde El Taller: reenviar, copiar, cambiar ─────────────────────


def enlace_para_copiar(acceso: AccesoCliente, actor, request=None) -> str:
    """La URL de su llave, para mandarla por WhatsApp. Queda en la bitácora."""
    if not acceso.activo:
        raise ErrorPortal("Ese acceso está revocado: vuelve a invitarlo.")
    token = llave_de(acceso, MOTIVO_INVITACION, _ip(request))
    registrar_evento(acceso, "copiado", f"por {getattr(actor, 'email', '') or 'el sistema'}", request)
    return url_de_enlace(token)


def cambiar_enlace(acceso: AccesoCliente, actor, request=None) -> ResultadoInvitacion:
    """Llave nueva (la anterior deja de abrir) y se la manda por correo. Para
    cuando la llave se filtró. La sesión abierta NO se cierra: para eso está
    revocar."""
    if not acceso.activo:
        raise ErrorPortal("Ese acceso está revocado: vuelve a invitarlo.")
    token = _crear_enlace(acceso, MOTIVO_INVITACION, _ip(request))
    registrar_evento(acceso, "cambiado", f"por {getattr(actor, 'email', '') or 'el sistema'}", request)
    _emitir("portal.enlace_cambiado", acceso, actor)
    res = _mandar_correo(acceso, token, invitacion=False, cambiado=True)
    return ResultadoInvitacion(acceso=acceso, correo_ok=res.ok, error_correo=res.error)


def marcar_entrada(acceso: AccesoCliente, request=None, via: str = "") -> None:
    """Para las entradas que no gastan enlace (Google)."""
    acceso.ultima_entrada_en = timezone.now()
    acceso.save(update_fields=["ultima_entrada_en", "actualizado_en"])
    registrar_evento(acceso, "entrada", via, request)


def abrir_sesion(request, acceso: AccesoCliente) -> None:
    """Sesión nueva (llave nueva: nada de fijación de sesión) atada a la
    generación vigente del acceso."""
    request.session.flush()
    request.session[SESION_ACCESO] = acceso.pk
    request.session[SESION_GENERACION] = acceso.generacion
    request.session.set_expiry(DURACION_SESION_SEG)


def cerrar_sesion(request) -> None:
    request.session.flush()


def acceso_de_sesion(session) -> AccesoCliente | None:
    """El acceso vivo de esta sesión, o None. Se pregunta en CADA petición: es lo
    que hace que revocar corte una sesión abierta."""
    pk = session.get(SESION_ACCESO)
    if not pk:
        return None
    acceso = (AccesoCliente.objects.filter(pk=pk).select_related("cliente").first())
    if (acceso is None or not acceso.activo or not acceso.cliente.activo
            or acceso.generacion != session.get(SESION_GENERACION)):
        return None
    return acceso


__all__ = [
    "CANJE_ANULADO",
    "CANJE_CORREO",
    "CANJE_EXPIRADO",
    "CANJE_INVALIDO",
    "CANJE_SIN_ACCESO",
    "DURACION_SESION_SEG",
    "ErrorPortal",
    "Invitable",
    "ResultadoInvitacion",
    "abrir_sesion",
    "acceso_activo_por_email",
    "acceso_de_sesion",
    "accesos_de",
    "buscar_enlace",
    "cambiar_enlace",
    "canjear",
    "cerrar_sesion",
    "correo_coincide",
    "enlace_para_copiar",
    "hash_token",
    "invitables_de",
    "invitar",
    "llave_de",
    "llave_viva",
    "marcar_entrada",
    "pedir_enlace",
    "registrar_evento",
    "revocar",
    "url_de_enlace",
    "url_recepcion",
]
