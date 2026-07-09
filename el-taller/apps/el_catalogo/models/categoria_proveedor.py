"""Taxonomía de proveedores (LC 2026-07).

Dos niveles:
- `CategoriaProveedor`: 6 categorías CORE editables por el admin, cada una con
  color HEX. (Materiales, Confección, Impresión, Promocionales, Letreros,
  Servicios.)
- `SubcategoriaProveedor`: 19 subcategorías detalladas; cada una pertenece a una
  core y HEREDA su color. Un proveedor se etiqueta con una o varias
  subcategorías (M2M en `Proveedor.subcategorias`).
"""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

HEX_COLOR = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Usa un color HEX como #465FFF.")


class CategoriaProveedor(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)
    color = models.CharField(max_length=7, default="#667085", validators=[HEX_COLOR])
    orden = models.PositiveSmallIntegerField(default=100, db_index=True)
    activa = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "catalogo_categoria_proveedor"
        ordering = ["orden", "nombre"]
        verbose_name = "categoría de proveedor"
        verbose_name_plural = "categorías de proveedor"

    def __str__(self) -> str:
        return self.nombre


class SubcategoriaProveedor(models.Model):
    categoria = models.ForeignKey(
        CategoriaProveedor, on_delete=models.CASCADE, related_name="subcategorias",
    )
    nombre = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    orden = models.PositiveSmallIntegerField(default=100, db_index=True)
    activa = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "catalogo_subcategoria_proveedor"
        ordering = ["categoria__orden", "orden", "nombre"]
        verbose_name = "subcategoría de proveedor"
        verbose_name_plural = "subcategorías de proveedor"

    def __str__(self) -> str:
        return self.nombre

    @property
    def color(self) -> str:
        """Hereda el color de su categoría core (LC 2026-07)."""
        return self.categoria.color
