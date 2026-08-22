"""PlantillaCorreo — cuerpo/asunto editables del correo de El Cartero.

Una fila por slug. Hay dos familias, y la diferencia importa:

- **De sistema** (`sistema=True`): las que dispara el propio código
  (`cotizacion`, `factura`, `cobranza`, `pago`, `bienvenida`, `generico`).
  Su contexto es fijo porque lo arma quien envía. No se borran: si
  desaparecieran, el envío correspondiente se quedaría sin cuerpo.
- **Propias** (`sistema=False`): las crea el usuario —o El Chalán— desde La
  Gerencia. Se eligen A MANO al enviar (ficha del cliente, campañas, El
  Chalán) o se atan a un evento con `ReglaCorreo`. Reciben el contexto común
  de `lib.correo_contexto`, así que pueden usar cualquier variable libre.

El cuerpo es HTML con variables `{{ }}`. El super_admin las edita gráficamente
(GrapesJS) en La Gerencia; si una fila de sistema queda vacía, El Cartero cae
al default de `ajustes.plantillas_correo_default`.

**Remitente por plantilla**: cada plantilla puede salir con su propia identidad
(`cobranza@learningcenter.mx`, `ventas@…`) en lugar del remitente global. Ojo
con el requisito de Gmail: el alias tiene que estar dado de alta en «Enviar
como» de la cuenta autenticada, o Gmail reescribe el From en silencio. Ver
`remitente_efectivo()`.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from ajustes.plantillas_correo_default import PLANTILLAS_DEFAULT

ORIGEN_PLANTILLA = (
    ("manual", "Creada a mano"),
    ("chalan", "Propuesta por El Chalán"),
    ("sistema", "Del sistema"),
)


class PlantillaCorreo(models.Model):
    slug = models.SlugField(max_length=40, unique=True, db_index=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Para qué sirve esta plantilla. Se ve al elegirla al enviar.",
    )
    asunto = models.CharField(max_length=300, blank=True, default="")
    cuerpo_html = models.TextField(blank=True, default="")
    activa = models.BooleanField(
        default=True,
        help_text="Una plantilla apagada no aparece al enviar ni la usa ninguna regla.",
    )
    # Las de sistema las dispara el código y no se pueden borrar.
    sistema = models.BooleanField(default=False, editable=False)
    origen = models.CharField(max_length=10, choices=ORIGEN_PLANTILLA, default="manual")

    # Identidad del remitente. Vacío = usa el remitente global de
    # ConfiguracionCorreo. Ver remitente_efectivo().
    remitente_email = models.EmailField(
        blank=True, default="",
        help_text="Alias desde el que sale este correo, ej. cobranza@learningcenter.mx. "
                  "Vacío = el remitente general. El alias debe estar dado de alta en "
                  "«Enviar como» de la cuenta de correo, o Gmail lo reescribe.",
    )
    remitente_nombre = models.CharField(
        max_length=120, blank=True, default="",
        help_text="Nombre visible de este remitente, ej. «Cobranza Learning Center».",
    )

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="plantillas_correo_actualizadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_plantilla_correo"
        ordering = ["-sistema", "nombre"]
        verbose_name = "plantilla de correo"
        verbose_name_plural = "plantillas de correo"

    def __str__(self) -> str:
        return f"PlantillaCorreo({self.slug})"

    # ── Consulta ─────────────────────────────────────────────────────────────

    @classmethod
    def obtener(cls, slug: str) -> PlantillaCorreo:
        """Fila del slug; la crea con el default si no existe. Idempotente.

        Sólo siembra contenido para los slugs de sistema: para uno propio que ya
        no exista devuelve una fila vacía, y `render()` cae al genérico.
        """
        defecto = PLANTILLAS_DEFAULT.get(slug, {})
        obj, _ = cls.objects.get_or_create(slug=slug, defaults={
            "nombre": defecto.get("nombre", slug.replace("-", " ").replace("_", " ").title()),
            "asunto": defecto.get("asunto", ""),
            "cuerpo_html": defecto.get("cuerpo_html", ""),
            "sistema": slug in PLANTILLAS_DEFAULT,
            "origen": "sistema" if slug in PLANTILLAS_DEFAULT else "manual",
        })
        return obj

    @classmethod
    def enviables(cls):
        """Plantillas que se pueden elegir para mandar algo hoy.

        Excluye las apagadas (incluidos los borradores que El Chalán deja sin
        revisar) y `generico`, que no se elige: es el molde del texto libre.
        """
        return cls.objects.filter(activa=True).exclude(slug="generico")

    # ── Render ───────────────────────────────────────────────────────────────

    @property
    def es_borrador(self) -> bool:
        """Propuesta de El Chalán que nadie ha revisado todavía."""
        return self.origen == "chalan" and not self.activa

    def remitente_efectivo(self) -> str:
        """`Nombre <correo>` con el que sale ESTE correo.

        Si la plantilla no declara alias, devuelve cadena vacía y El Cartero usa
        el remitente global. No se valida aquí que el alias exista en Gmail: eso
        se comprueba contra el servidor con `lib.cartero.verificar_remitente()`.
        """
        correo = (self.remitente_email or "").strip()
        if not correo:
            return ""
        nombre = (self.remitente_nombre or "").strip()
        return f"{nombre} <{correo}>" if nombre else correo

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
