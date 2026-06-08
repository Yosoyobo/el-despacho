from django.core.validators import RegexValidator
from django.db import models

HEX_COLOR = RegexValidator(
    regex=r"^#[0-9a-fA-F]{6}$",
    message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.",
)


class CategoriaServicio(models.Model):
    """Agrupación visual para servicios del Catálogo (Diseño, Impresión, etc.)."""

    nombre = models.CharField(max_length=80, unique=True)
    color = models.CharField(max_length=7, default="#667085", validators=[HEX_COLOR],
                             help_text="Color HEX del badge, ej. #465fff.")
    orden = models.IntegerField(default=100, db_index=True)
    activa = models.BooleanField(default=True, db_index=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalogo_categoria"
        ordering = ["orden", "nombre"]
        verbose_name = "categoría de servicio"
        verbose_name_plural = "categorías de servicio"

    def __str__(self) -> str:
        return self.nombre
