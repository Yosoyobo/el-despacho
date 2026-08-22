"""La lectura que El Chalán hace de los números del negocio.

Los números de El Análisis salen de consultas: son exactos, gratis y se
recalculan cada vez que alguien abre la pantalla. Lo que sí cuesta es la
LECTURA — el "qué significa esto" — así que se genera una vez al día (o cuando
alguien pica «Analizar ahora») y se guarda aquí.

Guardarla, en vez de tenerla en caché, sirve para dos cosas: sobrevive a un
reinicio y deja ver cómo cambió la opinión del Chalán con el tiempo.
"""

from __future__ import annotations

from django.db import models


class LecturaAnalisis(models.Model):
    dominio = models.CharField(
        max_length=20, db_index=True,
        help_text="Tema del negocio (finanzas, cobranza, ventas…).",
    )
    texto = models.TextField(help_text="Lo que opinó El Chalán sobre este tema.")
    modelo_ia = models.CharField(max_length=80, blank=True, default="")
    generado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "taller_home_lectura_analisis"
        verbose_name = "lectura de El Análisis"
        verbose_name_plural = "lecturas de El Análisis"
        ordering = ["-generado_en"]
        indexes = [models.Index(fields=["dominio", "-generado_en"])]

    def __str__(self) -> str:
        return f"{self.dominio} · {self.generado_en:%Y-%m-%d %H:%M}"

    @classmethod
    def ultima(cls, dominio: str):
        return cls.objects.filter(dominio=dominio).order_by("-generado_en").first()

    @classmethod
    def ultimas(cls) -> dict[str, LecturaAnalisis]:
        """La lectura más reciente de cada tema, en una sola consulta."""
        salida: dict[str, LecturaAnalisis] = {}
        for fila in cls.objects.order_by("dominio", "-generado_en"):
            salida.setdefault(fila.dominio, fila)
        return salida
