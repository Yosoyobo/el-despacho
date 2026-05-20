"""Push de mensaje de chat vía El Interfón.

Itera participantes de la conversación (sin contar al autor), envía
push categoría `recados_chat`. Si El Interfón no está configurado,
silencioso.
"""

from __future__ import annotations

import logging

from lib.interfono import enviar_a_usuario

logger = logging.getLogger(__name__)

CATEGORIA = "recados_chat"
LIMITE_CUERPO = 120


def push_mensaje(mensaje_id: int) -> dict[str, int]:
    from cuentas.models.usuario import Usuario

    from .models import Mensaje

    resumen = {"enviados": 0, "saltados": 0}
    try:
        m = Mensaje.objects.select_related("autor", "conversacion").get(pk=mensaje_id)
    except Mensaje.DoesNotExist:
        return resumen

    audiencia_ids = set(m.conversacion.participantes.values_list("id", flat=True))
    if m.autor_id:
        audiencia_ids.discard(m.autor_id)
    if not audiencia_ids:
        return resumen

    nombre_autor = (
        m.autor.get_short_name() if m.autor else "El Despacho"
    ) or (getattr(m.autor, "email", None) or "El Despacho")
    if m.conversacion.tipo == "grupo":
        titulo = f"{nombre_autor} en {m.conversacion.nombre or 'Grupo'}"
    else:
        titulo = f"Mensaje de {nombre_autor}"
    cuerpo = (m.cuerpo or "").strip()[:LIMITE_CUERPO]
    url = f"/recados/c/{m.conversacion_id}/"
    tag = f"chat-{m.conversacion_id}"

    for u in Usuario.objects.filter(id__in=audiencia_ids, is_active=True):
        try:
            enviar_a_usuario(u, titulo=titulo, cuerpo=cuerpo, url=url, tag=tag, categoria=CATEGORIA)
            resumen["enviados"] += 1
        except Exception:
            logger.exception("recados_chat.push: falló envío a usuario_id=%s", u.pk)
            resumen["saltados"] += 1
    return resumen
