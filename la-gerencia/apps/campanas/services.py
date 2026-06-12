"""Servicio de envío de campañas (V6 Bloque 7C). Best-effort por destinatario."""

from __future__ import annotations

from .models import CampanaCorreo, CampanaEnvio


def contexto_para(cliente, campana: CampanaCorreo) -> dict:
    from django.utils import timezone
    ctx = {
        "cliente": cliente.nombre_contacto or cliente.razon_social,
        "fecha": timezone.localdate().strftime("%d/%m/%Y"),
        "representante": "",
    }
    if campana.plantilla_slug == "generico":
        ctx["asunto"] = campana.asunto_custom or "Mensaje de Learning Center"
        ctx["mensaje"] = campana.mensaje_custom
    return ctx


def enviar_campana(campana: CampanaCorreo, clientes, actor) -> CampanaCorreo:
    """Manda el lote. Un fallo por destinatario NO aborta el resto. Audita
    cada envío y emite eventos Portavoz."""
    from ajustes.models.plantilla_correo import PlantillaCorreo
    from lib import cartero
    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz

    plantilla = PlantillaCorreo.obtener(campana.plantilla_slug)
    emitir(EventoPortavoz(
        tipo="correo.campana_iniciada",
        actor_id=actor.pk, actor_email=actor.email,
        payload={"campana_id": campana.pk, "plantilla": campana.plantilla_slug,
                 "total": len(clientes)},
    ))
    enviados = fallidos = 0
    for cliente in clientes:
        email = (cliente.email_contacto or "").strip()
        if not email:
            continue
        try:
            asunto, html = plantilla.render(contexto_para(cliente, campana))
            res = cartero.enviar(destinatario=email, asunto=asunto, html=html)
            ok = bool(getattr(res, "ok", False))
            error = "" if ok else str(getattr(res, "error", "") or "error desconocido")[:300]
        except Exception as exc:  # noqa: BLE001 — un destinatario no aborta el lote
            ok, error = False, str(exc)[:300]
        CampanaEnvio.objects.create(
            campana=campana, cliente=cliente, email=email,
            estado="enviado" if ok else "fallido", error=error,
        )
        if ok:
            enviados += 1
            emitir(EventoPortavoz(
                tipo="correo.campana_envio", actor_id=actor.pk, actor_email=actor.email,
                payload={"campana_id": campana.pk, "cliente_id": cliente.pk},
            ))
        else:
            fallidos += 1
            emitir(EventoPortavoz(
                tipo="correo.campana_fallido", actor_id=actor.pk, actor_email=actor.email,
                payload={"campana_id": campana.pk, "cliente_id": cliente.pk, "error": error},
            ))
    campana.enviados = enviados
    campana.fallidos = fallidos
    campana.save(update_fields=["enviados", "fallidos"])
    return campana
