"""Contexto de variables para las plantillas de correo.

Una plantilla de sistema sabe qué datos recibe porque quien la dispara los
arma. Una plantilla PROPIA no: se puede mandar desde la ficha de un cliente,
desde una campaña, desde una regla de evento o desde El Chalán. Para que
`{{ proyecto }}` no reviente en el caso donde no hay proyecto, este módulo arma
SIEMPRE el mismo diccionario y rellena con cadena vacía lo que no aplique.

Regla: **una variable nunca falta, a lo mucho llega vacía.** Django renderiza
una variable inexistente como cadena vacía igual, pero dejarlo al azar
significa que un typo (`{{ proyeto }}`) se ve idéntico a un dato ausente. Con
el contrato explícito, el editor puede ofrecer la lista correcta y quien
escribe sabe con qué cuenta.
"""

from __future__ import annotations

from ajustes.plantillas_correo_default import VARIABLES_LIBRES


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _nombre_de_cliente(cliente) -> str:
    """A quién saludamos: el contacto si lo hay, si no la razón social."""
    if cliente is None:
        return ""
    return _texto(getattr(cliente, "nombre_contacto", "")) or _texto(
        getattr(cliente, "razon_social", "")
    )


def armar(*, cliente=None, proyecto=None, representante=None, extra=None) -> dict:
    """Contexto acotado para renderizar cualquier plantilla.

    `extra` gana sobre lo derivado: quien envía puede pisar `asunto`/`mensaje`
    o corregir cualquier campo. Nunca lanza — un dato que no se puede leer
    llega vacío antes que tumbar un correo.
    """
    from django.utils import timezone

    ctx = dict.fromkeys(VARIABLES_LIBRES, "")
    ctx["fecha"] = timezone.localdate().strftime("%d/%m/%Y")

    if cliente is not None:
        ctx["cliente"] = _nombre_de_cliente(cliente)
        ctx["empresa"] = _texto(getattr(cliente, "razon_social", ""))

    if proyecto is not None:
        ctx["proyecto"] = _texto(getattr(proyecto, "nombre", "")) or _texto(
            getattr(proyecto, "codigo", "")
        )
        try:
            ctx["estado"] = _texto(proyecto.get_estado_display())
        except Exception:  # noqa: BLE001 — el catálogo de estados es configurable
            ctx["estado"] = _texto(getattr(proyecto, "estado", ""))
        ctx["folio"] = _texto(getattr(proyecto, "codigo", ""))
        # Si no vino cliente suelto, el del proyecto sirve igual.
        if not ctx["cliente"]:
            ctx["cliente"] = _nombre_de_cliente(getattr(proyecto, "cliente", None))
            ctx["empresa"] = _texto(
                getattr(getattr(proyecto, "cliente", None), "razon_social", "")
            )

    if representante is not None:
        try:
            ctx["representante"] = representante.get_short_name() or _texto(
                getattr(representante, "email", "")
            )
        except Exception:  # noqa: BLE001
            ctx["representante"] = _texto(representante)

    for clave, valor in (extra or {}).items():
        if clave in ctx or clave in VARIABLES_LIBRES:
            ctx[clave] = _texto(valor)

    return ctx


__all__ = ["armar"]
