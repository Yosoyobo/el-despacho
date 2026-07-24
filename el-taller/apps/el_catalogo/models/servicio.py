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
    # #12 (Sprint Fiscal 2026-07): unidad consolidada a 'pz'. Sin selector en
    # la UI; se conserva la columna por back-compat.
    unidad = models.CharField(max_length=30, default="pz")
    precio_base = models.DecimalField(max_digits=12, decimal_places=2)
    # S-LC-Feedback-V3: costo para cálculo de margen en proyectos/cotizaciones.
    costo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    categoria = models.ForeignKey(
        "el_catalogo.CategoriaServicio",
        on_delete=models.PROTECT,
        related_name="servicios",
    )
    activo = models.BooleanField(default=True, db_index=True)
    # LC 2026-07: imagen del producto (guardada en Google Drive, subcarpeta
    # "Productos"). Se sube por archivo o pegando desde el portapapeles.
    imagen_file_id = models.CharField(max_length=100, blank=True, default="")
    imagen_url = models.URLField(max_length=500, blank=True, default="")
    # S-LC-Feedback-V3: proveedores aplicables a este servicio.
    proveedores = models.ManyToManyField(
        "el_catalogo.Proveedor",
        blank=True,
        related_name="servicios",
    )
    # 2026-07: calculadora de costos por producto (usada solo por productos de
    # ciertos proveedores, p. ej. "Simil Cuero Plymouth"). Guarda los insumos
    # capturados: {"materiales": [4 montos], "sublimacion": [4 montos],
    # "mano_obra": monto, "factor": 2.2}. El subtotal (antes de IVA) alimenta
    # `precio_base`. Vacío = sin calculadora.
    detalles_costo = models.JSONField(default=dict, blank=True)

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

    @property
    def margen_porcentaje(self) -> float:
        """Margen calculado (precio_base - costo) / precio_base × 100.

        Si precio_base es 0, devuelve 0. Si costo es 0, devuelve 100.
        """
        if not self.precio_base or self.precio_base <= 0:
            return 0.0
        return float((self.precio_base - self.costo) / self.precio_base * 100)
