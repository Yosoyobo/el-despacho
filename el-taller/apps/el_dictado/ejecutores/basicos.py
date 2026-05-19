"""Ejecutores básicos V1 — proyectos, tareas, recados, buzón.

Cada función toma `(accion: DictadoAccion, usuario: Usuario)` y aplica el
cambio. Lanza `ValueError` si el payload es inválido o la entidad no existe.
"""

from __future__ import annotations

from . import registrar

CAMPOS_PROYECTO_PERMITIDOS = {"estado", "monto_cotizado", "fecha_compromiso", "descripcion"}
CAMPOS_TAREA_PERMITIDOS = {"estado", "prioridad", "asignado_slug", "fecha_compromiso"}


def _resolver_proyecto(slug: str):
    from apps.los_proyectos.models import Proyecto
    if not slug:
        raise ValueError("Falta `proyecto_slug` en payload.")
    proyecto = Proyecto.objects.filter(slug=slug.lower()).first()
    if not proyecto:
        raise ValueError(f"Proyecto `{slug}` no encontrado.")
    return proyecto


def _resolver_usuario(slug: str):
    from cuentas.models.usuario import Usuario
    u = Usuario.objects.filter(slug=slug.lower(), is_active=True).first()
    if not u:
        raise ValueError(f"Usuario `@{slug}` no encontrado.")
    return u


@registrar("actualizar_proyecto")
def actualizar_proyecto(accion, usuario):
    proyecto = _resolver_proyecto(accion.payload.get("proyecto_slug", ""))
    campos = accion.payload.get("campos") or {}
    if not isinstance(campos, dict):
        raise ValueError("Campo `campos` debe ser dict.")
    aplicado = []
    for k, v in campos.items():
        if k not in CAMPOS_PROYECTO_PERMITIDOS:
            continue
        setattr(proyecto, k, v)
        aplicado.append(k)
    if not aplicado:
        raise ValueError("Sin campos válidos para actualizar.")
    proyecto.save(update_fields=[*aplicado, "actualizado_en"])
    accion.entidad_tipo = "proyecto"
    accion.entidad_id = proyecto.pk


@registrar("asignar_usuario_proyecto")
def asignar_usuario_proyecto(accion, usuario):
    proyecto = _resolver_proyecto(accion.payload.get("proyecto_slug", ""))
    u = _resolver_usuario(accion.payload.get("usuario_slug", ""))
    rol_en_proyecto = (accion.payload.get("rol_en_proyecto") or "disenador").lower()
    if rol_en_proyecto not in {"lider", "disenador", "produccion", "revisor"}:
        rol_en_proyecto = "disenador"
    from apps.los_proyectos.models import ProyectoAsignacion
    ProyectoAsignacion.objects.update_or_create(
        proyecto=proyecto, usuario=u,
        defaults={"rol_en_proyecto": rol_en_proyecto},
    )
    accion.entidad_tipo = "asignacion"
    accion.entidad_id = proyecto.pk


@registrar("crear_tarea")
def crear_tarea(accion, usuario):
    proyecto = _resolver_proyecto(accion.payload.get("proyecto_slug", ""))
    titulo = (accion.payload.get("titulo") or "").strip()
    if not titulo:
        raise ValueError("Falta `titulo` en payload.")
    asignado_slug = (accion.payload.get("asignado_slug") or "").strip()
    asignada_a = _resolver_usuario(asignado_slug) if asignado_slug else None
    fecha = accion.payload.get("fecha_compromiso") or None
    prioridad = (accion.payload.get("prioridad") or "media").lower()
    if prioridad not in {"baja", "media", "alta"}:
        prioridad = "media"
    from apps.el_pizarron.models import Tarea
    t = Tarea.objects.create(
        proyecto=proyecto, titulo=titulo[:200], asignada_a=asignada_a,
        fecha_compromiso=fecha, prioridad=prioridad, creado_por=usuario,
    )
    accion.entidad_tipo = "tarea"
    accion.entidad_id = t.pk

    # Dispara push automático (S2b.4) si hay asignado.
    if asignada_a:
        from apps.taller_home.push_handlers import notificar_tarea_asignada
        notificar_tarea_asignada(t, usuario)


@registrar("actualizar_tarea")
def actualizar_tarea(accion, usuario):
    from apps.el_pizarron.models import Tarea
    tarea_id = accion.payload.get("tarea_id")
    if not tarea_id:
        raise ValueError("Falta `tarea_id`.")
    tarea = Tarea.objects.filter(pk=tarea_id).first()
    if not tarea:
        raise ValueError(f"Tarea {tarea_id} no encontrada.")
    campos = accion.payload.get("campos") or {}
    aplicado: list[str] = []
    for k, v in campos.items():
        if k not in CAMPOS_TAREA_PERMITIDOS:
            continue
        if k == "asignado_slug":
            tarea.asignada_a = _resolver_usuario(v)
            aplicado.append("asignada_a")
        else:
            setattr(tarea, k, v)
            aplicado.append(k)
    if not aplicado:
        raise ValueError("Sin campos válidos para actualizar.")
    tarea.save(update_fields=aplicado)
    accion.entidad_tipo = "tarea"
    accion.entidad_id = tarea.pk


@registrar("crear_recado")
def crear_recado_ejec(accion, usuario):
    from apps.recados.services import crear_recado
    destinatarios = accion.payload.get("destinatarios_slugs") or []
    cuerpo = (accion.payload.get("cuerpo") or "").strip()
    if not (destinatarios and cuerpo):
        raise ValueError("Recado necesita `destinatarios_slugs` + `cuerpo`.")
    # Servicio existente: crear_recado(autor, cuerpo, destinatarios_usuarios=[...], destinatarios_grupos=[...])
    from cuentas.models.usuario import Usuario
    ids = set(Usuario.objects.filter(
        slug__in=[s.lower() for s in destinatarios], is_active=True,
    ).values_list("pk", flat=True))
    if not ids:
        raise ValueError("Ningún destinatario válido.")
    recado = crear_recado(autor=usuario, cuerpo=cuerpo, destinatarios_ids=ids)
    accion.entidad_tipo = "recado"
    accion.entidad_id = recado.pk


@registrar("crear_mensaje_buzon")
def crear_mensaje_buzon_ejec(accion, usuario):
    from buzon.models import MensajeBuzon
    tipo = (accion.payload.get("tipo") or "otro").lower()
    if tipo not in {"sugerencia", "problema", "otro"}:
        tipo = "otro"
    asunto = (accion.payload.get("asunto") or "").strip()
    cuerpo = (accion.payload.get("cuerpo") or "").strip()
    if not (asunto and cuerpo):
        raise ValueError("Mensaje del Buzón necesita `asunto` + `cuerpo`.")
    msg = MensajeBuzon.objects.create(autor=usuario, tipo=tipo, asunto=asunto[:200], cuerpo=cuerpo)
    accion.entidad_tipo = "buzon"
    accion.entidad_id = msg.pk
    # Push automático S2b.4
    from apps.taller_home.push_handlers import notificar_buzon_nuevo
    notificar_buzon_nuevo(msg, usuario)


@registrar("registrar_egreso")
def registrar_egreso_stub(accion, usuario):
    """STUB — `registrar_egreso` se activa en S2b.3 — La Tesorería."""
    raise ValueError(
        "El módulo La Tesorería llega en S2b.3. Esta acción quedó propuesta "
        "pero no se ejecuta. Mientras tanto, registra el egreso manualmente."
    )
