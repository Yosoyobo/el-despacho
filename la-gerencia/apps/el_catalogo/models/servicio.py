from django.conf import settings
from django.db import models


class ServicioActivosManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(activo=True)


class Servicio(models.Model):
    """Servicio frecuente del despacho (precio base + unidad + categoría).
    Se usa como sugerencia al armar líneas de Cotización en S2b."""

    nombre = models.CharField(max_length=150, db_index=True)
    descripcion_default = models.TextField(blank=True, default="")
    unidad = models.CharField(max_length=30, default="pieza")
    precio_base = models.DecimalField(max_digits=12, decimal_places=2)
    categoria = models.ForeignKey(
        "el_catalogo.CategoriaServicio",
        on_delete=models.PROTECT,
        related_name="servicios",
    )
    activo = models.BooleanField(default=True, db_index=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servicios_creados",
    )

    objects = models.Manager()
    activos = ServicioActivosManager()

    class Meta:
        db_table = "catalogo_servicio"
        ordering = ["categoria__orden", "nombre"]
        verbose_name = "servicio"
        verbose_name_plural = "servicios"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.categoria.nombre})"
