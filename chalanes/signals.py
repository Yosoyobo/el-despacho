"""Signals de Los Chalanes.

Cuando se guarda una `Credencial` con clave `chalan_<proveedor>_api_key` y un
valor no vacío, se asegura que el proveedor tenga una fila en
`CadenaFallback` con la siguiente prioridad disponible y `activo=True`. Si la
credencial se borra (signal post_delete), la fila NO se quita automáticamente
— el super_admin puede dejarla inactiva manualmente. La razón: borrar la fila
perdería el orden histórico que el equipo configuró.
"""

from __future__ import annotations

import contextlib
import re

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

# Coincide con `chalan_<nombre>_api_key`. Captura el nombre del proveedor.
_PATRON_SLOT = re.compile(r"^chalan_([a-z0-9]+)_api_key$")

# Proveedores que aún no tienen adapter funcional (skeleton). Vacío a
# partir de S-Demo-Pre-Showcase — Gemini activado.
_NO_REGISTRAR: set[str] = set()


@receiver(post_save, sender="ajustes.Credencial")
def auto_agregar_a_cadena_fallback(sender, instance, created, **kwargs):  # noqa: ARG001
    """Si la credencial es un slot de Chalán con valor, ensure fila en cadena."""
    match = _PATRON_SLOT.match(instance.clave or "")
    if not match:
        return
    proveedor = match.group(1)
    if proveedor in _NO_REGISTRAR:
        return

    # Sólo registrar el adapter en `_FACTORIES` cuenta como "soportado".
    try:
        from lib.analistas.registry import _FACTORIES
        if proveedor not in _FACTORIES:
            return
    except Exception:  # noqa: BLE001
        return

    # Si el valor está vacío (la API de Credencial.guardar borra antes de llegar
    # a post_save en ese caso, así que aquí siempre hay valor), seguimos.
    try:
        from .models import CadenaFallback
    except Exception:  # noqa: BLE001
        return

    if CadenaFallback.objects.filter(proveedor=proveedor).exists():
        return

    siguiente = (
        CadenaFallback.objects.order_by("-prioridad").values_list("prioridad", flat=True).first()
        or 0
    ) + 1

    with contextlib.suppress(Exception):
        CadenaFallback.objects.create(
            proveedor=proveedor, prioridad=siguiente, activo=True,
        )


@receiver(post_save, sender="chalanes.PromptVoz", dispatch_uid="prompt_voz_cache_save")
@receiver(post_delete, sender="chalanes.PromptVoz", dispatch_uid="prompt_voz_cache_del")
def _invalidar_cache_voz(sender, **kwargs):  # noqa: ARG001
    """Al guardar/borrar una voz, limpia el caché para que el próximo prompt
    la recoja sin esperar a que expire el TTL."""
    with contextlib.suppress(Exception):
        from .voz import invalidar_cache_voz
        invalidar_cache_voz()
