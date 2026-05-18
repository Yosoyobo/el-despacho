"""Servicio: persistir referencias para un contenedor + emitir evento de menciones.

Uso:
    from referencias.services import sincronizar_referencias

    sincronizar_referencias(
        texto=recado.cuerpo,
        contenedor_tipo='recado',
        contenedor_id=recado.pk,
        autor=request.user,
    )
"""

from __future__ import annotations

from .parser import extraer_tokens
from .resolver import resolver_tokens


def sincronizar_referencias(
    *,
    texto: str,
    contenedor_tipo: str,
    contenedor_id: int,
    autor=None,
) -> dict:
    """Reemplaza referencias del contenedor con las detectadas en el texto.

    Devuelve dict con `tokens`, `creadas`, `usuarios_mencionados` (excluye autor).
    Si el resultado incluye usuarios, emite `referencia.usuario_mencionado` por
    cada usuario único (dedup).
    """
    from .models import Referencia

    tokens = extraer_tokens(texto or "")
    resueltos = resolver_tokens(tokens) if tokens else {}

    # Borra referencias previas del contenedor.
    Referencia.objects.filter(
        contenedor_tipo=contenedor_tipo, contenedor_id=contenedor_id
    ).delete()

    creadas = []
    usuarios_mencionados_ids: set[int] = set()
    autor_id = getattr(autor, "pk", None)

    for t in tokens:
        entidad = resueltos.get((t.tipo, t.slug))
        if entidad is None:
            # Referencia rota — NO persistimos fila (la regla del CHECK exige FK).
            # El render se encarga de mostrar el token con line-through al releer el texto.
            continue
        kwargs = {
            "contenedor_tipo": contenedor_tipo,
            "contenedor_id": contenedor_id,
            "tipo": t.tipo,
            "token_original": t.token_original,
            "posicion_inicio": t.inicio,
            "posicion_fin": t.fin,
        }
        if t.tipo == "usuario":
            kwargs["usuario"] = entidad
            if entidad.pk != autor_id:
                usuarios_mencionados_ids.add(entidad.pk)
        elif t.tipo == "proyecto":
            kwargs["proyecto"] = entidad
        elif t.tipo == "cliente":
            kwargs["cliente"] = entidad
        creadas.append(Referencia.objects.create(**kwargs))

    # Emitir un evento por cada usuario único mencionado.
    if usuarios_mencionados_ids:
        try:
            from lib.portavoz import emitir
            for uid in usuarios_mencionados_ids:
                emitir({
                    "tipo": "referencia.usuario_mencionado",
                    "usuario_id": uid,
                    "autor_id": autor_id,
                    "contenedor_tipo": contenedor_tipo,
                    "contenedor_id": contenedor_id,
                })
        except Exception:
            # El Portavoz no debe romper el flujo del caller — si está caído
            # los eventos se pierden silenciosamente (su propio worker maneja DLQ).
            pass

    return {
        "tokens": tokens,
        "creadas": creadas,
        "usuarios_mencionados": list(usuarios_mencionados_ids),
    }
