"""Andamio S2a.1 — Buzón de Clientes (UI completa en S5).

El modelo queda creado para que migraciones de S5 no requieran tocar schema en
producción con datos vivos. Sin UI activa: La Recepción muestra 'Próximamente'.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .mensaje_interno import ESTADO_CHOICES, TIPO_CHOICES


class MensajeBuzonCliente(models.Model):
    # FK lazy a Cliente/Proyecto para no acoplar buzon/ a el-taller (las apps
    # de El Taller no se cargan en La Recepción). En S5 la UI consulta vía
    # `cartera_cliente` / `proyectos_proyecto` por table name.
    cliente_id = models.BigIntegerField(db_index=True)
    proyecto_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    asunto = models.CharField(max_length=200)
    cuerpo = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="nuevo", db_index=True)

    nota_interna = models.TextField(blank=True, default="")
    respuesta_publica = models.TextField(blank=True, default="")
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="buzon_cliente_respondidos",
    )
    respondido_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "buzon_mensaje_cliente"
        ordering = ["-creado_en"]
        verbose_name = "mensaje del Buzón de Clientes"
        verbose_name_plural = "mensajes del Buzón de Clientes"
