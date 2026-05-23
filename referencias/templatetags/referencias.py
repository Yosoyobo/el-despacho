"""Templatetag `renderizar_referencias` — convierte texto plano con tokens
`@/#/$` en HTML con chips coloreados clickeables.

Uso en template:
    {% load referencias %}
    <div class="prose">{{ recado.cuerpo|renderizar_referencias|safe }}</div>

Colores semánticos (DOC_01 §5.3):
- `@` usuario   → text-brand-600 dark:text-brand-400
- `#` proyecto  → text-violet-600 dark:text-violet-400
- `$` cliente   → text-emerald-600 dark:text-emerald-400
- Roto          → text-gray-400 dark:text-gray-500 line-through

Itera de atrás hacia adelante para no romper offsets al substituir.
"""

from __future__ import annotations

from django import template
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from ..parser import extraer_tokens
from ..resolver import resolver_tokens

register = template.Library()

CLASES_POR_TIPO = {
    "usuario": "text-brand-600 dark:text-brand-400 hover:underline font-medium",
    "proyecto": "text-violet-600 dark:text-violet-400 hover:underline font-medium",
    "cliente": "text-emerald-600 dark:text-emerald-400 hover:underline font-medium",
}

CLASE_ROTO = "text-gray-400 dark:text-gray-500 line-through"


def _url_de(tipo: str, entidad) -> str:
    """URL absoluta hacia la entidad. Devuelve '#' si no se puede inferir."""
    if entidad is None:
        return "#"
    if tipo == "usuario":
        return f"/directorio/{entidad.pk}/"
    if tipo == "proyecto":
        return f"/proyectos/{entidad.pk}/"
    if tipo == "cliente":
        return f"/cartera/{entidad.pk}/"
    return "#"


def _etiqueta_visible(tipo: str, entidad) -> str:
    """S-LC-Feedback-V4: para `#proyecto` mostramos 'Nombre (LC-XXXX)' en lugar
    del slug crudo. Para `@usuario` el nombre completo; para `$cliente` la
    razón social. Si la entidad no expone nombre legible, fallback al slug.
    """
    if entidad is None:
        return ""
    if tipo == "proyecto":
        nombre = getattr(entidad, "nombre", "") or ""
        codigo = getattr(entidad, "codigo", "") or ""
        if nombre and codigo:
            return f"#{nombre} ({codigo})"
        if nombre:
            return f"#{nombre}"
        if codigo:
            return f"#{codigo}"
    if tipo == "usuario":
        nombre = (
            getattr(entidad, "nombre_completo", None)
            or getattr(entidad, "get_full_name", lambda: "")()
            or getattr(entidad, "email", "")
        )
        if nombre:
            return f"@{nombre}"
    if tipo == "cliente":
        nombre = getattr(entidad, "razon_social", "") or ""
        if nombre:
            return f"${nombre}"
    return ""


@register.filter(name="renderizar_referencias")
def renderizar_referencias(texto):
    """Reemplaza tokens por anchors con clases TailAdmin. HTML-escapa el texto
    base; las clases son confiables (constantes). Retorna SafeString."""
    if not texto:
        return ""
    texto = str(texto)
    tokens = extraer_tokens(texto)
    if not tokens:
        return escape(texto)

    resueltos = resolver_tokens(tokens)

    # Construye output recorriendo de izq→der: escape los segmentos planos,
    # inyecta anchors HTML-escapados para cada token.
    salida = []
    cursor = 0
    for t in tokens:
        if cursor < t.inicio:
            salida.append(escape(texto[cursor:t.inicio]))
        entidad = resueltos.get((t.tipo, t.slug))
        if entidad is None:
            salida.append(format_html(
                '<span class="{}">{}</span>',
                CLASE_ROTO, t.token_original,
            ))
        else:
            etiqueta = _etiqueta_visible(t.tipo, entidad) or t.token_original
            salida.append(format_html(
                '<a href="{}" class="{}" data-ref-tipo="{}" data-ref-slug="{}">{}</a>',
                _url_de(t.tipo, entidad),
                CLASES_POR_TIPO[t.tipo],
                t.tipo,
                t.slug,
                etiqueta,
            ))
        cursor = t.fin
    if cursor < len(texto):
        salida.append(escape(texto[cursor:]))
    return mark_safe("".join(salida))
