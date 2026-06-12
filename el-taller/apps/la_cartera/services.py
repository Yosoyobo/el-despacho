"""Services de La Cartera.

Unificación de los dos sistemas de contacto (S-LC-Feedback-V6 Bloque 0):
`ClienteContacto` es la única fuente de verdad; los campos legacy
`Cliente.nombre_contacto / email_contacto / telefono` se mantienen como espejo
del contacto principal (los usan la búsqueda, el orden de la lista y código
viejo). Toda ruta de escritura debe pasar por estos helpers.
"""

from apps.la_cartera.models import Cliente, ClienteContacto


def espejar_contacto_principal(cliente: Cliente) -> None:
    """Copia el contacto principal a los campos legacy del Cliente.

    Llamar SIEMPRE después de guardar el formset de contactos. Si el cliente
    no tiene contactos, no toca nada (preserva lo capturado a mano en rutas
    legacy).
    """
    cp = cliente.contacto_principal
    if cp is None:
        return
    cliente.nombre_contacto = cp.nombre
    cliente.email_contacto = cp.email
    cliente.telefono = cp.telefono
    cliente.save(update_fields=[
        "nombre_contacto", "email_contacto", "telefono", "actualizado_en",
    ])


def asegurar_contacto_principal(cliente: Cliente) -> None:
    """Espejo inverso: campos legacy → ClienteContacto principal.

    Para rutas que solo capturan los campos del Cliente (modal de proyecto,
    quick-create de Ingreso). Si el cliente ya tiene contactos, no duplica.
    """
    if cliente.contactos.exists():
        return
    if cliente.nombre_contacto or cliente.email_contacto or cliente.telefono:
        ClienteContacto.objects.create(
            cliente=cliente,
            nombre=cliente.nombre_contacto or "Contacto",
            email=cliente.email_contacto,
            telefono=cliente.telefono,
            principal=True,
        )
