"""Proveedores asignados a un proyecto, con su compromiso de entrega/recolección.

C5 S-LC-Feedback-V6. Distinto de los "proveedores aplicables" (derivados del
catálogo vía los servicios): aquí el equipo asigna explícitamente a quién le
encargó algo para ESTE proyecto, cuándo se comprometen a entregar (o cuándo
hay que recoger), con quién y dónde. Sirve para organizar/visualizar/mapear
pendientes.
"""

from __future__ import annotations

from django.db import models


class ProyectoProveedor(models.Model):
    TIPO_CHOICES = [
        ("entregan_ellos", "Ellos nos entregan"),
        ("recogemos_nosotros", "Nosotros recogemos"),
    ]

    proyecto = models.ForeignKey(
        "proyectos.Proyecto", on_delete=models.CASCADE, related_name="proveedores_asignados"
    )
    proveedor = models.ForeignKey(
        "el_catalogo.Proveedor", on_delete=models.PROTECT, related_name="proyectos_asignados"
    )
    tipo = models.CharField(max_length=24, choices=TIPO_CHOICES, default="entregan_ellos")
    # Fecha + hora del compromiso (default 12:00 PM en el form).
    compromiso = models.DateTimeField(
        null=True, blank=True,
        help_text="Cuándo se comprometen a entregar o cuándo hay que recoger.",
    )
    contacto = models.CharField(max_length=160, blank=True, default="")
    ubicacion = models.CharField(max_length=300, blank=True, default="")
    nota = models.CharField(max_length=300, blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proyectos_proveedor"
        ordering = ["compromiso", "creado_en"]
        verbose_name = "proveedor del proyecto"
        verbose_name_plural = "proveedores del proyecto"

    def __str__(self) -> str:
        return f"{self.proveedor.razon_social} · {self.get_tipo_display()}"
