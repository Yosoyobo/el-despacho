"""Push automáticos del Interfón cuando ocurren eventos de Tesorería (S2b.3).

Categorías nuevas:
- `tesoreria_reembolso` — notifica al pagador y a contadores que hay un
  reembolso pendiente que registrar/saldar.

Las categorías se exponen en `/perfil/notificaciones/` como checkboxes
opt-out (la fila se crea SOLO cuando el usuario desactiva).
"""

from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def _contadores_y_admins_activos():
    # V6 Bloque 10: usuarios_con_rol reconoce rol primario + roles
    # personalizados (roles_extra) y ya filtra is_active=True.
    from lib.permisos import usuarios_con_rol
    return usuarios_con_rol("super_admin", "dueno", "contador")


def _enviar(usuario, *, titulo: str, cuerpo: str, url: str, tag: str,
            categoria: str, origen_modulo: str, origen_id: int) -> None:
    from lib.interfono import enviar_a_usuario
    try:
        enviar_a_usuario(
            usuario, titulo=titulo, cuerpo=cuerpo, url=url, tag=tag,
            categoria=categoria, origen_modulo=origen_modulo, origen_id=origen_id,
        )
    except Exception:  # noqa: BLE001 — un push roto no debe abortar la captura
        logger.exception("push tesoreria %s falló (usuario=%s)", categoria, usuario.pk)


def notificar_reembolso_pendiente(egreso, autor) -> None:
    """Push al pagador y a los contadores cuando se captura un egreso
    `por_reembolsar`. El autor puede ser pagador o no — si lo es, se evita
    auto-notificación duplicada."""
    def _hacer():
        destinatarios: dict[int, object] = {}
        for u in _contadores_y_admins_activos():
            destinatarios[u.pk] = u
        if egreso.pagado_por_id and egreso.pagado_por_id not in destinatarios:
            destinatarios[egreso.pagado_por_id] = egreso.pagado_por
        destinatarios.pop(getattr(autor, "pk", None), None)

        monto = f"${egreso.monto:,.2f}".rstrip("0").rstrip(".") if egreso.monto else "—"
        pagador = (
            egreso.pagado_por.nombre_completo if egreso.pagado_por else "alguien"
        )
        for u in destinatarios.values():
            _enviar(
                u,
                titulo=f"💸 Reembolso pendiente: {egreso.codigo}",
                cuerpo=f"{pagador} adelantó {monto} — {egreso.descripcion[:120]}",
                url=f"/tesoreria/egresos/{egreso.pk}/",
                tag=f"tesoreria-reembolso-{egreso.pk}",
                categoria="tesoreria_reembolso",
                origen_modulo="tesoreria",
                origen_id=egreso.pk,
            )
    transaction.on_commit(_hacer)
