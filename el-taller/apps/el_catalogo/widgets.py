"""Widgets reusables del catálogo.

LC 2026-07-25 (Oscar): «en el buscador de productos debemos encontrarlos también
escribiendo el nombre del proveedor». LC 2026-07-26: y por cualquier ALIAS con el
que el producto se haya vendido en un proyecto («TShirt Modelo Janet» encuentra
la playera del catálogo).

El combobox canónico (`data-select-buscable`, `static/js/form_widgets.js`) ya
soporta búsqueda cruzada vía el atributo `data-buscar` de cada `<option>`; este
widget lo llena, sin ensuciar la etiqueta visible.
"""

from __future__ import annotations

import contextlib

from django import forms

CLAVE_CACHE_ALIAS = "catalogo:alias_productos"
TTL_CACHE_ALIAS = 60


def mapa_alias(*, usar_cache: bool = True) -> dict[int, list[str]]:
    """`{servicio_id: [alias, …]}` con los nombres que se le han puesto al
    producto en algún proyecto.

    Es UNA consulta plana (dos columnas) en lugar de traer los objetos, y va
    cacheada 60 s: un formset con N tarjetas instancia N forms, y sin caché cada
    uno repetiría la consulta. Portable (nada de agregados de Postgres, que
    tampoco existen en el SQLite de los tests) y defensivo: cualquier fallo
    devuelve un mapa vacío y el `<select>` se comporta como antes. Un alias nuevo
    es buscable de inmediato: un signal de `ProyectoProducto` tira la caché (ver
    `invalidar_mapa_alias`), y el TTL queda como red por si el signal no corre.
    """
    if usar_cache:
        try:
            from django.core.cache import cache
            guardado = cache.get(CLAVE_CACHE_ALIAS)
            if guardado is not None:
                return guardado
        except Exception:  # noqa: BLE001 — Redis caído: se consulta sin caché
            pass
    mapa = _mapa_alias_db()
    if usar_cache:
        try:
            from django.core.cache import cache
            cache.set(CLAVE_CACHE_ALIAS, mapa, TTL_CACHE_ALIAS)
        except Exception:  # noqa: BLE001
            pass
    return mapa


def invalidar_mapa_alias() -> None:
    """Tira la caché de alias. La llama un signal de `ProyectoProducto`
    (ver `los_proyectos.apps`) para que un alias nuevo sea buscable al instante
    en vez de esperar el TTL. Nunca lanza."""
    try:
        from django.core.cache import cache
        cache.delete(CLAVE_CACHE_ALIAS)
    except Exception:  # noqa: BLE001 — Redis caído: el TTL se encarga
        pass


def _mapa_alias_db() -> dict[int, list[str]]:
    try:
        from apps.los_proyectos.models import ProyectoProducto
        filas = (ProyectoProducto.objects
                 .exclude(nombre_proyecto="")
                 .values_list("servicio_id", "nombre_proyecto"))
        mapa: dict[int, list[str]] = {}
        for servicio_id, nombre in filas.iterator(chunk_size=2000):
            if not servicio_id:
                continue
            nom = (nombre or "").strip()
            lista = mapa.setdefault(servicio_id, [])
            if nom and nom not in lista:
                lista.append(nom)
        return mapa
    except Exception:  # noqa: BLE001 — un select nunca debe tumbar el form
        return {}


class SelectProductoBuscable(forms.Select):
    """`<select>` de Producto buscable también por proveedor y por los alias con
    que se ha vendido en proyectos."""

    def __init__(self, attrs=None, choices=(), alias=None):
        base = {"data-select-buscable": "1"}
        base.update(attrs or {})
        # Se calcula UNA vez por widget (no por opción).
        self.alias = alias if alias is not None else mapa_alias()
        super().__init__(base, choices)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex, attrs)
        instancia = getattr(value, "instance", None)
        if instancia is not None:
            partes = []
            # Solo proveedores VIGENTES: por uno archivado ya no se busca (y su
            # nombre no debe filtrarse a la página del proyecto).
            with contextlib.suppress(Exception):  # sin proveedores precargados
                partes += [p.razon_social for p in instancia.proveedores.all() if p.activo]
            partes += [a for a in (self.alias or {}).get(instancia.pk, []) if a not in partes]
            if partes:
                opcion["attrs"]["data-buscar"] = ", ".join(partes)
        return opcion


__all__ = ["SelectProductoBuscable", "invalidar_mapa_alias", "mapa_alias"]
