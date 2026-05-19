"""El Interfono — web-push VAPID con pywebpush.

Lee las llaves VAPID de Los Ajustes (cifradas con La Bóveda). Si no están
configuradas, las funciones de envío retornan rápido sin fallar — el resto
de la app no se ve afectado.

Las suscripciones expiradas (404/410) se marcan `activa=False` automáticamente.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, Literal

logger = logging.getLogger(__name__)

ResultadoEnvio = Literal["ok", "expired", "error", "no_configurado"]
TIMEOUT_PUSH = 5  # segundos por suscripción


class InterfonoConfig:
    """Acceso a la config VAPID guardada en Los Ajustes."""

    @classmethod
    def vapid_public_key(cls) -> str | None:
        from ajustes.models.credencial import Credencial
        return Credencial.obtener("vapid_public_key")

    @classmethod
    def vapid_private_key(cls) -> str | None:
        from ajustes.models.credencial import Credencial
        return Credencial.obtener("vapid_private_key")

    @classmethod
    def vapid_email(cls) -> str:
        from ajustes.models.credencial import Credencial
        valor = Credencial.obtener("vapid_email") or "soporte@bautista.mx"
        if not valor.startswith("mailto:"):
            valor = f"mailto:{valor}"
        return valor

    @classmethod
    def vapid_claims(cls) -> dict[str, str]:
        return {"sub": cls.vapid_email()}

    @classmethod
    def esta_configurado(cls) -> bool:
        return bool(cls.vapid_public_key() and cls.vapid_private_key())


def enviar_a_suscripcion(
    suscripcion,
    titulo: str,
    cuerpo: str,
    url: str = "",
    tag: str = "",
    entrega_id: int | None = None,
) -> ResultadoEnvio:
    """Envía push a UNA suscripción. Marca `activa=False` si el endpoint expiró.

    Si `entrega_id` se pasa, viaja en el payload para que el Service Worker
    pueda marcar la entrega como clickeada al abrir la URL.
    """
    if not InterfonoConfig.esta_configurado():
        return "no_configurado"

    import json

    from pywebpush import WebPushException, webpush

    private_key = InterfonoConfig.vapid_private_key()
    claims = InterfonoConfig.vapid_claims()

    payload = {
        "title": titulo,
        "body": cuerpo,
        "url": url,
        "icon": "/static/branding/Logo_LC-192.png",
        "badge": "/static/branding/Logo_LC-64.png",
    }
    if tag:
        payload["tag"] = tag
    if entrega_id is not None:
        payload["entrega_id"] = entrega_id

    sub_info = {
        "endpoint": suscripcion.endpoint,
        "keys": {"p256dh": suscripcion.p256dh, "auth": suscripcion.auth},
    }

    try:
        webpush(
            subscription_info=sub_info,
            data=json.dumps(payload),
            vapid_private_key=private_key,
            vapid_claims=dict(claims),
            timeout=TIMEOUT_PUSH,
        )
        return "ok"
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            _invalidar_suscripcion(suscripcion)
            return "expired"
        logger.warning("interfono: push falló suscripcion=%s status=%s", suscripcion.pk, status)
        return "error"
    except Exception as exc:
        logger.warning("interfono: push falló suscripcion=%s exc=%r", suscripcion.pk, exc)
        return "error"


def _invalidar_suscripcion(suscripcion) -> None:
    from django.utils import timezone

    suscripcion.activa = False
    suscripcion.desactivada_en = timezone.now()
    suscripcion.save(update_fields=["activa", "desactivada_en"])


def enviar_a_usuario(
    usuario,
    titulo: str,
    cuerpo: str,
    url: str = "",
    tag: str = "",
    categoria: str | None = None,
    origen_modulo: str = "",
    origen_id: int | None = None,
) -> dict[str, int]:
    """Itera todas las suscripciones activas del usuario.

    Persiste SIEMPRE una fila en `InterfonoEntrega` (historial orientado al
    destinatario) antes de despachar. Si la categoría está desactivada o si
    VAPID no está configurado, la entrega queda con el `estado_despacho`
    correspondiente pero sigue visible en `/perfil/notificaciones/` historial.

    Si `categoria` es no-vacío, respeta la preferencia opt-out del usuario
    para esa categoría (S2b.1 — tabla `PreferenciaCategoriaPush`). Default
    es activa: sólo se silencia si hay fila explícita con `activo=False`.
    """
    from interfono.models import InterfonoEntrega, InterfonoSuscripcion, categoria_activa

    totales = {"entregadas": 0, "fallidas": 0, "invalidadas": 0, "entrega_id": 0}

    entrega = InterfonoEntrega.objects.create(
        usuario=usuario,
        titulo=titulo[:200],
        cuerpo=cuerpo,
        url=url[:500],
        tag=tag[:100],
        categoria=(categoria or "")[:40],
        origen_modulo=origen_modulo[:40],
        origen_id=origen_id,
    )
    totales["entrega_id"] = entrega.pk

    if not InterfonoConfig.esta_configurado():
        entrega.estado_despacho = "no_configurado"
        entrega.save(update_fields=["estado_despacho"])
        return totales

    if categoria and not categoria_activa(usuario, categoria):
        entrega.estado_despacho = "silenciada_categoria"
        entrega.save(update_fields=["estado_despacho"])
        return totales

    qs = InterfonoSuscripcion.objects.filter(usuario=usuario, activa=True)
    suscripciones = list(qs)
    if not suscripciones:
        entrega.estado_despacho = "sin_suscripciones"
        entrega.save(update_fields=["estado_despacho"])
        return totales

    for sub in suscripciones:
        resultado = enviar_a_suscripcion(
            sub, titulo, cuerpo, url=url, tag=tag, entrega_id=entrega.pk,
        )
        if resultado == "ok":
            totales["entregadas"] += 1
        elif resultado == "expired":
            totales["invalidadas"] += 1
            totales["fallidas"] += 1
        else:
            totales["fallidas"] += 1

    if totales["entregadas"] > 0:
        entrega.estado_despacho = "entregada"
    else:
        entrega.estado_despacho = "fallida"
    entrega.save(update_fields=["estado_despacho"])
    return totales


def _resolver_usuarios(audiencia: str) -> Iterable[Any]:
    from cuentas.models.usuario import Usuario

    if audiencia == "todos":
        return Usuario.objects.filter(is_active=True)
    if audiencia.startswith("rol:"):
        rol = audiencia.split(":", 1)[1]
        return Usuario.objects.filter(is_active=True, rol=rol)
    if audiencia.startswith("usuario:"):
        try:
            uid = int(audiencia.split(":", 1)[1])
        except ValueError:
            return Usuario.objects.none()
        return Usuario.objects.filter(pk=uid, is_active=True)
    return Usuario.objects.none()


def enviar_a_audiencia(audiencia: str, titulo: str, cuerpo: str, url: str = "", tag: str = "") -> dict[str, int]:
    """audiencia: 'todos' | 'rol:<nombre>' | 'usuario:<id>'."""
    totales = {"entregadas": 0, "fallidas": 0, "invalidadas": 0}
    for usuario in _resolver_usuarios(audiencia):
        parciales = enviar_a_usuario(usuario, titulo, cuerpo, url=url, tag=tag)
        for clave in totales:
            totales[clave] += parciales.get(clave, 0)
    return totales
