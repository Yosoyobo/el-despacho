from __future__ import annotations

from django.conf import settings
from django.db import models

ESTADOS = (
    ("interpretando", "Interpretando con Chalán"),
    ("esperando_confirmacion", "Esperando confirmación"),
    ("preguntando", "Chalán pidió clarificación"),
    ("confirmado_parcial", "Confirmado con subset desmarcado"),
    ("confirmado_total", "Confirmado todas las acciones"),
    ("cancelado", "Cancelado por usuario"),
    ("fallo_ia", "Los Chalanes no disponibles"),
    ("aplicado", "Acciones ejecutadas"),
    ("aplicado_con_errores", "Algunas acciones fallaron"),
)

ORIGENES = (
    ("sala_juntas", "Sala de Juntas del Taller"),
    ("tesoreria_gasto", "Dictado de gasto en Tesorería"),
)


class Dictado(models.Model):
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="dictados",
    )
    texto_crudo = models.TextField()
    estado = models.CharField(max_length=30, choices=ESTADOS, default="interpretando", db_index=True)
    origen = models.CharField(max_length=30, choices=ORIGENES, default="sala_juntas")

    chalan = models.CharField(max_length=30, blank=True, default="")
    chalan_apodo = models.CharField(max_length=50, blank=True, default="")
    modelo = models.CharField(max_length=80, blank=True, default="")

    interpretacion_raw = models.JSONField(default=dict, blank=True)
    pregunta_clarificacion = models.TextField(blank=True, default="")

    latencia_interpretacion_ms = models.IntegerField(null=True, blank=True)
    costo_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0)

    creado_en = models.DateTimeField(auto_now_add=True)
    confirmado_en = models.DateTimeField(null=True, blank=True)
    aplicado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "el_dictado_dictado"
        indexes = [
            models.Index(fields=["autor", "-creado_en"]),
            models.Index(fields=["estado"]),
        ]
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"dictado#{self.pk} '{self.texto_crudo[:40]}'"
