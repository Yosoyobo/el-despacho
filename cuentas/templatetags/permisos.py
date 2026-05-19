"""Templatetags de permisos granulares (Pre-S2b.2).

Uso en templates:
    {% load permisos %}
    {% if request.user|puede:"buzon.ver_todos" %}
        <a href="/buzon/admin/">Bandeja admin</a>
    {% endif %}

    {# Equivalente con tag (cuando el módulo y la acción son variables) #}
    {% puede request.user "catalogo" "ver_precios" as ve_precios %}
    {% if ve_precios %} ... {% endif %}

Hookea `lib.permisos.puede()` (consulta la tabla `PermisoUsuario`).
"""

from __future__ import annotations

from django import template

from lib.permisos import puede as _puede

register = template.Library()


@register.filter(name="puede")
def filtro_puede(user, clave: str) -> bool:
    """`{{ user|puede:"modulo.accion" }}` — True/False."""
    if not clave or "." not in clave:
        return False
    modulo, accion = clave.split(".", 1)
    return _puede(user, modulo, accion)


@register.simple_tag(name="puede")
def tag_puede(user, modulo: str, accion: str) -> bool:
    """`{% puede user "modulo" "accion" as var %}` — para variables dinámicas."""
    return _puede(user, modulo, accion)
