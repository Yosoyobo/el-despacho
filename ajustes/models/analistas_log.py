"""Bitácora de cada intento de Los Analistas.

Registra estación, provider, modelo, tokens, costo USD estimado, latencia y
éxito/error. NO guarda el prompt en claro — solo su hash SHA-256.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AnalistaLog(models.Model):
    estacion = models.CharField(max_length=40, db_index=True)
    provider = models.CharField(max_length=30, db_index=True)
    modelo = models.CharField(max_length=80, blank=True, default="")

    prompt_hash = models.CharField(max_length=64, db_index=True)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    costo_usd_estimado = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    latencia_ms = models.IntegerField(default=0)
    exito = models.BooleanField(default=False, db_index=True)
    mensaje_error = models.TextField(blank=True, default="")

    # Pre-S2b.1: marca cuando el intento fue posterior al primario configurado.
    es_fallback = models.BooleanField(default=False, db_index=True)
    proveedor_original = models.CharField(max_length=30, blank=True, default="")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analistas_logs",
    )
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ajustes_analistas_log"
        ordering = ["-creado_en"]
        verbose_name = "log de Los Analistas"
        verbose_name_plural = "logs de Los Analistas"

    def __str__(self) -> str:
        ok = "✓" if self.exito else "✗"
        return f"{ok} {self.estacion}/{self.provider} {self.creado_en:%Y-%m-%d %H:%M}"
