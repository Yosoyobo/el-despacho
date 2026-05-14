"""Permisos centralizados — 4 roles, decoradores y helpers.

Roles:
- super_admin : todo, único que toca Los Ajustes.
- dueno       : todo operativo + reportes; NO Los Ajustes.
- contador    : Contaduría, Facturación, Caja, Cobranza, reportes financieros.
- disenador   : Proyectos y Pizarrón, restringido a sus asignaciones.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Iterable

from django.http import HttpRequest, HttpResponseForbidden
from django.shortcuts import redirect

ROLES = ("super_admin", "dueno", "contador", "disenador")
ROL_DEFAULT = "disenador"


def es_admin(user) -> bool:
    return getattr(user, "rol", None) in ("super_admin", "dueno")


def es_super_admin(user) -> bool:
    return getattr(user, "rol", None) == "super_admin"


def puede_ver_ajustes(user) -> bool:
    return es_super_admin(user)


def puede_ver_finanzas(user) -> bool:
    return getattr(user, "rol", None) in ("super_admin", "dueno", "contador")


def puede_ver_proyecto(user, proyecto) -> bool:
    rol = getattr(user, "rol", None)
    if rol in ("super_admin", "dueno"):
        return True
    if rol == "contador":
        return True  # ve proyectos para reconciliar pagos
    if rol == "disenador":
        return proyecto.asignados.filter(pk=user.pk).exists()
    return False


def requires_role(*roles: str) -> Callable:
    """Decorador para vistas Django. Si no autenticado → redirect a login;
    si autenticado pero rol no permitido → 403."""
    def wrap(view: Callable) -> Callable:
        @wraps(view)
        def inner(request: HttpRequest, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                login_url = getattr(request, "_login_url", "/sign-in")
                return redirect(login_url)
            if getattr(user, "rol", None) not in roles:
                return HttpResponseForbidden("Sin permisos para esta acción.")
            return view(request, *args, **kwargs)
        return inner
    return wrap


def requires_any_role(roles: Iterable[str]) -> Callable:
    return requires_role(*roles)
