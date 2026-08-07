from __future__ import annotations

from django.db import models

TIPOS_ACCION = (
    ("crear_proyecto", "Crear proyecto"),
    ("actualizar_proyecto", "Actualizar proyecto"),
    ("asignar_usuario_proyecto", "Asignar usuario a proyecto"),
    ("crear_cliente", "Crear cliente"),
    ("actualizar_cliente", "Actualizar cliente"),
    ("crear_tarea", "Crear tarea"),
    ("actualizar_tarea", "Actualizar tarea"),
    ("crear_cotizacion", "Crear cotización"),
    ("actualizar_cotizacion", "Actualizar cotización"),
    ("crear_factura", "Crear factura"),
    ("marcar_factura_cobrada", "Marcar factura cobrada"),
    ("registrar_ingreso", "Registrar ingreso"),
    ("registrar_egreso", "Registrar egreso"),
    ("crear_recado", "Crear recado"),
    ("crear_mensaje_buzon", "Crear mensaje en El Buzón"),
)


class DictadoAccion(models.Model):
    dictado = models.ForeignKey(
        "el_dictado.Dictado", on_delete=models.CASCADE, related_name="acciones"
    )
    orden = models.IntegerField()

    tipo = models.CharField(max_length=40, choices=TIPOS_ACCION)
    descripcion = models.CharField(max_length=300)
    payload = models.JSONField()

    entidad_tipo = models.CharField(max_length=30, blank=True, default="")
    entidad_id = models.BigIntegerField(null=True, blank=True)

    confianza = models.FloatField(default=1.0)
    confirmada = models.BooleanField(default=True)
    aplicada = models.BooleanField(default=False)
    error_al_aplicar = models.TextField(blank=True, default="")
    aplicada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "el_dictado_accion"
        ordering = ["dictado", "orden"]

    def __str__(self) -> str:
        return f"accion#{self.pk} {self.tipo} dictado={self.dictado_id}"

    # ── Presentación en el chat (LC 2026-08-04) ───────────────────────────────
    # La tarjeta de la acción se pinta con datos, no con la prosa del LLM: una
    # pastilla con el nombre de la acción y sus campos como pares legibles.
    @property
    def etiqueta_accion(self) -> str:
        """Nombre humano de la acción, para la pastilla («Crear proyecto»)."""
        from ..presentacion import titulo_accion
        return titulo_accion(self.tipo)

    @property
    def campos_visibles(self) -> list[dict]:
        """`[{etiqueta, valor}]` del payload, en orden de lectura."""
        from ..presentacion import campos_accion
        return campos_accion(self.tipo, self.payload)

    # LC 2026-08-07 (Oscar): en el resultado hay que saber QUÉ acción se logró o
    # falló, no sólo cuántas. Estas dos alimentan la fila del ✓/✕.
    @property
    def resumen_visible(self) -> str:
        """De qué era la acción: «Seguimiento de diseños»."""
        from ..presentacion import resumen_accion
        return resumen_accion(self.tipo, self.payload)

    @property
    def error_visible(self) -> str:
        """El motivo de la falla, recortado para la burbuja del chat."""
        from ..presentacion import error_legible
        return error_legible(self.error_al_aplicar)
