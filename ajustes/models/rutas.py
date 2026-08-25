"""ConfiguracionRutas — los números con los que el planeador estima la vuelta.

Regla del proyecto: si algo se puede configurar, vive en un GUI de Gerencia.
Los primeros cuatro estaban como constantes en `apps.el_pizarron.planeador` y
Oscar pidió sacarlos (2026-08-23). Los de abajo salieron del repaso del
2026-08-24 a lo que el mapa (OSRM) sabe hacer y no se le estaba pidiendo:
evitar casetas, evitar autopistas, llegar por la acera del cliente, y un factor
de tráfico sobre unos tiempos que el mapa calcula a calle libre.

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

    # ── Cómo mide el mapa (OSRM) ──────────────────────────────────────────────
    # Verificado contra el servidor: las exclusiones NO se combinan («Exclude
    # flag combination is not supported»), así que es UNA a la vez y por eso es
    # un menú y no dos casillas.
    EVITAR = (
        ("", "Nada — la ruta más rápida"),
        ("toll", "Evitar casetas"),
        ("motorway", "Evitar autopistas y vías rápidas"),
        ("ferry", "Evitar transbordadores"),
    )
    MODOS = (
        ("coche", "Coche o moto"),
        ("bici", "Bicicleta"),
    )

    evitar = models.CharField(
        max_length=12, choices=EVITAR, blank=True, default="",
        help_text=(
            "Qué esquivar al trazar la ruta. Evitar casetas suele salir un poco "
            "más largo y más lento, pero sin cobro. Sólo se puede elegir una: el "
            "mapa no tiene precocidas las combinaciones."
        ),
    )
    acera_del_cliente = models.BooleanField(
        default=False,
        help_text=(
            "Llegar por la acera donde está el cliente, para no cruzar la "
            "avenida con la caja. Alarga un poco la ruta cuando toca dar vuelta."
        ),
    )
    factor_trafico = models.DecimalField(
        max_digits=3, decimal_places=1, default=Decimal("1.0"),
        validators=[MinValueValidator(Decimal("1.0")), MaxValueValidator(Decimal("3.0"))],
        help_text=(
            "Multiplica los tiempos que calcula el mapa, que son de calle libre "
            "y sin tráfico. 1.0 los deja como vienen; 1.5 es hora pico de "
            "ciudad. No baja de 1: decir que se llega antes de lo que el mapa "
            "cree es al revés de lo que pasa en la calle."
        ),
    )
    modo = models.CharField(
        max_length=8, choices=MODOS, default="coche",
        help_text=(
            "Con qué se reparte. La bicicleta necesita su propio mapa cargado en "
            "el servidor; si no está, se mide como coche."
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
