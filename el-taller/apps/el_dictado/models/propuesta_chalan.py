from __future__ import annotations

from django.conf import settings
from django.db import models


class PropuestaChalan(models.Model):
    """Sugerencia PROACTIVA de El Chalán para un usuario (Fase 3).

    A diferencia de `SugerenciaKPI` (que es específica de KPIs), ésta es
    genérica: la generan los *scouts* por cron (facturas vencidas, proyectos
    estancados, mandados sin avance, etc.) y el digest matutino. El Chalán
    redacta el texto con herramientas read-only; si la sugerencia implica
    ESCRITURAS, se materializan como un `Dictado(origen='chalan_proactivo')`
    pendiente — el usuario lo confirma en el preview estándar. NUNCA se aplica
    sola (respeta la regla de que El Chalán propone, no actúa).

    `clave_dedup` da idempotencia: un scout que vuelve a correr no duplica la
    propuesta de la misma condición (ej. `factura_vencida:123`). El
    `unique_together (usuario, clave_dedup)` lo garantiza a nivel DB.
    """

    ESTADOS = (
        ("pendiente", "Pendiente"),
        ("vista", "Vista"),
        ("aplicada", "Aplicada"),
        ("descartada", "Descartada"),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="propuestas_chalan",
    )
    tipo = models.CharField(max_length=40, db_index=True)
    clave_dedup = models.CharField(max_length=120, db_index=True)

    titulo = models.CharField(max_length=160)
    cuerpo = models.TextField(blank=True, default="")
    url = models.CharField(max_length=300, blank=True, default="")

    # Si la propuesta implica cambios, se materializa como un Dictado pendiente.
    dictado = models.ForeignKey(
        "el_dictado.Dictado",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="propuestas",
    )

    chalan = models.CharField(max_length=30, blank=True, default="")
    estado = models.CharField(max_length=20, choices=ESTADOS, default="pendiente", db_index=True)

    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "el_dictado_propuesta_chalan"
        unique_together = [("usuario", "clave_dedup")]
        indexes = [models.Index(fields=["usuario", "estado"])]
        ordering = ["-creada_en"]

    def __str__(self) -> str:
        return f"propuesta#{self.pk} u={self.usuario_id} {self.tipo} {self.estado}"
