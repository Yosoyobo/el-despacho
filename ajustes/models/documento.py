"""ConfiguracionDocumento — cómo se arman los PDF que ve el cliente.

Regla del proyecto: si algo se puede configurar, vive en un GUI de Gerencia
(Oscar, 2026-08-24: «debemos ser capaces de editar todo lo posible de los PDFs
en el GUI de la gerencia»). Estos valores estaban como constantes en
`apps.cotizaciones.services` y sólo se podían mover con un despliegue.

Qué se gana además de la comodidad: **el motor se puede cambiar desde la
pantalla**. Si los documentos salen mal con Chromium, se vuelve a Google con
un clic en vez de esperar a que pase un despliegue completo — que es
exactamente lo que uno quiere tener a mano el día que un formato se rompe
frente a un cliente.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

#: 72 puntos = 1 pulgada. Los márgenes se guardan en puntos porque es la
#: unidad en la que está escrito el resto del código del documento.
PT_POR_PULGADA = 72

MOTOR_AUTO = "auto"
MOTOR_GOTENBERG = "gotenberg"
MOTOR_GOOGLE = "google"

MOTORES = [
    (MOTOR_AUTO, "Automático — Chromium si está disponible, si no Google"),
    (MOTOR_GOTENBERG, "Sólo Chromium (aquí en el servidor)"),
    (MOTOR_GOOGLE, "Sólo Google Docs (como antes)"),
]

TAMANO_CARTA = "carta"
TAMANO_OFICIO = "oficio"
TAMANO_A4 = "a4"

#: Ancho y alto en pulgadas.
TAMANOS = {
    TAMANO_CARTA: (8.5, 11.0),
    TAMANO_OFICIO: (8.5, 13.0),
    TAMANO_A4: (8.27, 11.69),
}

TAMANOS_CHOICES = [
    (TAMANO_CARTA, "Carta (21.6 × 27.9 cm)"),
    (TAMANO_OFICIO, "Oficio (21.6 × 33 cm)"),
    (TAMANO_A4, "A4 (21 × 29.7 cm)"),
]


class ConfiguracionDocumento(models.Model):
    """Singleton (id=1) con la forma de los PDF de cotizaciones y facturas."""

    motor = models.CharField(
        max_length=16, choices=MOTORES, default=MOTOR_AUTO,
        help_text=(
            "Quién arma el PDF. Déjalo en automático salvo que estés "
            "diagnosticando algo: Chromium respeta los márgenes y numera las "
            "páginas de verdad; Google es el camino anterior."
        ),
    )

    tamano_papel = models.CharField(
        max_length=10, choices=TAMANOS_CHOICES, default=TAMANO_CARTA,
        help_text="Tamaño de la hoja. En México casi todo va en carta.",
    )

    # ── Márgenes, en puntos (72 = 1 pulgada) ────────────────────────────────
    margen_superior_pt = models.PositiveSmallIntegerField(
        default=36, validators=[MaxValueValidator(216)],
        help_text=(
            "Aire entre el borde de arriba y donde empieza el logotipo. "
            "36 son media pulgada; 72, una pulgada."
        ),
    )
    margen_inferior_pt = models.PositiveSmallIntegerField(
        default=43, validators=[MaxValueValidator(216)],
        help_text="Aire hasta el borde de abajo. El pie de página vive dentro de este margen.",
    )
    margen_izquierdo_pt = models.PositiveSmallIntegerField(
        default=72, validators=[MaxValueValidator(216)],
        help_text="Margen izquierdo. Súbelo si el documento se va a engargolar.",
    )
    margen_derecho_pt = models.PositiveSmallIntegerField(
        default=72, validators=[MaxValueValidator(216)],
        help_text="Margen derecho.",
    )

    # ── Pie de página ───────────────────────────────────────────────────────
    pie_texto = models.CharField(
        max_length=120, blank=True, default="",
        help_text=(
            "Texto chico al pie de cada hoja, alineado a la izquierda. "
            "Déjalo vacío si no quieres ninguno."
        ),
    )
    numerar_paginas = models.BooleanField(
        default=True,
        help_text=(
            "Muestra «1/3» a la derecha del pie. Con Chromium el número avanza "
            "de verdad; con Google todas las hojas dirían «1/1», que es la razón "
            "por la que este ajuste existe."
        ),
    )

    # ── Encabezado y marca de agua ──────────────────────────────────────────
    encabezado_texto = models.CharField(
        max_length=120, blank=True, default="",
        help_text=(
            "Texto chico arriba de cada hoja, alineado a la derecha. Útil para el "
            "nombre del despacho o un teléfono. Vacío = sin encabezado."
        ),
    )
    marca_borrador = models.CharField(
        max_length=30, blank=True, default="BORRADOR",
        help_text=(
            "Se estampa cruzada en las cotizaciones que aún no se han enviado, para "
            "que no se confundan con las que ya salieron. Vacío = sin marca."
        ),
    )

    # ── Tipografía del cuerpo ───────────────────────────────────────────────
    interlineado = models.DecimalField(
        max_digits=3, decimal_places=2, default=1.02,
        validators=[MinValueValidator(0.8), MaxValueValidator(2.0)],
        help_text=(
            "Qué tan pegados van los renglones. 1.02 es lo más apretado que se "
            "puede sin que los acentos se encimen; 1.5 es holgado."
        ),
    )

    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        "cuentas.Usuario", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "ajustes_config_documento"
        verbose_name = "configuración de documentos"
        verbose_name_plural = "configuración de documentos"

    def __str__(self) -> str:
        return f"Documentos · {self.get_tamano_papel_display()} · motor {self.motor}"

    @classmethod
    def obtener(cls) -> ConfiguracionDocumento:
        """La fila única, creándola con los defaults si no existe.

        Se crea al leer y NO con una migración de datos: una migración que
        inserta en la misma tabla cuyo índice acaba de crear es lo que tumbó el
        arranque el 2026-08-23 (§14 Bug I).
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # ── Lo que consume el generador ─────────────────────────────────────────

    @property
    def medidas_papel(self) -> tuple[float, float]:
        """(ancho, alto) en pulgadas."""
        return TAMANOS.get(self.tamano_papel, TAMANOS[TAMANO_CARTA])

    @property
    def alto_util_pt(self) -> int:
        """Alto de hoja menos los márgenes: lo que de verdad cabe de contenido.

        Lo usa el estimador que decide cuánto aire dejar antes de las notas. Si
        alguien sube los márgenes y esto no lo siguiera, el hueco quedaría mal
        calculado — que es justo el error que costó varias rondas en agosto.
        """
        _, alto_in = self.medidas_papel
        return int(alto_in * PT_POR_PULGADA) - self.margen_superior_pt - self.margen_inferior_pt

    def como_pagina(self) -> dict:
        """El diccionario que esperan `lib.gotenberg` y el camino de Google."""
        ancho_in, alto_in = self.medidas_papel
        return {
            "margen_superior_pt": self.margen_superior_pt,
            "margen_inferior_pt": self.margen_inferior_pt,
            "margen_izquierdo_pt": self.margen_izquierdo_pt,
            "margen_derecho_pt": self.margen_derecho_pt,
            # El pie y el encabezado viven DENTRO de sus márgenes, así que no le
            # quitan nada al contenido.
            "margen_pie_pt": 20,
            "margen_encabezado_pt": 12,
            "pie_texto": self.pie_texto,
            "encabezado_texto": self.encabezado_texto,
            "numerar_paginas": self.numerar_paginas,
            "ancho_in": ancho_in,
            "alto_in": alto_in,
            "interlineado": float(self.interlineado),
        }
