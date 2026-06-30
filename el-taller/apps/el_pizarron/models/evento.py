"""Evento genérico del calendario — S-LC-Feedback-V13.

NO está ligado a un proyecto: sirve para días feriados, vacaciones, eventos
operativos o generales. Puede durar varios días (fecha_inicio → fecha_fin) y
aparece en TODAS las celdas del rango en el Calendario. Visible para todo el
Taller (no se scopea por usuario — son eventos de la empresa).

Vive en `apps.el_pizarron` (label `pizarron`) porque es la app de agenda y ya
está instalada en ambos projects (solo La Gerencia corre migrate, §14 Bug B).
"""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

HEX_COLOR = RegexValidator(
    regex=r"^#[0-9a-fA-F]{6}$",
    message="Usa un color hexadecimal de 6 dígitos, ej. #465fff.",
)


class Evento(models.Model):
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default="")
    fecha_inicio = models.DateField(db_index=True)
    fecha_fin = models.DateField(db_index=True)
    color = models.CharField(max_length=7, default="#465fff", validators=[HEX_COLOR])
    creado_por = models.ForeignKey(
        "cuentas.Usuario", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="eventos_creados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pizarron_evento"
        ordering = ["fecha_inicio", "titulo"]
        verbose_name = "evento"
        verbose_name_plural = "eventos"

    def __str__(self) -> str:
        return self.titulo

    @property
    def es_multidia(self) -> bool:
        return bool(self.fecha_fin and self.fecha_inicio and self.fecha_fin > self.fecha_inicio)

    def save(self, *args, **kwargs):
        # fecha_fin nunca menor que inicio; vacía ⇒ mismo día.
        if self.fecha_fin is None:
            self.fecha_fin = self.fecha_inicio
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            self.fecha_fin = self.fecha_inicio
        super().save(*args, **kwargs)
