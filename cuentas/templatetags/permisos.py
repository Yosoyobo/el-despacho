"""Templatetags de permisos granulares (Pre-S2b.2).

Uso en templates:
    {% load permisos %}
    {% if request.user|puede:"buzon.ver_todos" %}
        <a href="/buzon/admin/">Bandeja admin</a>
    {% endif %}

    {# Equivalente con tag (cuando el módulo y la acción son variables) #}
    {% puede request.user "catalogo" "ver_precios" as ve_precios %}
    {% if ve_precios %} ... {% endif %}

    {# El failsafe: lo único que se decide por rol (§4 #20) #}
    {% if user|es_super_admin %} ... {% endif %}

Hookea `lib.permisos.puede()` (consulta la tabla `PermisoUsuario`).
"""

from __future__ import annotations

from django import template

from lib.permisos import es_super_admin as _es_super_admin
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


@register.filter(name="es_super_admin")
def filtro_es_super_admin(user) -> bool:
    """`{{ user|es_super_admin }}` — el failsafe de `lib.permisos`: el único rol
    que decide algo (§4 #20). Mira los roles efectivos y respeta «ver como rol».
    Reemplaza a `user.rol == 'super_admin'` en las plantillas, que el candado
    `tests/test_permisos_sin_rol_literal.py` ya no deja escribir."""
    return _es_super_admin(user)
