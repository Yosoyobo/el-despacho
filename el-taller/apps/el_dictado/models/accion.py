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
