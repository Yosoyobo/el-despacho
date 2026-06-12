"""ConfiguracionCobranza — política de recordatorios automáticos de cobranza.

Singleton (id=1). La Cobranza envía recordatorios por correo al CLIENTE
cuando una factura está vencida (o por vencer), vía El Cartero, usando la
plantilla `cobranza`. Esta config gobierna la cadencia.

**Por seguridad arranca DESACTIVADA** (`activa=False`): no queremos mandar
correos a clientes reales sin que el super_admin lo habilite explícitamente
desde La Gerencia → Ajustes → Cobranza.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class ConfiguracionCobranza(models.Model):
    # Singleton: siempre id=1 (ver obtener()).
    activa = models.BooleanField(
        default=False,
        help_text="Si está activa, el cron diario manda recordatorios a los clientes.",
    )
    dias_entre_recordatorios = models.PositiveSmallIntegerField(
        default=7,
        help_text="Días mínimos entre un recordatorio y el siguiente para la misma factura.",
    )
    max_recordatorios = models.PositiveSmallIntegerField(
        default=4,
        help_text="Máximo de recordatorios por factura (0 = sin límite).",
    )
    recordar_pre_vencimiento_dias = models.PositiveSmallIntegerField(
        default=0,
        help_text="Días ANTES del vencimiento para un aviso anticipado (0 = solo después de vencer).",
    )
    incluir_pdf = models.BooleanField(
        default=False,
        help_text="Adjuntar el PDF de la factura al recordatorio (requiere Google Drive).",
    )

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="config_cobranza_actualizadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_configuracion_cobranza"
        verbose_name = "configuración de cobranza"
        verbose_name_plural = "configuración de cobranza"

    def __str__(self) -> str:
        return f"ConfiguracionCobranza(activa={self.activa})"

    @classmethod
    def obtener(cls) -> ConfiguracionCobranza:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
