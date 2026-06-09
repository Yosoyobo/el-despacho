"""PlantillaCorreo — cuerpo/asunto editables del correo de El Cartero.

Una fila por slug (`cotizacion`, `factura`, `cobranza`, `generico`). El cuerpo
es HTML con variables `{{ }}` que El Cartero rellena con un contexto acotado.
El super_admin las edita gráficamente (GrapesJS) en La Gerencia; si una fila
no existe o queda vacía, El Cartero cae al default de
`ajustes.plantillas_correo_default`.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from ajustes.plantillas_correo_default import PLANTILLAS_DEFAULT


class PlantillaCorreo(models.Model):
    slug = models.SlugField(max_length=40, unique=True, db_index=True)
    nombre = models.CharField(max_length=120)
    asunto = models.CharField(max_length=300, blank=True, default="")
    cuerpo_html = models.TextField(blank=True, default="")
    activa = models.BooleanField(default=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="plantillas_correo_actualizadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_plantilla_correo"
        ordering = ["slug"]
        verbose_name = "plantilla de correo"
        verbose_name_plural = "plantillas de correo"

    def __str__(self) -> str:
        return f"PlantillaCorreo({self.slug})"

    @classmethod
    def obtener(cls, slug: str) -> PlantillaCorreo:
        """Fila del slug; la crea con el default si no existe. Idempotente."""
        defecto = PLANTILLAS_DEFAULT.get(slug, {})
        obj, _ = cls.objects.get_or_create(slug=slug, defaults={
            "nombre": defecto.get("nombre", slug.title()),
            "asunto": defecto.get("asunto", ""),
            "cuerpo_html": defecto.get("cuerpo_html", ""),
        })
        return obj

    def render(self, contexto: dict) -> tuple[str, str]:
        """Renderiza (asunto, cuerpo_html) con `contexto` vía el motor de Django.

        Si el cuerpo está vacío, usa el default del slug. Autoescape ON — el
        contexto es de strings simples, no HTML."""
        from django.template import Context, Template

        defecto = PLANTILLAS_DEFAULT.get(self.slug, {})
        cuerpo = self.cuerpo_html or defecto.get("cuerpo_html", "")
        asunto = self.asunto or defecto.get("asunto", "")
        ctx = Context(contexto)
        try:
            cuerpo_r = Template(cuerpo).render(ctx)
            asunto_r = Template(asunto).render(Context(contexto))
        except Exception:  # noqa: BLE001 — plantilla mal formada no tumba el envío
            cuerpo_r = Template(defecto.get("cuerpo_html", "")).render(ctx)
            asunto_r = Template(defecto.get("asunto", "")).render(Context(contexto))
        return asunto_r, cuerpo_r
