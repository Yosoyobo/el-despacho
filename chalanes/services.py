"""Servicios de Los Chalanes — overrides de Chalán por usuario (raíz, shared).

Centraliza la escritura de `ChalanAsignado` para que la usen tanto el
autoservicio del Taller (`/perfil/chalanes/`) como el panel admin del
Directorio (La Gerencia), sin duplicar lógica.

Estaciones canónicas: `chalanes.estaciones.ESTACIONES`.
"""

from __future__ import annotations

import contextlib

from chalanes.estaciones import ESTACIONES, ESTACIONES_DICT
from chalanes.models import ChalanAsignado
from lib.analistas import registry as _registry
from lib.analistas.capacidades import Capability
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

ESTACIONES_SLUGS = [e[0] for e in ESTACIONES]


def _soporta_vision(proveedor: str) -> bool:
    factory = _registry._FACTORIES.get(proveedor)
    if factory is None:
        return False
    return Capability.VISION in (getattr(factory, "capacidades", set()) or set())


def proveedores_configurados() -> list[str]:
    """Proveedores con llave válida en La Bóveda (slot `chalan_<n>_api_key`).
    Defensivo: si Credencial falla, devuelve todos los registrados."""
    try:
        from ajustes.models.credencial import Credencial
        out = []
        for nombre in _registry._FACTORIES:
            if Credencial.obtener(f"chalan_{nombre}_api_key"):
                out.append(nombre)
        return out
    except Exception:
        return list(_registry._FACTORIES.keys())


def overrides_de(usuario) -> dict[str, tuple[str, str]]:
    """`{estacion: (proveedor, modelo)}` de los overrides del usuario."""
    return {
        a.estacion: (a.proveedor, a.modelo or "")
        for a in ChalanAsignado.objects.filter(usuario=usuario)
    }


def proveedor_efectivo(usuario) -> str:
    """Resumen para el chip de la lista:
    - "auto"  → sin overrides (usa el Cuadro global).
    - <prov>  → TODAS las estaciones overrideadas al mismo proveedor.
    - "mixto" → overrides parciales o con proveedores distintos.
    """
    overs = ChalanAsignado.objects.filter(usuario=usuario).values_list("proveedor", flat=True)
    overs = list(overs)
    if not overs:
        return "auto"
    distintos = set(overs)
    if len(distintos) == 1 and len(overs) >= len(ESTACIONES_SLUGS):
        return overs[0]
    return "mixto"


def set_override(usuario, estacion: str, proveedor: str, modelo: str, actor) -> None:
    """Crea/actualiza/borra el override de una estación. `proveedor=""` borra."""
    proveedor = (proveedor or "").strip()
    estacion = (estacion or "").strip()
    if estacion not in ESTACIONES_DICT:
        return
    if proveedor and proveedor not in _registry._FACTORIES:
        return
    # Estación con visión: solo proveedores con visión.
    if proveedor and ESTACIONES_DICT[estacion].get("requiere_vision") and not _soporta_vision(proveedor):
        return
    if not proveedor:
        ChalanAsignado.objects.filter(usuario=usuario, estacion=estacion).delete()
    else:
        ChalanAsignado.objects.update_or_create(
            usuario=usuario, estacion=estacion,
            defaults={"proveedor": proveedor, "modelo": (modelo or "").strip()},
        )
    with contextlib.suppress(Exception):
        emitir(EventoPortavoz(
            tipo="usuario.chalan_override_actualizado",
            actor_id=getattr(actor, "pk", None), actor_email=getattr(actor, "email", None),
            payload={"usuario_id": usuario.pk, "estacion": estacion, "proveedor": proveedor or None},
        ))


def forzar_proveedor(usuario, proveedor: str, actor) -> int:
    """Fija TODAS las estaciones del usuario al mismo proveedor (modelo default
    del adapter). Las estaciones que requieren visión solo se fijan si el
    proveedor la soporta. Devuelve cuántas estaciones quedaron asignadas."""
    proveedor = (proveedor or "").strip()
    if proveedor not in _registry._FACTORIES:
        return 0
    soporta_v = _soporta_vision(proveedor)
    n = 0
    for slug, meta in ESTACIONES_DICT.items():
        if meta.get("requiere_vision") and not soporta_v:
            continue
        ChalanAsignado.objects.update_or_create(
            usuario=usuario, estacion=slug,
            defaults={"proveedor": proveedor, "modelo": ""},
        )
        n += 1
    with contextlib.suppress(Exception):
        emitir(EventoPortavoz(
            tipo="usuario.chalan_overrides_forzados",
            actor_id=getattr(actor, "pk", None), actor_email=getattr(actor, "email", None),
            payload={"usuario_id": usuario.pk, "proveedor": proveedor, "estaciones": n},
        ))
    return n


def limpiar_overrides(usuario, actor) -> int:
    """Borra todos los overrides del usuario → vuelve a "Auto" (Cuadro global)."""
    n, _ = ChalanAsignado.objects.filter(usuario=usuario).delete()
    with contextlib.suppress(Exception):
        emitir(EventoPortavoz(
            tipo="usuario.chalan_overrides_forzados",
            actor_id=getattr(actor, "pk", None), actor_email=getattr(actor, "email", None),
            payload={"usuario_id": usuario.pk, "proveedor": None, "estaciones": 0},
        ))
    return n
