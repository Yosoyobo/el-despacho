"""Signals de Los Chalanes.

Cuando se guarda una `Credencial` con clave `chalan_<proveedor>_api_key` y un
valor no vacío, se asegura que el proveedor tenga una fila en `CadenaFallback`
con la siguiente prioridad disponible y `activo=True` (reactivándola si estaba
apagada). Cuando la credencial se borra (post_delete), la fila se **desactiva**
(`activo=False`) — NO se elimina, para preservar el orden histórico que el
equipo configuró; al volver a pegar la llave se reactiva sola. Así el proveedor
sin llave sale del relevo/fallback de inmediato (S-Chalan-Agente fix).
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


def _proveedor_de_slot(clave: str | None) -> str | None:
    """Devuelve el proveedor soportado del slot `chalan_<prov>_api_key`, o None."""
    match = _PATRON_SLOT.match(clave or "")
    if not match:
        return None
    proveedor = match.group(1)
    if proveedor in _NO_REGISTRAR:
        return None
    try:
        from lib.analistas.registry import _FACTORIES
        if proveedor not in _FACTORIES:
            return None
    except Exception:  # noqa: BLE001
        return None
    return proveedor


@receiver(post_save, sender="ajustes.Credencial")
def auto_agregar_a_cadena_fallback(sender, instance, created, **kwargs):  # noqa: ARG001
    """Al guardar la llave de un Chalán: crea su fila en la cadena (si falta) o
    la **reactiva** si estaba apagada por un borrado previo."""
    proveedor = _proveedor_de_slot(instance.clave)
    if not proveedor:
        return
    try:
        from .models import CadenaFallback
    except Exception:  # noqa: BLE001
        return

    fila = CadenaFallback.objects.filter(proveedor=proveedor).first()
    if fila is not None:
        if not fila.activo:
            fila.activo = True
            fila.save(update_fields=["activo"])
        return

    siguiente = (
        CadenaFallback.objects.order_by("-prioridad").values_list("prioridad", flat=True).first()
        or 0
    ) + 1
    with contextlib.suppress(Exception):
        CadenaFallback.objects.create(
            proveedor=proveedor, prioridad=siguiente, activo=True,
        )


@receiver(post_delete, sender="ajustes.Credencial")
def auto_desactivar_de_cadena_fallback(sender, instance, **kwargs):  # noqa: ARG001
    """Al borrar la llave de un Chalán: lo desactiva del relevo/fallback (no
    borra la fila, para conservar el orden)."""
    proveedor = _proveedor_de_slot(instance.clave)
    if not proveedor:
        return
    with contextlib.suppress(Exception):
        from .models import CadenaFallback
        CadenaFallback.objects.filter(proveedor=proveedor, activo=True).update(activo=False)


@receiver(post_save, sender="chalanes.PromptVoz", dispatch_uid="prompt_voz_cache_save")
@receiver(post_delete, sender="chalanes.PromptVoz", dispatch_uid="prompt_voz_cache_del")
def _invalidar_cache_voz(sender, **kwargs):  # noqa: ARG001
    """Al guardar/borrar una voz, limpia el caché para que el próximo prompt
    la recoja sin esperar a que expire el TTL."""
    with contextlib.suppress(Exception):
        from .voz import invalidar_cache_voz
        invalidar_cache_voz()
