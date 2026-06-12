"""Push automáticos del Interfón cuando ocurren eventos de negocio (S2b.4).

Cada función `notificar_*` se llama desde la vista que crea/modifica el modelo.
Internamente usa `transaction.on_commit` para no despachar push si la
transacción hace rollback. Respeta opt-out por categoría
(`PreferenciaCategoriaPush`) y persiste historial (`InterfonoEntrega`) gracias
a `lib.interfono.enviar_a_usuario` (S2b.1.5).

Categorías nuevas en S2b.4:
- `buzon` — admin/dueno reciben nuevos mensajes del Buzón
- `proyectos` — asignados + creador reciben creación / cambio de estado
- `tareas` — el `asignada_a` recibe al ser asignado

Las categorías se exponen en `/perfil/notificaciones/` como checkboxes
opt-out (la fila se crea SOLO cuando el usuario desactiva).
"""

from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def _admins_activos():
    # V6 Bloque 10: usuarios_con_rol reconoce rol primario + roles
    # personalizados (roles_extra) y ya filtra is_active=True.
    from lib.permisos import usuarios_con_rol
    return usuarios_con_rol("super_admin", "dueno")


def _cobranza_activos():
    """Usuarios que reciben alertas de cobranza: admins + contadores activos."""
    # V6 Bloque 10: usuarios_con_rol (rol primario + roles_extra, is_active).
    from lib.permisos import usuarios_con_rol
    return usuarios_con_rol("super_admin", "dueno", "contador")


def _enviar(usuario, titulo: str, cuerpo: str, *, url: str, tag: str, categoria: str,
            origen_modulo: str, origen_id: int) -> None:
    from lib.interfono import enviar_a_usuario
    try:
        enviar_a_usuario(
            usuario, titulo=titulo, cuerpo=cuerpo, url=url, tag=tag,
            categoria=categoria, origen_modulo=origen_modulo, origen_id=origen_id,
        )
    except Exception:  # noqa: BLE001 — un push roto no debe romper la vista
        logger.exception("push automatico %s falló para usuario=%s", categoria, usuario.pk)


# ── Buzón ──


def notificar_buzon_nuevo(mensaje, autor) -> None:
    """Push a admins activos cuando un empleado crea un mensaje."""
    def _hacer():
        for admin in _admins_activos():
            if admin.pk == autor.pk:
                continue
            _enviar(
                admin,
                titulo=f"📨 Buzón: {mensaje.get_tipo_display() if hasattr(mensaje, 'get_tipo_display') else mensaje.tipo}",
                cuerpo=f"{autor.nombre_completo}: {mensaje.asunto[:120]}",
                url=f"/buzon/{mensaje.pk}/",
                tag=f"buzon-{mensaje.pk}",
                categoria="buzon",
                origen_modulo="buzon",
                origen_id=mensaje.pk,
            )
    transaction.on_commit(_hacer)


def notificar_buzon_estado(mensaje, actor) -> None:
    """S-LC-Buzon-V2: dispara la acción automática configurada para el estado
    actual del mensaje (notificar_autor / notificar_admins). Se llama tras un
    cambio EXPLÍCITO de estado por un admin. Best-effort."""
    from buzon.estados import accion_de
    accion = accion_de(mensaje.estado)
    if accion == "notificar_autor":
        def _hacer():
            _enviar(
                mensaje.autor,
                titulo=f"📨 Tu mensaje del Buzón: {mensaje.get_estado_display()}",
                cuerpo=mensaje.asunto[:120],
                url=f"/buzon/{mensaje.pk}/",
                tag=f"buzon-{mensaje.pk}",
                categoria="buzon",
                origen_modulo="buzon",
                origen_id=mensaje.pk,
            )
        transaction.on_commit(_hacer)
    elif accion == "notificar_admins":
        def _hacer():
            for admin in _admins_activos():
                if actor and admin.pk == actor.pk:
                    continue
                _enviar(
                    admin,
                    titulo=f"📨 Buzón #{mensaje.pk}: {mensaje.get_estado_display()}",
                    cuerpo=mensaje.asunto[:120],
                    url=f"/buzon/{mensaje.pk}/",
                    tag=f"buzon-{mensaje.pk}",
                    categoria="buzon",
                    origen_modulo="buzon",
                    origen_id=mensaje.pk,
                )
        transaction.on_commit(_hacer)


def notificar_buzon_comentario(mensaje, autor_comentario) -> None:
    """C5d: avisa al otro lado del ticket. Si comentó el autor del mensaje →
    avisa a los admins; si comentó un admin → avisa al autor. Best-effort."""
    es_autor_del_mensaje = mensaje.autor_id == getattr(autor_comentario, "pk", None)

    def _hacer():
        if es_autor_del_mensaje:
            destinatarios = list(_admins_activos())
        else:
            destinatarios = [mensaje.autor] if mensaje.autor_id else []
        for u in destinatarios:
            if u.pk == autor_comentario.pk:
                continue
            _enviar(
                u,
                titulo=f"💬 Respuesta en Buzón #{mensaje.pk}",
                cuerpo=f"{autor_comentario.nombre_completo}: {mensaje.asunto[:100]}",
                url=f"/buzon/{mensaje.pk}/",
                tag=f"buzon-{mensaje.pk}",
                categoria="buzon",
                origen_modulo="buzon",
                origen_id=mensaje.pk,
            )
    transaction.on_commit(_hacer)


# ── Proyectos ──


def notificar_proyecto_creado(proyecto, creador) -> None:
    """Push a admins activos cuando se crea un proyecto."""
    def _hacer():
        for admin in _admins_activos():
            if admin.pk == creador.pk:
                continue
            _enviar(
                admin,
                titulo=f"🆕 Proyecto nuevo: {proyecto.codigo}",
                cuerpo=f"{creador.nombre_completo} creó &laquo;{proyecto.nombre[:80]}&raquo;.",
                url=f"/proyectos/{proyecto.pk}/",
                tag=f"proyecto-creado-{proyecto.pk}",
                categoria="proyectos",
                origen_modulo="proyectos",
                origen_id=proyecto.pk,
            )
    transaction.on_commit(_hacer)


def notificar_proyecto_status_cambiado(proyecto, anterior: str, nuevo: str, actor) -> None:
    """Push a asignados (excluyendo el actor) cuando cambia el estado."""
    def _hacer():
        asignados = (
            proyecto.asignaciones.select_related("usuario")
            .filter(usuario__is_active=True)
        )
        notificados: set[int] = set()
        for asignacion in asignados:
            u = asignacion.usuario
            if not u or u.pk == actor.pk or u.pk in notificados:
                continue
            notificados.add(u.pk)
            _enviar(
                u,
                titulo=f"📐 {proyecto.codigo}: {anterior} → {nuevo}",
                cuerpo=f"Estado del proyecto &laquo;{proyecto.nombre[:80]}&raquo; cambió.",
                url=f"/proyectos/{proyecto.pk}/",
                tag=f"proyecto-status-{proyecto.pk}",
                categoria="proyectos",
                origen_modulo="proyectos",
                origen_id=proyecto.pk,
            )
    transaction.on_commit(_hacer)


# ── Cobranza ──


def notificar_factura_vencida(factura, dias_vencida: int, saldo: float) -> None:
    """Push a admins + contador cuando el cron marca una factura como vencida.

    Categoría `cobranza` — opt-out individual desde /perfil/notificaciones/.
    Idempotente porque el cron sólo dispara una vez por factura (campo
    `vencida_notificada_en`).
    """
    cliente = getattr(factura, "cliente", None)
    cliente_label = getattr(cliente, "razon_social", "") or "cliente"
    titulo = f"💸 Factura vencida: {factura.codigo}"
    cuerpo = (
        f"{cliente_label} · {dias_vencida} día{'s' if dias_vencida != 1 else ''} de retraso"
        f" · saldo ${saldo:,.2f}"
    )
    url = f"/facturacion/{factura.pk}/"
    tag = f"factura-vencida-{factura.pk}"

    def _hacer():
        for u in _cobranza_activos():
            _enviar(
                u, titulo=titulo, cuerpo=cuerpo, url=url, tag=tag,
                categoria="cobranza",
                origen_modulo="facturacion", origen_id=factura.pk,
            )
    transaction.on_commit(_hacer)


# ── Tareas ──


def notificar_tarea_asignada(tarea, actor) -> None:
    """Push al `asignada_a` cuando le crean/asignan una tarea (no a sí mismo)."""
    if not tarea.asignada_a_id or tarea.asignada_a_id == getattr(actor, "pk", None):
        return
    asignada_a = tarea.asignada_a
    if not getattr(asignada_a, "is_active", False):
        return

    def _hacer():
        _enviar(
            asignada_a,
            titulo=f"✅ Nueva tarea: {tarea.titulo[:80]}",
            cuerpo=(f"En {tarea.proyecto.codigo}" if tarea.proyecto_id else "Nueva tarea")
                   + (f" · entrega {tarea.fecha_compromiso}" if tarea.fecha_compromiso else ""),
            url=f"/tareas/{tarea.pk}/",
            tag=f"tarea-asignada-{tarea.pk}",
            categoria="tareas",
            origen_modulo="tareas",
            origen_id=tarea.pk,
        )
    transaction.on_commit(_hacer)


def notificar_tarea_recordatorio(tarea, usuario, *, motivo: str, dias: int = 0) -> None:
    """Recordatorio de tarea por vencer (S-Chalanes-UX #4). Lo invoca el cron
    `recordar_tareas_por_vencer` por cada (tarea, destinatario). Envío directo
    (sin on_commit) — corre fuera de una request. Categoría `tareas` (opt-out).

    `motivo` ∈ {antes, hoy, vencida}; `dias` = días de anticipación (motivo=antes).
    """
    if not usuario or not getattr(usuario, "is_active", False):
        return
    if motivo == "vencida":
        emoji, frase = "🔴", f"vencida hace {abs(dias)} día{'s' if abs(dias) != 1 else ''}" if dias else "vencida"
    elif motivo == "hoy":
        emoji, frase = "⏰", "vence hoy"
    else:
        emoji, frase = "🔔", f"vence en {dias} día{'s' if dias != 1 else ''}"
    proyecto = f" · {tarea.proyecto.codigo}" if tarea.proyecto_id else ""
    _enviar(
        usuario,
        titulo=f"{emoji} Tarea {frase}: {tarea.titulo[:70]}",
        cuerpo=f"Entrega {tarea.fecha_compromiso}{proyecto}",
        url=f"/tareas/{tarea.pk}/",
        tag=f"tarea-recordatorio-{tarea.pk}",
        categoria="tareas",
        origen_modulo="tareas",
        origen_id=tarea.pk,
    )
