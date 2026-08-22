"""Motor de las reglas de correo: evento del sistema → plantilla → envío.

Lo invocan las señales (proyecto que cambia de estado, cotización aprobada,
entrega completada) y el cron de clientes dormidos. Todo aquí es
**best-effort**: si el correo falla, se registra y ya. Entregar un proyecto no
puede fallar porque el servidor de correo esté caído.

Dos salvaguardas que no son opcionales:

1. **Anti-repetición.** Cada disparo lleva una `referencia` que identifica el
   hecho (`proyecto:12:entregado`). Si ya se mandó, no se repite. Un proyecto
   que va y vuelve entre dos estados no bombardea al cliente.
2. **Sólo a correos registrados.** El destinatario sale del cliente que ya está
   en el sistema; una regla nunca escribe a una dirección improvisada.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _email_de(cliente) -> str:
    if cliente is None:
        return ""
    return (getattr(cliente, "email_contacto", "") or "").strip()


def disparar(
    evento: str, *, referencia: str, cliente=None, proyecto=None,
    extra: dict | None = None,
) -> int:
    """Corre las reglas activas de `evento`. Devuelve cuántos correos salieron.

    Nunca lanza: la operación que originó el evento ya ocurrió y no se
    deshace por un correo.
    """
    try:
        return _disparar(evento, referencia, cliente, proyecto, extra)
    except Exception:  # noqa: BLE001 — el correo jamás tumba la operación
        logger.warning("reglas_correo: fallo disparando %s (%s)", evento, referencia,
                       exc_info=True)
        return 0


def _disparar(evento, referencia, cliente, proyecto, extra) -> int:
    from ajustes.models import CorreoEnviadoRegla, ReglaCorreo
    from lib import cartero, correo_contexto

    reglas = list(ReglaCorreo.activas_de(evento))
    if not reglas:
        return 0

    if cliente is None and proyecto is not None:
        cliente = getattr(proyecto, "cliente", None)
    destinatario = _email_de(cliente)
    if not destinatario:
        logger.info("reglas_correo: %s sin email de contacto, no se manda (%s)",
                    evento, referencia)
        return 0

    enviados = 0
    for regla in reglas:
        if not regla.esta_completa:
            continue
        if _ya_se_mando(regla, referencia):
            continue
        contexto = correo_contexto.armar(
            cliente=cliente, proyecto=proyecto, extra=extra,
        )
        asunto, html = regla.plantilla.render(contexto)
        from ajustes.models.alias_remitente import remitente_para

        resultado = cartero.enviar(
            destinatario=destinatario, asunto=asunto, html=html,
            # Sin usuario detrás: `remitente_para` descarta cualquier alias
            # personal. Un correo que sale solo no puede ir firmado por alguien
            # que ni se enteró.
            remitente=remitente_para(regla.plantilla, None),
        )
        ok = bool(getattr(resultado, "ok", False))
        # Se audita el intento SIEMPRE, ok o no: la fila es el candado, así que
        # un fallo tampoco debe reintentarse en bucle en el siguiente guardado.
        CorreoEnviadoRegla.objects.get_or_create(
            regla=regla, referencia=referencia,
            defaults={
                "destinatario": destinatario, "ok": ok,
                "error": ("" if ok else getattr(resultado, "error", ""))[:300],
            },
        )
        if ok:
            enviados += 1
            _emitir(evento, regla, cliente, destinatario)
        else:
            logger.warning("reglas_correo: %s no se pudo entregar: %s",
                           evento, getattr(resultado, "error", ""))
    return enviados


def _ya_se_mando(regla, referencia: str) -> bool:
    from ajustes.models import CorreoEnviadoRegla
    return CorreoEnviadoRegla.objects.filter(
        regla=regla, referencia=referencia,
    ).exists()


def _emitir(evento, regla, cliente, destinatario) -> None:
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="correo.regla_disparada",
            actor_id=None, actor_email=None,
            payload={
                "evento": evento, "regla_id": regla.pk,
                "plantilla": regla.plantilla.slug,
                "cliente_id": getattr(cliente, "pk", None),
                "destinatario": destinatario,
            },
        ))
    except Exception:  # noqa: BLE001
        logger.debug("reglas_correo: no se pudo emitir el evento", exc_info=True)


# ── Disparadores concretos ───────────────────────────────────────────────────
# Cada uno arma su referencia y su contexto. Se llaman desde señales, siempre
# dentro de transaction.on_commit para no mandar correo de algo que se revierte.


def proyecto_cambio_estado(proyecto, estado_nuevo: str) -> int:
    """Sólo dispara las reglas cuyo `estado_slug` coincide con el nuevo estado."""
    from ajustes.models import ReglaCorreo

    reglas = [r for r in ReglaCorreo.activas_de("proyecto_estado")
              if r.estado_slug == estado_nuevo]
    if not reglas:
        return 0
    return disparar(
        "proyecto_estado",
        referencia=f"proyecto:{proyecto.pk}:{estado_nuevo}",
        proyecto=proyecto,
    )


def cotizacion_aprobada(cot) -> int:
    proyecto = getattr(cot, "proyecto", None)
    cliente = getattr(cot, "cliente", None) or getattr(proyecto, "cliente", None)
    try:
        monto = f"{cot.calcular_totales()['total']:,.2f}"
    except Exception:  # noqa: BLE001 — el monto es adorno, no bloquea el aviso
        monto = ""
    return disparar(
        "cotizacion_aprobada",
        referencia=f"cotizacion:{cot.pk}",
        cliente=cliente, proyecto=proyecto,
        extra={"folio": getattr(cot, "codigo", ""), "monto": monto},
    )


def mandado_entregado(mandado) -> int:
    tarea = getattr(mandado, "tarea", None)
    proyecto = getattr(tarea, "proyecto", None)
    return disparar(
        "mandado_entregado",
        referencia=f"mandado:{mandado.pk}",
        proyecto=proyecto,
        extra={"mensaje": getattr(tarea, "titulo", "")},
    )


def clientes_dormidos(dry_run: bool = False) -> list[dict]:
    """Recorre las reglas de «cliente dormido». Lo llama el cron.

    Un cliente entra si no tiene proyectos creados en los últimos `dias` días.
    La referencia lleva el mes, así que como mucho recibe un correo al mes por
    regla aunque el cron corra a diario.
    """
    from datetime import timedelta

    from django.utils import timezone

    from ajustes.models import ReglaCorreo

    resultados: list[dict] = []
    for regla in ReglaCorreo.activas_de("cliente_dormido"):
        if not regla.esta_completa:
            continue
        corte = timezone.now() - timedelta(days=regla.dias)
        for cliente in _clientes_sin_proyectos_desde(corte):
            referencia = f"cliente:{cliente.pk}:{timezone.localdate():%Y-%m}"
            if _ya_se_mando(regla, referencia):
                continue
            if dry_run:
                resultados.append({"cliente": cliente.razon_social, "enviado": False})
                continue
            n = disparar("cliente_dormido", referencia=referencia, cliente=cliente)
            resultados.append({"cliente": cliente.razon_social, "enviado": bool(n)})
    return resultados


def _clientes_sin_proyectos_desde(corte):
    """Clientes activos, con email, sin ningún proyecto creado después de `corte`."""
    from apps.la_cartera.models import Cliente
    return (
        Cliente.objects.filter(activo=True)
        .exclude(email_contacto="")
        .exclude(proyectos__creado_en__gte=corte)
        .distinct()
    )


__all__ = [
    "disparar", "proyecto_cambio_estado", "cotizacion_aprobada",
    "mandado_entregado", "clientes_dormidos",
]
