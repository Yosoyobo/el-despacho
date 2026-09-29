"""La Caja desde El Chalán: hacer (y mandar) un link de pago en línea.

Mismo contrato que el resto: `(accion, usuario, contexto)`, lanza `ValueError`
si algo no cuadra, y nada se aplica sin la confirmación humana (§20). El permiso
se vuelve a comprobar aquí aunque el prompt ya filtre: el prompt sugiere, esto
es la puerta. Para el link de una factura o cotización se pide además poder
VERLA — La Caja no abre lo que el módulo dueño tiene cerrado.

Lo que NO hace: registrar un pago que llegó y no cuadró. Eso es decidir sobre
dinero real y se hace con el botón «Registrar» de La Caja.
"""

from __future__ import annotations

from . import _gate, registrar


def _payload(accion) -> dict:
    return accion.payload if hasattr(accion, "payload") else (accion or {})


def _si(valor) -> bool:
    return valor is True or str(valor).strip().lower() in {"1", "true", "si", "sí", "yes"}


@registrar("crear_link_pago")
def crear_link_pago(accion, usuario, contexto=None):
    """Payload: factura | cotizacion | (cliente_slug o proyecto_slug) + monto + concepto;
    enviar_correo?."""
    _gate(usuario, "puede_crear_link_caja", "crear links de pago")
    from apps.caja import services

    from .avanzados import _cotizacion_por_codigo, _factura_por_codigo
    from .basicos import _resolver_cliente, _resolver_proyecto

    if not services.configurada():
        raise ValueError("La Caja está apagada: faltan las llaves de Stripe o MercadoPago en Los Ajustes.")
    p = _payload(accion)
    if p.get("factura") or p.get("codigo_factura"):
        _gate(usuario, "puede_ver_facturacion", "ver facturas")
        objeto = _factura_por_codigo(p.get("factura") or p.get("codigo_factura"))
        link = services.link_para(objeto, actor=usuario)
        if link is None:
            raise ValueError(f"La factura {objeto.folio_display} no tiene saldo que cobrar en línea "
                             "(o no está emitida).")
    elif p.get("cotizacion"):
        _gate(usuario, "puede_ver_cotizaciones", "ver cotizaciones")
        objeto = _cotizacion_por_codigo(p.get("cotizacion"))
        link = services.link_para(objeto, actor=usuario)
        if link is None:
            raise ValueError(f"La cotización {objeto.codigo} no tiene anticipo por cobrar.")
    else:
        proyecto = cliente = None
        if slug := (p.get("proyecto_slug") or "").strip():
            proyecto = _resolver_proyecto(slug, contexto)
        elif slug := (p.get("cliente_slug") or "").strip():
            cliente = _resolver_cliente(slug.lower(), contexto)
        else:
            raise ValueError("Di de qué factura o cotización es el link, o a qué cliente o proyecto cobrarle.")
        link = services.crear_link_libre(
            monto=str(p.get("monto") or "").replace(",", "").replace("$", "").strip() or "0",
            concepto=p.get("concepto") or "", actor=usuario, cliente=cliente, proyecto=proyecto,
        )
    if _si(p.get("enviar_correo")):
        res = services.enviar_por_correo(link, actor=usuario)
        if not res.ok:
            raise ValueError(f"El link quedó hecho ({link.url_publica()}), pero el correo no salió: "
                             f"{res.error or res.detalle}")
    if hasattr(accion, "entidad_tipo"):
        accion.entidad_tipo = "link_pago"
        accion.entidad_id = link.pk
    return {"entidad_tipo": "link_pago", "entidad_id": link.pk, "url": link.url_publica()}
