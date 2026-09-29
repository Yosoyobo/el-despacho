"""El aviso al equipo cuando un cliente responde una cotización desde el portal.

Dos caminos, los dos best-effort (responder la cotización nunca falla por el
aviso):

- **Portavoz**: evento tipado `portal.cotizacion_aprobada` / `…_rechazada`
  (además del `cotizacion.aprobada` / `…rechazada` que ya emite el servicio de
  cotizaciones), para que n8n sepa que vino del portal.
- **El Interfón**: push a quien puede ver cotizaciones (`cotizaciones.ver`),
  categoría `portal` — opt-out en `/perfil/notificaciones/` como las demás.
  Después del commit y en el fondo: el cliente no espera a que Apple y Google
  acusen recibo.
"""

from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger(__name__)

#: La categoría opt-out en `/perfil/notificaciones/`.
CATEGORIA = "portal"
#: A quién le llega (y quién ve la casilla para silenciarlo).
PERMISO = ("cotizaciones", "ver")


def cotizacion_respondida(cot, acceso, *, nombre: str, aprobada: bool, tipo_evento: str) -> None:
    """Nunca lanza."""
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        emitir(EventoPortavoz(
            tipo=tipo_evento, actor_id=None, actor_email=acceso.email,
            payload={"cotizacion_id": cot.pk, "codigo": cot.codigo,
                     "cliente_id": cot.cliente_id, "acceso_id": acceso.pk,
                     "nombre": nombre[:200], "via": "portal"},
        ))
    except Exception:  # noqa: BLE001
        logger.warning("portal: no se pudo emitir %s", tipo_evento, exc_info=True)

    empresa = getattr(cot.cliente, "razon_social", "") or "Un cliente"
    titulo = ("✅ Cotización aprobada en el portal" if aprobada
              else "✋ Cotización rechazada en el portal")
    cuerpo = (f"{empresa}: {nombre} {'aprobó' if aprobada else 'rechazó'} la "
              f"{cot.codigo} ({cot.titulo})."[:300])
    pk = cot.pk

    def _hacer():
        from lib.interfono import enviar_a_usuario
        from lib.permisos import usuarios_con_permiso

        for u in usuarios_con_permiso(*PERMISO):
            try:
                enviar_a_usuario(u, titulo=titulo, cuerpo=cuerpo, url=f"/cotizaciones/{pk}/",
                                 tag=f"portal-cot-{pk}", categoria=CATEGORIA,
                                 origen_modulo="cotizaciones", origen_id=pk)
            except Exception:  # noqa: BLE001 — un aviso roto no tumba los demás
                logger.exception("portal: no se pudo avisar a usuario=%s", u.pk)

    def _al_confirmar():
        from lib.tareas_fondo import ejecutar_en_fondo

        ejecutar_en_fondo(_hacer)

    try:
        transaction.on_commit(_al_confirmar)
    except Exception:  # noqa: BLE001
        logger.exception("portal: no se pudo programar el aviso")


__all__ = ["CATEGORIA", "PERMISO", "cotizacion_respondida"]
