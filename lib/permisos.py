"""Permisos centralizados — 4 roles, decoradores y helpers.

Roles:
- super_admin : todo, único que toca Los Ajustes.
- dueno       : todo operativo + reportes; NO Los Ajustes.
- contador    : Contaduría, Facturación, Caja, Cobranza, reportes financieros.
- disenador   : Proyectos y Pizarrón, restringido a sus asignaciones.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import wraps

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
        return True  # ve proyectos para reconciliar pagos (read-only enforced en vistas)
    if rol == "disenador":
        return proyecto.asignaciones.filter(usuario_id=user.pk).exists()
    return False


def puede_editar_proyecto(user, proyecto) -> bool:
    """Crear/editar/cambiar estado de proyectos: solo admins. Diseñadores
    pueden actuar sobre tareas pero no mutar el proyecto mismo."""
    return es_admin(user)


def puede_ver_cartera(user) -> bool:
    """Listar y ver clientes: admins + contador (read-only); diseñadores no."""
    return getattr(user, "rol", None) in ("super_admin", "dueno", "contador")


def puede_editar_cartera(user) -> bool:
    """Crear/editar/archivar clientes: solo admins."""
    return es_admin(user)


def puede_ver_tarea(user, tarea) -> bool:
    """Tareas: heredan la visibilidad del proyecto."""
    return puede_ver_proyecto(user, tarea.proyecto)


def puede_ver_comentario(user, comentario) -> bool:
    """Comentario interno: oculto a `disenador` salvo que sea el autor.
    Comentario público: visible si el usuario ve el proyecto/tarea padre."""
    rol = getattr(user, "rol", None)
    if rol in ("super_admin", "dueno", "contador"):
        return True
    if rol == "disenador":
        if comentario.es_interno and comentario.autor_id != getattr(user, "pk", None):
            return False
        proyecto = comentario.proyecto or (comentario.tarea.proyecto if comentario.tarea else None)
        if proyecto is None:
            return False
        return puede_ver_proyecto(user, proyecto)
    return False


def puede(usuario, modulo: str, permiso: str) -> bool:
    """Pre-S2b.1: consulta PermisoUsuario granular.

    Retorna True si la fila `(usuario, modulo, permiso)` existe y `activo=True`.
    Usuario inactivo siempre False. Si la tabla no existe aún o falla la
    consulta, retorna False defensivamente.
    """
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return False
    if not getattr(usuario, "is_active", True):
        return False
    try:
        from cuentas.models.permiso_usuario import PermisoUsuario
        return PermisoUsuario.objects.filter(
            usuario=usuario, modulo=modulo, permiso=permiso, activo=True
        ).exists()
    except Exception:
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
