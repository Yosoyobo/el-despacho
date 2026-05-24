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
    from cuentas.models.usuario import Usuario
    return Usuario.objects.filter(is_active=True, rol__in=("super_admin", "dueno"))


def _cobranza_activos():
    """Usuarios que reciben alertas de cobranza: admins + contadores activos."""
    from cuentas.models.usuario import Usuario
    return Usuario.objects.filter(
        is_active=True, rol__in=("super_admin", "dueno", "contador")
    )


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
            url=f"/proyectos/{tarea.proyecto_id}/" if tarea.proyecto_id else "/",
            tag=f"tarea-asignada-{tarea.pk}",
            categoria="tareas",
            origen_modulo="tareas",
            origen_id=tarea.pk,
        )
    transaction.on_commit(_hacer)
