"""Directorio de Sedes / POI de Learning Center + modo de geocerca global.

Pedido de Oscar (S-LC-Feedback-V12): "en la gerencia debemos poder configurar
POI de LC, todas las sedes de las oficinas, como un directorio con su ubicación
y los límites de la geocerca configurada (Oficina 1, Oficina 2…). De esta forma
configuramos todas las ubicaciones válidas para LC".

Decisión Oscar: directorio GLOBAL (sedes compartidas) + modo Libre/Restringido.
La checada se valida contra CUALQUIER sede activa; el modo solo cambia si una
checada fuera de toda sede se ANOTA como observación. NUNCA bloquea la checada
(misma política no-bloqueante que la geocerca por-empleado de V7).
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from django.db import models


def distancia_m(lat1, lng1, lat2, lng2) -> float | None:
    """Haversine en metros entre dos coordenadas. None si falta alguna."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371000.0  # radio terrestre en metros
    la1, lo1, la2, lo2 = map(radians, (float(lat1), float(lng1), float(lat2), float(lng2)))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * r * asin(sqrt(h))


class SedeLC(models.Model):
    """Una ubicación válida de Learning Center (oficina, taller, sucursal…)."""

    nombre = models.CharField(max_length=120, help_text="Ej. Oficina 1, Taller Cuajimalpa.")
    direccion = models.TextField(blank=True, default="", help_text="Dirección visible.")
    # Pin geográfico (centro de la geocerca). Mismo formato que Usuario.geo_*.
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    radio_m = models.PositiveIntegerField(
        default=150, help_text="Radio de la geocerca en metros desde el pin.")
    activa = models.BooleanField(default=True, help_text="Si está activa, cuenta como ubicación válida.")
    orden = models.PositiveSmallIntegerField(default=100)
    notas = models.TextField(blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checador_sede"
        verbose_name = "sede de LC"
        verbose_name_plural = "sedes de LC"
        ordering = ["orden", "nombre"]

    def __str__(self) -> str:
        return self.nombre

    @property
    def tiene_pin(self) -> bool:
        return self.lat is not None and self.lng is not None

    def distancia_a_m(self, lat, lng):
        """Metros del pin de la sede a (lat, lng). None si no hay pin/coords."""
        if not self.tiene_pin:
            return None
        return distancia_m(self.lat, self.lng, lat, lng)

    def contiene(self, lat, lng) -> bool | None:
        """True/False si (lat,lng) cae dentro del radio, o None si no evaluable."""
        d = self.distancia_a_m(lat, lng)
        if d is None:
            return None
        return d <= (self.radio_m or 150)


class ConfiguracionGeocerca(models.Model):
    """Singleton (id=1) con el modo de geocerca del Checador.

    - libre:        no se valida ubicación; las checadas no se anotan por estar
                    fuera de sede (auditoría limpia). Es el default.
    - restringido:  una checada fuera de TODAS las sedes activas se ANOTA en la
                    jornada y emite evento para auditoría. Sigue sin bloquear.
    """

    MODOS = (
        ("libre", "Modo Libre — no valida ubicación"),
        ("restringido", "Modo Restringido — anota las checadas fuera de sede"),
    )
    modo = models.CharField(max_length=12, choices=MODOS, default="libre")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checador_config_geocerca"
        verbose_name = "configuración de geocerca"
        verbose_name_plural = "configuración de geocerca"

    def __str__(self) -> str:
        return self.get_modo_display()

    @classmethod
    def obtener(cls) -> ConfiguracionGeocerca:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
