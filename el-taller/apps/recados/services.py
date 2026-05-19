"""Servicios de Los Recados (DOC_03).

- `resolver_destinatarios`: une usuarios directos + grupos estáticos +
  grupos dinámicos `equipo-de-#proyecto-X`, deduplica y excluye al autor.
- `crear_recado`: persiste Recado + RecadoDestinatario + sincroniza
  referencias + emite evento `recado.creado` + dispara push (vía handler).
- `editar_recado`: snapshot a `RecadoVersion`, incrementa `version_actual`,
  re-sincroniza referencias, emite `recado.editado`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Resolución de destinatarios ──────────────────────────────────────────────

PREFIJO_DINAMICO = "equipo-de-#"


def _usuarios_por_rol(roles: list[str]) -> set[int]:
    from cuentas.models.usuario import Usuario
    qs = Usuario.objects.filter(is_active=True)
    if roles:
        qs = qs.filter(rol__in=roles)
    return set(qs.values_list("id", flat=True))


def expandir_grupo_estatico(slug: str) -> set[int]:
    """Devuelve los IDs de usuarios del grupo estático/por rol con ese slug."""
    from .models import RecadoGrupo
    try:
        g = RecadoGrupo.objects.get(slug=slug)
    except RecadoGrupo.DoesNotExist:
        return set()
    if g.tipo == "rol":
        return _usuarios_por_rol(list(g.roles or []))
    return set()


def expandir_grupo_dinamico(slug: str) -> set[int]:
    """`equipo-de-#PRY-000123` o `equipo-de-#nombre-slug` → IDs asignados."""
    if not slug.startswith(PREFIJO_DINAMICO):
        return set()
    ref = slug[len(PREFIJO_DINAMICO):].strip()
    if not ref:
        return set()

    try:
        from apps.los_proyectos.models import Proyecto
    except Exception:
        return set()

    proyecto = (
        Proyecto.objects.filter(slug__iexact=ref).first()
        or Proyecto.objects.filter(codigo__iexact=ref).first()
    )
    if proyecto is None:
        return set()
    return set(
        proyecto.asignaciones.filter(usuario__is_active=True)
        .values_list("usuario_id", flat=True)
    )


def resolver_destinatarios(
    *,
    autor,
    usuarios_ids: Iterable[int] = (),
    grupos: Iterable[str] = (),
    dinamicos: Iterable[str] = (),
) -> set[int]:
    """Une, deduplica y excluye al autor + usuarios inactivos.

    Devuelve un set de IDs listos para persistir como `RecadoDestinatario`.
    """
    from cuentas.models.usuario import Usuario

    ids: set[int] = set()

    if usuarios_ids:
        activos = Usuario.objects.filter(
            id__in=list(usuarios_ids), is_active=True
        ).values_list("id", flat=True)
        ids.update(activos)

    for slug in grupos or ():
        ids.update(expandir_grupo_estatico(slug))

    for slug in dinamicos or ():
        ids.update(expandir_grupo_dinamico(slug))

    if autor and getattr(autor, "pk", None):
        ids.discard(autor.pk)

    return ids


# ── Creación / edición ───────────────────────────────────────────────────────


@transaction.atomic
def crear_recado(*, autor, cuerpo: str, destinatarios_ids: set[int]):
    """Persiste Recado + RecadoDestinatario, sincroniza referencias, emite
    eventos y dispara push. Retorna la instancia `Recado`.
    """
    from .models import Recado, RecadoDestinatario

    recado = Recado.objects.create(autor=autor, cuerpo=cuerpo)

    RecadoDestinatario.objects.bulk_create(
        [RecadoDestinatario(recado=recado, usuario_id=uid) for uid in destinatarios_ids],
        ignore_conflicts=True,
    )

    # Referencias (@/#/$). Reusa Pre-S2b.1.
    try:
        from referencias.services import sincronizar_referencias
        sincronizar_referencias(
            texto=cuerpo,
            contenedor_tipo="recado",
            contenedor_id=recado.pk,
            autor=autor,
        )
    except Exception:
        logger.exception("recados: fallo al sincronizar referencias")

    _emitir_creado(recado, autor, destinatarios_ids)
    # Push fuera del atomic para no demorar el commit.
    transaction.on_commit(lambda: _disparar_push_creado(recado.pk))
    return recado


@transaction.atomic
def editar_recado(*, recado, editor, nuevo_cuerpo: str):
    """Snapshot a RecadoVersion, incrementa version_actual, marca editado,
    re-sincroniza referencias y emite `recado.editado`.
    """
    from .models import RecadoVersion

    RecadoVersion.objects.create(
        recado=recado,
        version=recado.version_actual,
        cuerpo=recado.cuerpo,
        editado_por=editor,
        editado_en=timezone.now(),
    )

    recado.cuerpo = nuevo_cuerpo
    recado.editado = True
    recado.editado_en = timezone.now()
    recado.version_actual += 1
    recado.save(update_fields=["cuerpo", "editado", "editado_en", "version_actual"])

    try:
        from referencias.services import sincronizar_referencias
        sincronizar_referencias(
            texto=nuevo_cuerpo,
            contenedor_tipo="recado",
            contenedor_id=recado.pk,
            autor=editor,
        )
    except Exception:
        logger.exception("recados: fallo al sincronizar referencias en edición")

    _emitir_editado(recado, editor)
    return recado


# ── Eventos + push ───────────────────────────────────────────────────────────


def _emitir_creado(recado, autor, destinatarios_ids) -> None:
    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz
    try:
        emitir(EventoPortavoz(
            tipo="recado.creado",
            actor_id=getattr(autor, "pk", None),
            actor_email=getattr(autor, "email", None),
            payload={
                "recado_id": recado.pk,
                "destinatarios_ids": sorted(int(i) for i in destinatarios_ids),
                "tiene_adjuntos": False,
            },
        ))
    except Exception:
        logger.exception("recados: emitir recado.creado falló")


def _emitir_editado(recado, editor) -> None:
    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz
    try:
        emitir(EventoPortavoz(
            tipo="recado.editado",
            actor_id=getattr(editor, "pk", None),
            actor_email=getattr(editor, "email", None),
            payload={
                "recado_id": recado.pk,
                "version_anterior": recado.version_actual - 1,
                "version_nueva": recado.version_actual,
            },
        ))
    except Exception:
        logger.exception("recados: emitir recado.editado falló")


def emitir_leido(recado, lector) -> None:
    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz
    try:
        emitir(EventoPortavoz(
            tipo="recado.leido",
            actor_id=getattr(lector, "pk", None),
            actor_email=getattr(lector, "email", None),
            payload={"recado_id": recado.pk},
        ))
    except Exception:
        logger.exception("recados: emitir recado.leido falló")


def _disparar_push_creado(recado_id: int) -> None:
    """Llama al handler de push (separado para tests + mocks)."""
    from . import handlers
    try:
        handlers.push_recado_creado(recado_id)
    except Exception:
        logger.exception("recados: push handler falló recado_id=%s", recado_id)


# ── Visibilidad / acceso al detalle ──────────────────────────────────────────


def puede_ver_recado(usuario, recado) -> bool:
    """True si es autor, destinatario o mencionado por `@` en el cuerpo."""
    if not usuario or not getattr(usuario, "pk", None):
        return False
    if recado.autor_id == usuario.pk:
        return True
    if recado.destinatarios.filter(usuario_id=usuario.pk).exists():
        return True
    # Mencionado por `@`
    try:
        from referencias.parser import extraer_tokens
        slugs = {t.slug for t in extraer_tokens(recado.cuerpo or "") if t.tipo == "usuario"}
        if slugs:
            from cuentas.models.usuario import Usuario
            return Usuario.objects.filter(pk=usuario.pk, slug__in=slugs).exists()
    except Exception:
        pass
    return False
