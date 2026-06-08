"""Permisos centralizados — 4 roles, decoradores y helpers.

Roles:
- super_admin : todo, único que toca Los Ajustes.
- dueno       : todo operativo + reportes; NO Los Ajustes.
- contador    : Contaduría, Facturación, Caja, Cobranza, reportes financieros.
- disenador   : Proyectos y Pizarrón, restringido a sus asignaciones.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterable
from functools import wraps

from django.http import HttpRequest, HttpResponseForbidden
from django.shortcuts import redirect

ROLES = ("super_admin", "dueno", "contador", "disenador")
ROL_DEFAULT = "disenador"


def roles_efectivos(user) -> set[str]:
    """S-LC-Feedback-V5 c7 / fix: unión del rol primario (`user.rol`) +
    los nombres de los `roles_extra` asignados.

    Es la base de los checks que gatean por **nombre de rol** (no por
    permiso granular). Sin esto los roles extra solo aplicaban al camino
    granular `puede()` y los helpers gruesos (`es_admin`,
    `puede_ver_finanzas`, etc.) los ignoraban — por eso "los roles no se
    aplicaban" al asignarlos. Defensivo: si el M2M no existe (modelo viejo
    o usuario sin guardar) devuelve solo el rol primario."""
    roles: set[str] = set()
    primario = getattr(user, "rol", None)
    if primario:
        roles.add(primario)
    with contextlib.suppress(Exception):
        roles.update(user.roles_extra.values_list("nombre", flat=True))
    return roles


def es_admin(user) -> bool:
    return bool(roles_efectivos(user) & {"super_admin", "dueno"})


def es_super_admin(user) -> bool:
    return "super_admin" in roles_efectivos(user)


def puede_ver_ajustes(user) -> bool:
    return es_super_admin(user)


def puede_ver_finanzas(user) -> bool:
    return bool(roles_efectivos(user) & {"super_admin", "dueno", "contador"})


def puede_ver_proyecto(user, proyecto) -> bool:
    roles = roles_efectivos(user)
    if roles & {"super_admin", "dueno", "contador"}:
        # contador ve proyectos para reconciliar pagos (read-only enforced en vistas)
        return True
    if "disenador" in roles:
        return proyecto.asignaciones.filter(usuario_id=user.pk).exists()
    return False


def puede_editar_proyecto(user, proyecto) -> bool:
    """Crear/editar/cambiar estado de proyectos: solo admins. Diseñadores
    pueden actuar sobre tareas pero no mutar el proyecto mismo."""
    return es_admin(user)


def puede_ver_cartera(user) -> bool:
    """Listar y ver clientes: admins + contador (read-only); diseñadores no."""
    return bool(roles_efectivos(user) & {"super_admin", "dueno", "contador"})


def puede_editar_cartera(user) -> bool:
    """Crear/editar/archivar clientes: solo admins."""
    return es_admin(user)


def puede_ver_tarea(user, tarea) -> bool:
    """Tareas: heredan la visibilidad del proyecto."""
    return puede_ver_proyecto(user, tarea.proyecto)


def puede_ver_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "ver")


def puede_crear_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "crear")


def puede_editar_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "editar")


def puede_enviar_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "enviar")


def puede_aprobar_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "aprobar")


def puede_rechazar_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "rechazar")


def puede_anular_cotizaciones(user) -> bool:
    return puede(user, "cotizaciones", "anular")


def puede_ver_facturacion(user) -> bool:
    return puede(user, "facturacion", "ver")


def puede_crear_facturacion(user) -> bool:
    return puede(user, "facturacion", "crear")


def puede_editar_facturacion(user) -> bool:
    return puede(user, "facturacion", "editar")


def puede_emitir_facturacion(user) -> bool:
    return puede(user, "facturacion", "emitir")


def puede_cobrar_facturacion(user) -> bool:
    return puede(user, "facturacion", "cobrar")


def puede_cancelar_facturacion(user) -> bool:
    return puede(user, "facturacion", "cancelar")


def puede_ver_contaduria(user) -> bool:
    return puede(user, "contaduria", "ver")


def puede_capturar_contaduria(user) -> bool:
    return puede(user, "contaduria", "capturar")


def puede_anular_contaduria(user) -> bool:
    return puede(user, "contaduria", "anular")


def puede_reportes_contaduria(user) -> bool:
    return puede(user, "contaduria", "reportes")


def puede_usar_chalan(user) -> bool:
    """S-Estados-Color-HEX: acceso al chat conversacional de El Chalán."""
    return puede(user, "chalan", "usar")


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

    S-LC-Feedback-V5 c7: además consulta `Usuario.roles_extra` — si
    cualquier rol extra del usuario contiene el permiso, retorna True.
    El PermisoUsuario individual con `activo=False` SIEMPRE gana (revoca
    incluso permisos heredados por roles).
    """
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return False
    if not getattr(usuario, "is_active", True):
        return False
    try:
        from cuentas.models.permiso_usuario import PermisoUsuario
        # Override individual (activo=False) revoca incluso permisos por rol extra.
        revocado = PermisoUsuario.objects.filter(
            usuario=usuario, modulo=modulo, permiso=permiso, activo=False
        ).exists()
        if revocado:
            return False
        # Activo individual → True directo.
        if PermisoUsuario.objects.filter(
            usuario=usuario, modulo=modulo, permiso=permiso, activo=True
        ).exists():
            return True
        # Fallback: roles extra del usuario (M2M Rol.permisos JSON).
        return any(
            permiso in (rol.permisos.get(modulo) or [])
            for rol in usuario.roles_extra.all()
        )
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
            if not (roles_efectivos(user) & set(roles)):
                return HttpResponseForbidden("Sin permisos para esta acción.")
            return view(request, *args, **kwargs)
        return inner
    return wrap


def requires_any_role(roles: Iterable[str]) -> Callable:
    return requires_role(*roles)
