"""Proveedor — CRM de proveedores en El Catálogo (S-LC-Feedback-V3).

Cada Servicio puede tener una lista M2M de proveedores que lo surten.
El detalle del producto muestra los proveedores aplicables.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Proveedor(models.Model):
    razon_social = models.CharField(max_length=200, db_index=True)
    nombre_contacto = models.CharField(max_length=120, blank=True, default="")
    email_contacto = models.EmailField(blank=True, default="")
    telefono = models.CharField(max_length=40, blank=True, default="")
    rfc = models.CharField(max_length=20, blank=True, default="")
    direccion = models.TextField(blank=True, default="")
    notas = models.TextField(blank=True, default="")

    activo = models.BooleanField(default=True, db_index=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="proveedores_creados",
    )

    class Meta:
        db_table = "catalogo_proveedor"
        ordering = ["razon_social"]
        verbose_name = "proveedor"
        verbose_name_plural = "proveedores"

    def __str__(self) -> str:
        return self.razon_social
