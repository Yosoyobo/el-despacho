"""PromptVoz — voz/tono editable que se inyecta a los prompts de Los Chalanes.

Una fila por slot. `clave="base"` es el **Prompt base**: se antepone a TODAS
las estaciones (define tono, idioma y restricciones globales). Las demás
claves (`dictado`, `taller_chat`, `ocr_recibo`, `kpi_dsl`) son voces
opcionales que se inyectan SÓLO en esa estación.

La voz editable NO toca los prompts ESTRUCTURALES (esquemas JSON de acciones,
whitelist del DSL, schema de salida del OCR): esos son contrato con el código
y viven hardcodeados en su builder. La voz sólo ajusta tono y prioridades.

`contenido` vacío = comportamiento por defecto (no se inyecta nada).

El super_admin la edita desde `/chalanes/prompts/` (La Gerencia). La lectura
en caliente la hace `chalanes.voz.voz()` con caché de proceso.
"""

from __future__ import annotations

from django.db import models

# (clave, etiqueta, descripcion_ayuda) — el orden define el render del form;
# `base` siempre primero.
SLOTS_VOZ: tuple[tuple[str, str, str], ...] = (
    ("base", "Prompt base",
     "Personalidad e instrucciones generales. Se antepone a TODAS las "
     "llamadas (Dictado, Chat, OCR, KPIs). Define tono, idioma y "
     "restricciones globales."),
    ("dictado", "Voz al interpretar dictados",
     "Texto opcional inyectado al interpretar un dictado. NO toca el esquema "
     "de acciones — sólo ajusta tono y prioridades narrativas."),
    ("taller_chat", "Voz del chat (El Chalán)",
     "Tono y estilo del chat conversacional del Taller. NO toca las "
     "herramientas ni las acciones permitidas (eso lo gobierna el rol)."),
    ("ocr_recibo", "Voz al leer recibos",
     "Matiz al extraer datos de recibos. NO toca el esquema JSON de salida "
     "(es contrato con el código)."),
    ("kpi_dsl", "Voz al construir KPIs",
     "Tono al traducir preguntas a métricas. NO toca el whitelist del DSL."),
)

SLOTS_VOZ_DICT = {s[0]: {"etiqueta": s[1], "ayuda": s[2]} for s in SLOTS_VOZ}


class PromptVoz(models.Model):
    clave = models.CharField(max_length=40, unique=True, db_index=True)
    contenido = models.TextField(blank=True, default="")
    actualizado_por = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="prompt_voz_actualizados",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chalanes_prompt_voz"
        ordering = ["clave"]
        verbose_name = "voz de prompt"
        verbose_name_plural = "voces de prompt"

    def __str__(self) -> str:
        return f"PromptVoz({self.clave})"

    @property
    def etiqueta(self) -> str:
        return SLOTS_VOZ_DICT.get(self.clave, {}).get("etiqueta", self.clave)

    @property
    def ayuda(self) -> str:
        return SLOTS_VOZ_DICT.get(self.clave, {}).get("ayuda", "")
