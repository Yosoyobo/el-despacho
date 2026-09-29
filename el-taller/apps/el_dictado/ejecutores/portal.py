"""Ejecutor de La Recepción: invitar a un contacto al portal de clientes.

Siempre llega como PROPUESTA del Chalán que una persona confirma (regla §20):
la invitación manda un correo con la llave de entrada al portal. La lógica vive
en `portal.servicios.invitar` —la misma del botón «Invitar al portal» de la
ficha—, así que las dos superficies aplican las mismas reglas: sólo correos que
ya están en la ficha del cliente, y un correo abre un solo cliente.
"""

from __future__ import annotations

from . import _gate, registrar
from .avanzados import _exigir


def _cliente(payload: dict):
    from capacidades.lecturas import _cliente_por_texto

    ref = str(payload.get("cliente_slug") or payload.get("cliente") or "").strip()
    _exigir(bool(ref), "Falta `cliente_slug`: el cliente al que pertenece el contacto.")
    c = _cliente_por_texto(ref)
    _exigir(c is not None, f"No encontré el cliente «{ref}».")
    return c


def _email_del_contacto(cliente, contacto: str) -> str:
    """El correo del contacto pedido, buscado SÓLO entre los de su ficha."""
    from portal.servicios import invitables_de, normalizar_email

    texto = (contacto or "").strip()
    _exigir(bool(texto), "Falta `contacto`: su nombre o su correo, tal como está en la ficha.")
    filas = invitables_de(cliente)
    if "@" in texto:
        email = normalizar_email(texto)
        _exigir(any(f.email == email for f in filas),
                f"{email} no es de ningún contacto de {cliente.razon_social}. Agrégalo "
                "primero como contacto en su ficha.")
        return email
    candidatos = [f for f in filas if texto.lower() in (f.nombre or "").lower()]
    _exigir(bool(candidatos),
            f"{cliente.razon_social} no tiene un contacto con correo que se llame «{texto}».")
    _exigir(len(candidatos) == 1,
            f"Hay {len(candidatos)} contactos que coinciden con «{texto}»: dime su correo.")
    return candidatos[0].email


@registrar("invitar_portal")
def invitar_portal(accion, usuario, contexto=None):
    """Payload: cliente_slug, contacto (nombre o correo de un contacto de la ficha)."""
    _gate(usuario, "puede_invitar_portal", "invitar clientes al portal")
    from portal.servicios import ErrorPortal, invitar

    payload = accion.payload or {}
    cliente = _cliente(payload)
    email = _email_del_contacto(cliente, str(payload.get("contacto") or payload.get("email") or ""))
    try:
        res = invitar(cliente, email, usuario)
    except ErrorPortal as exc:
        raise ValueError(str(exc)) from exc
    accion.entidad_tipo = "cliente"
    accion.entidad_id = cliente.pk
    if not res.correo_ok:
        # El acceso quedó, pero sin correo la persona no puede entrar: se dice.
        raise ValueError(
            f"{email} ya tiene acceso al portal, pero el correo de invitación no salió "
            f"({res.error_correo or 'El Cartero no contestó'}). Reenvíalo desde la ficha del cliente.")


__all__ = ["invitar_portal"]
