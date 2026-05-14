import secrets

from django.conf import settings
from django.db import models

# Enum expandido para giro diseño/maquila:
# - cotizado: entre prospecto y arranque (ventana comercial S2).
# - revision_cliente: bottleneck típico waiting-on-client.
# - en_pausa: insumos atrasados, cliente que desaparece (lateral, reversible).
# - cancelado: terminal.
ESTADOS_PROYECTO = (
    ("prospecto", "Prospecto"),
    ("cotizado", "Cotizado"),
    ("en_diseno", "En diseño"),
    ("revision_cliente", "Revisión cliente"),
    ("en_produccion", "En producción"),
    ("entregado", "Entregado"),
    ("en_pausa", "En pausa"),
    ("cancelado", "Cancelado"),
)

ESTADOS_TERMINALES = {"entregado", "cancelado"}


def generar_codigo_proyecto() -> str:
    """Genera PRY-NNNNNN aleatorio. Se verifica unicidad en save()."""
    return f"PRY-{secrets.randbelow(900000) + 100000}"


class Proyecto(models.Model):
    codigo = models.CharField(max_length=12, unique=True, db_index=True, default=generar_codigo_proyecto)
    nombre = models.CharField(max_length=200)
    cliente = models.ForeignKey("cartera.Cliente", on_delete=models.PROTECT, related_name="proyectos")
    descripcion = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=20, choices=ESTADOS_PROYECTO, default="prospecto", db_index=True)

    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_compromiso = models.DateField(null=True, blank=True)
    fecha_real_entrega = models.DateField(null=True, blank=True)

    monto_estimado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="proyectos_creados",
    )

    class Meta:
        db_table = "proyectos_proyecto"
        verbose_name = "proyecto"
        verbose_name_plural = "proyectos"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    def save(self, *args, **kwargs):
        # Garantía de unicidad del código autogenerado: hasta 5 intentos.
        if not self.pk and self.codigo:
            for _ in range(5):
                if not Proyecto.objects.filter(codigo=self.codigo).exists():
                    break
                self.codigo = generar_codigo_proyecto()
        super().save(*args, **kwargs)

    @property
    def es_terminal(self) -> bool:
        return self.estado in ESTADOS_TERMINALES
