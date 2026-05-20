from django.conf import settings
from django.db import models
from django.utils.text import slugify

NATURALEZAS = (
    ("proyecto", "Asociable a proyecto"),
    ("operativo", "Operación general"),
    ("mixto", "Cualquiera"),
)


class CentroDeCosto(models.Model):
    """Catálogo de centros de costo. CRUD vive en La Gerencia → Catálogos;
    Tesorería sólo los lee (FK PROTECT desde Egreso)."""

    nombre = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=300, blank=True, default="")
    naturaleza = models.CharField(max_length=20, choices=NATURALEZAS, default="mixto")
    activo = models.BooleanField(default=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="centros_costo_creados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tesoreria_centro_de_costo"
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["activo"]),
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nombre)[:80] or "centro"
            slug, n = base, 1
            while CentroDeCosto.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                n += 1
                slug = f"{base}-{n}"[:80]
            self.slug = slug
        super().save(*args, **kwargs)
