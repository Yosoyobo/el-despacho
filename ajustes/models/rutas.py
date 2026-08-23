"""ConfiguracionRutas — los números con los que el planeador estima la vuelta.

Regla del proyecto: si algo se puede configurar, vive en un GUI de Gerencia.
Estos cuatro estaban como constantes en `apps.el_pizarron.planeador` y Oscar
pidió sacarlos (2026-08-23).

Por qué importan: de la velocidad y del tiempo por parada salen las **horas
estimadas** que ve el runner en su ruta. Con números que no se parecen a la
realidad, la ruta le promete horas que no va a cumplir — y entonces deja de
creerle. Ajustarlos es cosa de quien conoce la ciudad y el trabajo, no de quien
escribe el código.
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ConfiguracionRutas(models.Model):
    """Singleton (id=1) con los supuestos del planeador de rutas."""

    velocidad_kmh = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("25.0"),
        validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("200"))],
        help_text=(
            "Velocidad promedio para estimar cuánto se tarda entre paradas, en "
            "km/h. 25 es un promedio de ciudad con tráfico; súbela si la mayoría "
            "de las entregas son por carretera."
        ),
    )
    minutos_por_parada = models.PositiveSmallIntegerField(
        default=10,
        validators=[MaxValueValidator(240)],
        help_text=(
            "Lo que se tarda en cada parada: estacionarse, bajar, entregar, "
            "recabar firma. Se suma a cada tramo del recorrido."
        ),
    )
    hora_inicio = models.TimeField(
        default=time(9, 0),
        help_text=(
            "A qué hora se supone que arranca la vuelta si ninguna cita obliga "
            "antes. Una cita más temprana adelanta la salida sola."
        ),
    )
    max_paradas_por_ruta = models.PositiveSmallIntegerField(
        default=9,
        validators=[MinValueValidator(1), MaxValueValidator(25)],
        help_text=(
            "Tope de paradas por ruta. Nueve es lo que acepta el enlace de Google "
            "Maps con paradas intermedias; más que eso, el botón de «abrir en el "
            "mapa» deja fuera las últimas."
        ),
    )

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_config_rutas"
        verbose_name = "configuración de rutas"
        verbose_name_plural = "configuración de rutas"

    def __str__(self) -> str:
        return f"Rutas · {self.velocidad_kmh} km/h · {self.minutos_por_parada} min/parada"

    @classmethod
    def obtener(cls) -> ConfiguracionRutas:
        """La fila única, creándola con los defaults si no existe.

        Se crea al leer (no con una migración de datos) a propósito: una
        migración que INSERTA en la misma tabla cuyo índice acaba de crear es lo
        que tumbó el arranque el 2026-08-23 (§14 Bug I).
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
