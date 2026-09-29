"""El historial de actividad de cada persona del equipo (2026-09-29).

La presencia (`Usuario.actividad_*`) dice dónde anda cada quien AHORA y se
sobrescribe; esto es lo que queda: un renglón por **pantalla que abre** y por
**acción que guarda algo**, más entradas y salidas. Decisiones de Oscar:

- **Qué se guarda**: pantallas y acciones. El sondeo automático no cuenta (mismo
  criterio que la presencia), y recargar la misma pantalla o autoguardar el mismo
  formulario en menos de un minuto no repite renglón.
- **Cuánto**: un año. `manage.py historial_actividad_purgar` borra lo más viejo
  cada noche.
- **Quién lo ve**: cada quien el suyo; el de otros, con `equipo.ver_historial`
  (nace para super_admin y dueño, se delega en El Directorio).

Se guarda lo CRUDO —ruta, nombre de la URL y sus argumentos— y el texto legible
se arma al mostrarlo (`lib.historial_actividad`), igual que la presencia: un
proyecto renombrado se lee con su nombre de hoy, y el nombre de un registro sólo
lo ve quien podría abrirlo.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class RegistroActividad(models.Model):
    PANTALLA = "pantalla"
    ACCION = "accion"
    ENTRADA = "entrada"
    SALIDA = "salida"
    TIPOS = [
        (PANTALLA, "Abrió una pantalla"),
        (ACCION, "Guardó algo"),
        (ENTRADA, "Entró"),
        (SALIDA, "Cerró sesión"),
    ]

    # La persona que está ahí de verdad. Durante una impersonación es el
    # super_admin, y a quién estaba mirando va en `como`.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="registros_actividad",
    )
    como = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    en = models.DateTimeField()
    tipo = models.CharField(max_length=10, choices=TIPOS)
    app = models.CharField(max_length=12, blank=True, default="")
    # La PANTALLA que la persona tenía enfrente (en una acción, desde dónde la hizo).
    ruta = models.CharField(max_length=300, blank=True, default="")
    url_name = models.CharField(max_length=120, blank=True, default="")
    kwargs = models.JSONField(blank=True, default=dict)
    # Sólo en una acción: a qué se le mandó el POST.
    destino = models.CharField(max_length=300, blank=True, default="")
    destino_url_name = models.CharField(max_length=120, blank=True, default="")
    metodo = models.CharField(max_length=8, blank=True, default="")
    ip = models.CharField(max_length=64, blank=True, default="")
    agente = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        db_table = "cuentas_registro_actividad"
        ordering = ["-en", "-pk"]
        indexes = [
            models.Index(fields=["usuario", "-en"], name="idx_regact_usuario_en"),
            # La purga nocturna borra por fecha, sin importar de quién.
            models.Index(fields=["en"], name="idx_regact_en"),
        ]

    def __str__(self) -> str:
        return f"{self.usuario_id} · {self.tipo} · {self.en:%Y-%m-%d %H:%M}"
