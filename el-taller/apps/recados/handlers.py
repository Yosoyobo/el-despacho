"""Push de `recado.creado` vía El Interfón.

Diseño: el servicio `crear_recado` llama a `push_recado_creado(recado_id)`
en `transaction.on_commit`, fuera del atomic. El handler:

1. Reúne destinatarios + mencionados (@) en un set (dedup).
2. Excluye al autor.
3. Por cada usuario activo, llama a `lib.interfono.enviar_a_usuario(...,
   categoria='recados')`. La función ya filtra por preferencia opt-out.

Si El Interfón no está configurado, las llamadas retornan silenciosas — el
flujo del recado no se ve afectado.
"""

from __future__ import annotations

import logging

from lib.interfono import enviar_a_usuario  # importado a módulo para tests

logger = logging.getLogger(__name__)

CATEGORIA = "recados"
LIMITE_CUERPO = 120


def _audiencia(recado) -> set[int]:
    ids = set(recado.destinatarios.values_list("usuario_id", flat=True))
    try:
        from cuentas.models.usuario import Usuario
        from referencias.parser import extraer_tokens
        slugs = {t.slug for t in extraer_tokens(recado.cuerpo or "") if t.tipo == "usuario"}
        if slugs:
            mencionados = Usuario.objects.filter(slug__in=slugs).values_list("id", flat=True)
            ids.update(mencionados)
    except Exception:
        logger.exception("recados.push: fallo al parsear menciones")
    if recado.autor_id:
        ids.discard(recado.autor_id)
    return ids


def push_recado_creado(recado_id: int) -> dict[str, int]:
    """Itera audiencia y envía push categoría 'recados'.

    Retorna `{"enviados": n, "saltados": k}` (útil para tests).
    """
    from cuentas.models.usuario import Usuario

    from .models import Recado

    resumen = {"enviados": 0, "saltados": 0}
    try:
        recado = Recado.objects.select_related("autor").get(pk=recado_id)
    except Recado.DoesNotExist:
        return resumen

    ids = _audiencia(recado)
    if not ids:
        return resumen

    if recado.autor:
        nombre_autor = recado.autor.get_short_name() or recado.autor.email
    else:
        nombre_autor = "El Despacho"
    cuerpo_push = (recado.cuerpo_para_push or "").strip()[:LIMITE_CUERPO]
    titulo = f"Recado de {nombre_autor}"
    url = f"/recados/{recado.pk}/"
    tag = f"recado-{recado.pk}"

    for u in Usuario.objects.filter(id__in=ids, is_active=True):
        try:
            enviar_a_usuario(u, titulo=titulo, cuerpo=cuerpo_push, url=url, tag=tag, categoria=CATEGORIA)
            resumen["enviados"] += 1
        except Exception:
            logger.exception("recados.push: falló envío a usuario_id=%s", u.pk)
            resumen["saltados"] += 1
    return resumen
