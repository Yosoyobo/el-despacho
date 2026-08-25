"""Cómo se comporta el archivo del papeleo — Paperless, desde La Gerencia.

Todo lo que decide un humano vive aquí y se edita en una pantalla, no en el
código: la dirección con la que se abre, si el papeleo que entra se liga solo
a su cliente, con qué etiqueta se marca lo que llega, y la contraseña con la
que el buzón empuja documentos.

La llave de la API no está en esta tabla: es una credencial y vive cifrada en
La Bóveda (§4 #3), en el slot `paperless_token`.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ConfiguracionPapeleo(models.Model):
    """Singleton (id=1) con los ajustes del archivo de papeleo."""

    url_publica = models.URLField(
        blank=True, default="",
        help_text=(
            "La dirección con la que se abre Paperless en el navegador — la de "
            "la red privada, por ejemplo http://100.121.244.5:8204. NO es la "
            "que usa el servidor por dentro: sin ésta, los enlaces a un "
            "documento no abren en ninguna máquina."
        ),
    )

    ligar_automatico = models.BooleanField(
        default=False,
        help_text=(
            "Cuando entra un documento, buscar en su texto a qué cliente, "
            "proveedor o proyecto se refiere y ligarlo solo. Sólo liga cuando "
            "no hay duda: si dos clientes coinciden, lo deja sin ligar para "
            "que alguien decida — adivinar sería peor que no ligar."
        ),
    )
    minimo_caracteres_nombre = models.PositiveSmallIntegerField(
        default=6,
        validators=[MinValueValidator(3), MaxValueValidator(40)],
        help_text=(
            "Qué tan largo tiene que ser un nombre para buscarlo en el texto. "
            "Con menos de seis letras, un nombre corto aparece por casualidad "
            "dentro de cualquier palabra y liga documentos que no son."
        ),
    )

    etiqueta_entrada = models.CharField(
        max_length=64, blank=True, default="El Despacho",
        help_text=(
            "Etiqueta que se le pone en Paperless a todo lo que entra desde El "
            "Despacho, para distinguirlo de lo que se escaneó a mano. Si no "
            "existe, se crea sola. Vacío = no se etiqueta."
        ),
    )

    avisar_al_entrar = models.BooleanField(
        default=False,
        help_text=(
            "Avisar por El Interfón cuando llega papeleo nuevo. Arranca apagado "
            "a propósito: si entran veinte remisiones el lunes, veinte avisos "
            "enseñan al equipo a ignorarlos."
        ),
    )

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_config_papeleo"
        verbose_name = "configuración del papeleo"
        verbose_name_plural = "configuración del papeleo"

    def __str__(self) -> str:
        estado = "liga solo" if self.ligar_automatico else "liga a mano"
        return f"Papeleo · {estado}"

    @classmethod
    def obtener(cls) -> ConfiguracionPapeleo:
        """La fila única, creándola con los defaults si no existe.

        Se crea al leer y no con una migración de datos a propósito: una
        migración que INSERTA en la misma tabla cuyo índice acaba de crear es
        lo que tumbó el arranque el 2026-08-23 (§14 Bug I).
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
