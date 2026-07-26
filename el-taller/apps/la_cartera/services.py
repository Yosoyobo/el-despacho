"""Services de La Cartera.

Unificación de los dos sistemas de contacto (S-LC-Feedback-V6 Bloque 0):
`ClienteContacto` es la única fuente de verdad; los campos legacy
`Cliente.nombre_contacto / email_contacto / telefono` se mantienen como espejo
del contacto principal (los usan la búsqueda, el orden de la lista y código
viejo). Toda ruta de escritura debe pasar por estos helpers.
"""

from apps.la_cartera.models import Cliente, ClienteContacto, ClienteRazonSocial


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


# ── Razones sociales de facturación (LC 2026-07-26) ──────────────────────────
#
# Mismo patrón que los contactos: `ClienteRazonSocial` es la lista completa y la
# marcada `principal` se espeja a los campos legacy `razon_social_fiscal`/`rfc`
# del Cliente (los usan la búsqueda, el CFDI y el código viejo).

def espejar_razon_principal(cliente: Cliente) -> None:
    """Razón social principal → campos legacy del Cliente.

    Llamar después de guardar el formset de razones sociales. Si el cliente no
    tiene ninguna, no toca nada (preserva lo capturado por rutas legacy).
    """
    rp = cliente.razon_social_principal
    if rp is None:
        return
    cliente.razon_social_fiscal = rp.razon_social
    cliente.rfc = rp.rfc
    cliente.save(update_fields=["razon_social_fiscal", "rfc", "actualizado_en"])


def asegurar_razon_principal(cliente: Cliente) -> None:
    """Espejo inverso: campos legacy → razón social principal.

    Para rutas que solo capturan los campos del Cliente (edición rápida de la
    lista, quick-create desde un proyecto). Si ya hay razones sociales, actualiza
    la principal en lugar de duplicar.
    """
    if not (cliente.razon_social_fiscal or cliente.rfc):
        return
    rp = cliente.razon_social_principal
    if rp is None:
        ClienteRazonSocial.objects.create(
            cliente=cliente,
            razon_social=cliente.razon_social_fiscal or cliente.razon_social,
            rfc=cliente.rfc or "",
            principal=True,
        )
        return
    rp.razon_social = cliente.razon_social_fiscal or rp.razon_social
    rp.rfc = cliente.rfc or rp.rfc
    rp.principal = True
    rp.save(update_fields=["razon_social", "rfc", "principal"])
