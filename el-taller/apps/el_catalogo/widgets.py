"""Widgets reusables del catálogo.

LC 2026-07-25 (Oscar): «en el buscador de productos debemos encontrarlos también
escribiendo el nombre del proveedor». El combobox canónico
(`data-select-buscable`, `static/js/form_widgets.js`) ya soporta búsqueda cruzada
vía el atributo `data-buscar` de cada `<option>`; este widget lo llena con los
proveedores del producto, sin ensuciar la etiqueta visible.
"""

from __future__ import annotations

from django import forms


class SelectProductoBuscable(forms.Select):
    """`<select>` de Producto buscable también por nombre de proveedor."""

    def __init__(self, attrs=None, choices=()):
        base = {"data-select-buscable": "1"}
        base.update(attrs or {})
        super().__init__(base, choices)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex, attrs)
        instancia = getattr(value, "instance", None)
        if instancia is not None:
            try:
                provs = ", ".join(p.razon_social for p in instancia.proveedores.all())
            except Exception:  # noqa: BLE001 — un select nunca debe tumbar el form
                provs = ""
            if provs:
                opcion["attrs"]["data-buscar"] = provs
        return opcion


__all__ = ["SelectProductoBuscable"]
