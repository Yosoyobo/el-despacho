"""Lógica de chat (Conversacion/Mensaje). Separado de `services.py` para
no contaminar el módulo legacy con la nueva forma de mensajería.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Max, OuterRef, Q, Subquery
from django.utils import timezone

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Conversacion, Mensaje, MensajeLectura

logger = logging.getLogger(__name__)
Usuario = get_user_model()


# ── Crear / obtener conversación ─────────────────────────────────────────────


def obtener_o_crear_directa(usuario_a, usuario_b) -> Conversacion:
    """Devuelve la conversación 1:1 entre dos usuarios. Crea si no existe.
    Idempotente vía `clave_directa` única."""
    if usuario_a.pk == usuario_b.pk:
        raise ValueError("No puedes abrir conversación contigo mismo.")
    clave = Conversacion.clave_para_par(usuario_a.pk, usuario_b.pk)
    conv = Conversacion.objects.filter(clave_directa=clave).first()
    if conv:
        return conv
    with transaction.atomic():
        conv = Conversacion.objects.create(
            tipo=Conversacion.DIRECTA,
            clave_directa=clave,
            creada_por=usuario_a,
        )
        conv.participantes.set([usuario_a, usuario_b])
    return conv


def crear_grupo(*, autor, nombre: str, participantes_ids: Iterable[int]) -> Conversacion:
    """Crea un grupo. `participantes_ids` debe incluir al autor (si no, se agrega)."""
    ids = set(int(i) for i in participantes_ids) | {autor.pk}
    if len(ids) < 2:
        raise ValueError("Un grupo requiere al menos 2 participantes.")
    with transaction.atomic():
        conv = Conversacion.objects.create(
            tipo=Conversacion.GRUPO,
            nombre=(nombre or "").strip()[:120],
            creada_por=autor,
        )
        conv.participantes.set(Usuario.objects.filter(pk__in=ids))
    return conv


# ── Enviar mensaje ───────────────────────────────────────────────────────────


def enviar_mensaje(*, conversacion: Conversacion, autor, cuerpo: str) -> Mensaje:
    cuerpo = (cuerpo or "").strip()
    if not cuerpo:
        raise ValueError("Mensaje vacío.")
    if not conversacion.participantes.filter(pk=autor.pk).exists():
        raise PermissionError("No eres participante de esta conversación.")

    with transaction.atomic():
        m = Mensaje.objects.create(conversacion=conversacion, autor=autor, cuerpo=cuerpo)
        Conversacion.objects.filter(pk=conversacion.pk).update(ultima_actividad=timezone.now())
        # Autor lee su propio mensaje automáticamente.
        MensajeLectura.objects.update_or_create(
            usuario=autor, conversacion=conversacion,
            defaults={"ultimo_mensaje": m},
        )

    transaction.on_commit(lambda: _emitir_creado(m))
    transaction.on_commit(lambda: _disparar_push(m.pk))
    return m


def marcar_leido_hasta(*, usuario, conversacion: Conversacion, mensaje_id: int | None = None) -> None:
    """Marca como leído hasta el mensaje dado (o el último si es None)."""
    if mensaje_id is None:
        ultimo = conversacion.mensajes.order_by("-id").first()
        if ultimo is None:
            return
        mensaje_id = ultimo.pk
    MensajeLectura.objects.update_or_create(
        usuario=usuario, conversacion=conversacion,
        defaults={"ultimo_mensaje_id": mensaje_id},
    )


# ── Bandeja: lista de conversaciones con counters ────────────────────────────


def mis_conversaciones(usuario):
    """Conversaciones del usuario con: último mensaje, no_leidos, nombre
    resuelto (para directas, el otro participante)."""
    convs = (
        Conversacion.objects
        .filter(participantes=usuario)
        .annotate(_ultima_id=Max("mensajes__id"))
        .order_by("-ultima_actividad")
        .prefetch_related("participantes")
    )

    # Mapa lectura → último_mensaje_id leído por este usuario.
    leidos = dict(
        MensajeLectura.objects
        .filter(usuario=usuario, conversacion__in=convs)
        .values_list("conversacion_id", "ultimo_mensaje_id")
    )

    salida = []
    for c in convs:
        ultimo_leido = leidos.get(c.pk) or 0
        no_leidos = (
            Mensaje.objects.filter(conversacion=c)
            .filter(~Q(autor=usuario), id__gt=ultimo_leido).count()
            if c._ultima_id else 0
        )
        ultimo_msg = c.mensajes.order_by("-id").first() if c._ultima_id else None
        if c.tipo == Conversacion.DIRECTA:
            otro = next((p for p in c.participantes.all() if p.pk != usuario.pk), None)
            titulo = (otro.nombre_completo or otro.email) if otro else "(sin participante)"
        else:
            titulo = c.nombre or f"Grupo #{c.pk}"
        salida.append({
            "conversacion": c,
            "titulo": titulo,
            "ultimo_mensaje": ultimo_msg,
            "no_leidos": no_leidos,
        })
    return salida


def total_no_leidos(usuario) -> int:
    """Total de mensajes no leídos del usuario (excluye los suyos). Usado
    en el badge del sidebar."""
    # Sub-query: último mensaje leído por el usuario en cada conversación.
    leidos = MensajeLectura.objects.filter(
        usuario=usuario, conversacion=OuterRef("conversacion"),
    ).values("ultimo_mensaje_id")[:1]
    return (
        Mensaje.objects
        .filter(conversacion__participantes=usuario)
        .exclude(autor=usuario)
        .annotate(_ultimo_leido=Subquery(leidos))
        .filter(Q(_ultimo_leido__isnull=True) | Q(id__gt=F("_ultimo_leido")))
        .count()
    )


# ── Push + Portavoz ──────────────────────────────────────────────────────────


def _emitir_creado(mensaje: Mensaje) -> None:
    try:
        emitir(EventoPortavoz(
            tipo="recados_chat.mensaje_enviado",
            actor_id=getattr(mensaje.autor, "pk", None),
            actor_email=getattr(mensaje.autor, "email", None),
            payload={
                "conversacion_id": mensaje.conversacion_id,
                "mensaje_id": mensaje.pk,
                "tipo_conv": mensaje.conversacion.tipo,
            },
        ))
    except Exception:
        logger.exception("recados_chat: emitir falló")


def _disparar_push(mensaje_id: int) -> None:
    try:
        from . import handlers_chat
        handlers_chat.push_mensaje(mensaje_id)
    except Exception:
        logger.exception("recados_chat: push handler falló mensaje_id=%s", mensaje_id)
