"""Estado de Novedades (changelog del manual) — S-Chalanes-UX #5.

- `LecturaNovedades` (per-usuario): qué claves de novedad ya vio cada quien.
  Alimenta el badge contador del sidebar y se limpia al abrir /ayuda/novedades.
- `NovedadAnunciada` (global): qué claves ya se notificaron por push masivo.
  El command `anunciar_novedades` empuja sólo las nuevas (idempotente).
"""

from __future__ import annotations

from django.db import models


class LecturaNovedades(models.Model):
    usuario = models.OneToOneField(
        "cuentas.Usuario", on_delete=models.CASCADE, related_name="lectura_novedades")
    claves_vistas = models.JSONField(default=list, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cuentas"

    def __str__(self):
        return f"LecturaNovedades({self.usuario_id})"


class NovedadAnunciada(models.Model):
    clave = models.CharField(max_length=90, unique=True)
    anunciada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cuentas"

    def __str__(self):
        return self.clave
