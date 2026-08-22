"""ConfiguracionAnalisis y TarifaRol — los números con los que El Análisis juzga.

Regla del proyecto: si algo se puede configurar, vive en un GUI de Gerencia.
Aquí viven los umbrales que El Chalán usa para decidir qué está bien y qué está
mal, en vez de tenerlos escritos en el código:

- Cuántos días de silencio convierten una cotización en oportunidad perdida.
- Qué margen se considera sano (debajo de ahí, el proyecto se marca).
- A partir de cuántos días de mora un cliente se vuelve un problema.
- Qué tan seguro tiene que estar el Chalán para activar solo lo que aprendió.

`TarifaRol` guarda el costo por hora de cada rol para poder costear la mano de
obra de un proyecto. Es la pieza que convierte horas trabajadas en dinero.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class ConfiguracionAnalisis(models.Model):
    """Singleton (id=1) con los umbrales de El Análisis."""

    # ── Ventas / oportunidades perdidas ──────────────────────────────────
    dias_silencio_cotizacion = models.PositiveSmallIntegerField(
        default=45,
        help_text=(
            "Días sin respuesta desde que se envió una cotización para darla "
            "por perdida. Cero = nunca se da por perdida sola."
        ),
    )
    marcar_perdidas_solo = models.BooleanField(
        default=False,
        help_text=(
            "Si está prendido, la cotización enfriada cambia de estado sola. "
            "Apagado (default): sólo se reporta y tú decides."
        ),
    )

    # ── Márgenes ─────────────────────────────────────────────────────────
    margen_sano_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("50.00"),
        help_text="% de margen que consideras sano. Debajo de esto el proyecto se marca.",
    )
    margen_critico_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="% de margen por debajo del cual el proyecto es una alarma roja.",
    )

    # ── Cobranza ─────────────────────────────────────────────────────────
    dias_mora_alerta = models.PositiveSmallIntegerField(
        default=30,
        help_text="Días de atraso en un pago para que el Chalán levante la mano.",
    )

    # ── Mano de obra ─────────────────────────────────────────────────────
    tarifa_hora_default = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text=(
            "Costo por hora que se usa cuando la persona no tiene tarifa por "
            "rol. Cero = no se cuesta la mano de obra de esa persona."
        ),
    )
    prorratear_jornada = models.BooleanField(
        default=True,
        help_text=(
            "Cuando no hay cronómetro de proyecto, repartir las horas de la "
            "jornada en partes iguales entre los proyectos que la persona tocó "
            "ese día. El resultado se marca como estimado, no como medido."
        ),
    )
    horas_jornada_tope = models.PositiveSmallIntegerField(
        default=12,
        help_text="Tope de horas que se le acreditan a una jornada al prorratear.",
    )

    # ── Aprendizaje del Chalán ───────────────────────────────────────────
    auto_activar_aprendizajes = models.BooleanField(
        default=True,
        help_text=(
            "Dejar que el Chalán active solo lo que aprendió cuando está muy "
            "seguro. Siempre te avisa y siempre se puede revertir."
        ),
    )
    confianza_minima_auto = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("0.85"),
        help_text="Qué tan seguro debe estar (0 a 1) para activar algo solo.",
    )
    dias_ventana_aprendizaje = models.PositiveSmallIntegerField(
        default=30,
        help_text="Cuántos días hacia atrás revisa cada vez que aprende.",
    )

    # ── Ritmo ────────────────────────────────────────────────────────────
    analisis_diario_activo = models.BooleanField(
        default=True,
        help_text="Correr la lectura del Chalán cada mañana. Apagado: sólo con el botón.",
    )

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="config_analisis_actualizadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_configuracion_analisis"
        verbose_name = "configuración de El Análisis"
        verbose_name_plural = "configuración de El Análisis"

    def __str__(self) -> str:
        return f"ConfiguracionAnalisis(margen_sano={self.margen_sano_pct}%)"

    @classmethod
    def obtener(cls) -> ConfiguracionAnalisis:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class TarifaRol(models.Model):
    """Costo por hora de un rol — para costear la mano de obra de un proyecto.

    Una persona con varios roles cuesta lo que cuesta su rol MÁS CARO: al
    costear conviene no quedarse corto. Si ninguno de sus roles tiene tarifa,
    se usa `ConfiguracionAnalisis.tarifa_hora_default`.
    """

    rol = models.OneToOneField(
        "cuentas.Rol", on_delete=models.CASCADE, related_name="tarifa",
    )
    costo_hora = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Cuánto le cuesta al despacho una hora de este rol.",
    )
    activo = models.BooleanField(default=True)

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tarifas_actualizadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_tarifa_rol"
        verbose_name = "tarifa por rol"
        verbose_name_plural = "tarifas por rol"
        ordering = ["rol__nombre"]

    def __str__(self) -> str:
        return f"{self.rol.nombre}: ${self.costo_hora}/h"
