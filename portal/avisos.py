"""Los avisos al equipo por lo que hace un cliente en el portal: responder una
cotización y subir un documento.

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


#: Quién se entera de un documento nuevo. El comprobante de pago además le llega
#: a quien cobra, que es quien registra el cobro (el comprobante NO lo registra).
PERMISO_DOCUMENTOS = ("recepcion", "documentos")
PERMISO_COBRO = ("facturacion", "cobrar")
#: Su propia casilla opt-out: quien revisa papelería no tiene por qué recibir las
#: respuestas de cotizaciones, y viceversa.
CATEGORIA_DOCUMENTOS = "portal_documentos"


def documento_subido(doc) -> None:
    """Push a quien revisa documentos (y a quien cobra, si es un comprobante).
    Sólo si lo subió el CLIENTE: lo que sube el equipo ya lo sabe el equipo.
    Nunca lanza."""
    if not doc.acceso_id:
        return
    from .models import TIPO_COMPROBANTE

    empresa = getattr(doc.cliente, "razon_social", "") or "Un cliente"
    quien = doc.quien_subio or "El cliente"
    es_pago = doc.tipo == TIPO_COMPROBANTE
    titulo = "💸 Comprobante de pago en el portal" if es_pago else "📎 Documento nuevo en el portal"
    detalle = f" de la factura {doc.factura.folio or doc.factura.codigo}" if (es_pago and doc.factura_id) else ""
    cuerpo = f"{empresa}: {quien} subió {doc.tipo_nombre.lower()}{detalle}."[:300]
    if es_pago:
        cuerpo = (cuerpo + " Revísalo y registra el cobro en la factura.")[:300]
    url = f"/cartera/{doc.cliente_id}/#documentos-cliente"
    pk = doc.pk

    def _hacer():
        from lib.interfono import enviar_a_usuario
        from lib.permisos import usuarios_con_permiso

        destinatarios = {u.pk: u for u in usuarios_con_permiso(*PERMISO_DOCUMENTOS)}
        if es_pago:
            destinatarios.update({u.pk: u for u in usuarios_con_permiso(*PERMISO_COBRO)})
        for u in destinatarios.values():
            try:
                enviar_a_usuario(u, titulo=titulo, cuerpo=cuerpo, url=url,
                                 tag=f"portal-doc-{pk}", categoria=CATEGORIA_DOCUMENTOS,
                                 origen_modulo="recepcion", origen_id=pk)
            except Exception:  # noqa: BLE001
                logger.exception("portal: no se pudo avisar del documento a usuario=%s", u.pk)

    def _al_confirmar():
        from lib.tareas_fondo import ejecutar_en_fondo

        ejecutar_en_fondo(_hacer)

    try:
        transaction.on_commit(_al_confirmar)
    except Exception:  # noqa: BLE001
        logger.exception("portal: no se pudo programar el aviso del documento")


__all__ = ["CATEGORIA", "CATEGORIA_DOCUMENTOS", "PERMISO", "PERMISO_COBRO", "PERMISO_DOCUMENTOS",
           "cotizacion_respondida", "documento_subido"]
