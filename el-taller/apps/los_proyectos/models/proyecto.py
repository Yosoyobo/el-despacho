from django.conf import settings
from django.db import models, transaction

# Enum reflejando el ciclo real del despacho (LC, 2026-05-22).
ESTADOS_PROYECTO = (
    ("por_cotizar", "Por cotizar"),
    ("esperando_respuesta", "Esperando respuesta"),
    ("en_proceso_diseno", "En proceso de diseño"),
    ("en_proceso_produccion", "En proceso de producción"),
    ("entregado", "Entregado"),
    ("en_pausa", "En pausa"),
    ("cancelado", "Cancelado"),
)

ESTADOS_TERMINALES = {"entregado", "cancelado"}


def generar_codigo_proyecto() -> str:
    """Genera LC-NNNN correlativo (atómico vía select_for_update).

    Decisión S-LC-Feedback-V2: códigos correlativos LC-0001, LC-0002, … en
    lugar de PRY-NNNNNN aleatorio. Para go-live productivo existe el
    management command `resetear_contador_proyectos` que limpia demos y
    deja el contador en LC-0001.
    """
    with transaction.atomic():
        codigos = (
            Proyecto.objects.select_for_update()
            .filter(codigo__startswith="LC-")
            .values_list("codigo", flat=True)
        )
        max_n = 0
        for c in codigos:
            try:
                n = int(c.split("-", 1)[1])
                if n > max_n:
                    max_n = n
            except (ValueError, IndexError):
                continue
        return f"LC-{max_n + 1:04d}"


class Proyecto(models.Model):
    codigo = models.CharField(max_length=12, unique=True, db_index=True, default=generar_codigo_proyecto)
    # Slug para el Sistema de Referencias (#). Espejo del código en minúsculas.
    slug = models.CharField(max_length=80, unique=True)
    # S-LC-Feedback-V5 c9: el slug ahora se basa en el NOMBRE del proyecto.
    # El slug original (basado en código `lc-0001`) se preserva aquí para
    # resolver referencias `#lc-0001` en mensajes históricos.
    slug_legacy = models.CharField(max_length=80, null=True, blank=True, db_index=True)
    nombre = models.CharField(max_length=200)
    cliente = models.ForeignKey("cartera.Cliente", on_delete=models.PROTECT, related_name="proyectos")
    descripcion = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=24, choices=ESTADOS_PROYECTO, default="por_cotizar", db_index=True)

    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_compromiso = models.DateField(null=True, blank=True)
    fecha_real_entrega = models.DateField(null=True, blank=True)

    monto_estimado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Montos del ciclo comercial (terreno para El Pipeline — S2b).
    # monto_estimado arriba es la primera aproximación; los siguientes se llenan
    # conforme avanza el ciclo. En S2b llegan flujos automáticos.
    monto_cotizado = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Monto formal cotizado al cliente (puede diferir del estimado inicial).",
    )
    monto_facturado = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Suma de lo facturado al cliente para este proyecto.",
    )
    monto_cobrado = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Suma de lo efectivamente cobrado para este proyecto.",
    )
    fecha_ingreso_esperado = models.DateField(
        null=True, blank=True,
        help_text="Fecha en la que se espera cobrar el grueso del proyecto. Usada para proyecciones.",
    )

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
        # Si el código es el default y aún no se generó, hacerlo dentro de
        # la transacción para evitar colisiones bajo carga. generar_codigo_proyecto
        # ya hace select_for_update; aquí solo regeneramos si colisiona por
        # llamadas concurrentes que crearon mismo número antes del save.
        if not self.pk and self.codigo and self.codigo.startswith("LC-"):
            for _ in range(5):
                if not Proyecto.objects.filter(codigo=self.codigo).exists():
                    break
                self.codigo = generar_codigo_proyecto()
        if not self.slug:
            from lib.slug import generar_slug_proyecto
            self.slug = generar_slug_proyecto(self)
        super().save(*args, **kwargs)

    @property
    def es_terminal(self) -> bool:
        return self.estado in ESTADOS_TERMINALES
