"""El Directorio — CRUD de usuarios internos. Solo super_admin y dueño."""

import contextlib

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from cuentas.models.permiso_usuario import PermisoUsuario
from cuentas.models.usuario import Usuario
from lib.permisos import requires_role
from lib.permisos_defaults import DEFAULTS_POR_ROL
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import UsuarioForm


@requires_role("super_admin", "dueno")
def lista(request):
    from django.db.models import Count

    from lib.graficas import donut_desde_conteo

    qs = Usuario.objects.all().order_by("nombre_completo")
    activos = Usuario.objects.filter(is_active=True).count()
    total = Usuario.objects.count()
    por_rol = dict(
        Usuario.objects.filter(is_active=True)
        .values_list("rol").annotate(c=Count("id")).values_list("rol", "c")
    )
    etiquetas = {
        "super_admin": "Super admin", "dueno": "Admin",
        "contador": "Contador", "disenador": "Diseñador",
    }
    kpis = {
        "activos": activos,
        "inactivos": total - activos,
        "admins": por_rol.get("super_admin", 0) + por_rol.get("dueno", 0),
        "total": total,
    }
    return render(request, "directorio/lista.html", {
        "usuarios": qs,
        "kpis": kpis,
        "donut_roles_json": donut_desde_conteo(por_rol, etiquetas=etiquetas),
        "cabeceras_directorio": [
            {"label": "Nombre"},
            {"label": "Email"},
            {"label": "Rol"},
            {"label": "Estado"},
            {"label": "", "align": "right"},
        ],
    })


@requires_role("super_admin", "dueno")
@require_http_methods(["GET", "POST"])
def crear(request):
    if request.method == "POST":
        form = UsuarioForm(request.POST)
        if form.is_valid():
            u = form.save()
            emitir(EventoPortavoz(
                tipo="usuario.creado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"usuario_id": u.pk, "email": u.email, "rol": u.rol},
            ))
            messages.success(request, f"Usuario {u.email} creado.")
            return redirect("directorio-lista")
    else:
        form = UsuarioForm()
    return render(request, "directorio/form.html", {"form": form, "modo": "crear"})


@requires_role("super_admin", "dueno")
@require_http_methods(["GET", "POST"])
def editar(request, pk: int):
    u = get_object_or_404(Usuario, pk=pk)
    if request.method == "POST":
        form = UsuarioForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario actualizado.")
            return redirect("directorio-lista")
    else:
        form = UsuarioForm(instance=u)
    return render(request, "directorio/form.html", {"form": form, "modo": "editar", "usuario": u})


@requires_role("super_admin", "dueno")
@require_http_methods(["POST"])
def bloquear(request, pk: int):
    u = get_object_or_404(Usuario, pk=pk)
    if u.pk == request.user.pk:
        messages.error(request, "No puedes bloquearte a ti mismo.")
        return redirect("directorio-lista")
    u.is_active = not u.is_active
    u.save(update_fields=["is_active"])
    if not u.is_active:
        emitir(EventoPortavoz(
            tipo="usuario.bloqueado",
            actor_id=request.user.pk,
            actor_email=request.user.email,
            payload={"usuario_id": u.pk, "email": u.email},
        ))
    messages.success(request, f"Usuario {'activado' if u.is_active else 'bloqueado'}.")
    return redirect("directorio-lista")


# ── Permisos granulares (Pre-S2b.1) ─────────────────────────────────────────


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def permisos(request, pk: int):
    """UI de gestión de PermisoUsuario para un usuario específico."""
    u = get_object_or_404(Usuario, pk=pk)
    defaults_rol = DEFAULTS_POR_ROL.get(u.rol, {})

    if request.method == "POST":
        if "restablecer" in request.POST:
            # Borra todo y vuelve a sembrar.
            PermisoUsuario.objects.filter(usuario=u).delete()
            for modulo, permisos_lista in defaults_rol.items():
                for permiso in permisos_lista:
                    PermisoUsuario.objects.create(
                        usuario=u, modulo=modulo, permiso=permiso, activo=True,
                        modificado_por=request.user,
                    )
        else:
            seleccionados = set(request.POST.getlist("permisos"))
            todos = []
            for modulo, permisos_lista in defaults_rol.items():
                for permiso in permisos_lista:
                    todos.append((modulo, permiso))
            for modulo, permiso in todos:
                clave = f"{modulo}.{permiso}"
                activo = clave in seleccionados
                PermisoUsuario.objects.update_or_create(
                    usuario=u, modulo=modulo, permiso=permiso,
                    defaults={"activo": activo, "modificado_por": request.user},
                )
        with contextlib.suppress(Exception):
            emitir(EventoPortavoz(
                tipo="permisos.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"usuario_id": u.pk, "email": u.email},
            ))
        messages.success(request, f"Permisos de {u.email} actualizados.")
        return redirect("directorio-permisos", pk=u.pk)

    # GET: construye estructura {modulo: [(permiso, activo), ...]}
    activos = {
        (p.modulo, p.permiso): p.activo
        for p in PermisoUsuario.objects.filter(usuario=u)
    }
    secciones = []
    for modulo, permisos_lista in defaults_rol.items():
        filas = [(p, activos.get((modulo, p), True)) for p in permisos_lista]
        secciones.append((modulo, filas))

    return render(request, "directorio/permisos.html", {
        "usuario": u, "secciones": secciones,
    })


# ── S-LC-Feedback-V5 c7: CRUD de Roles personalizados ─────────────


@requires_role("super_admin")
def roles_lista(request):
    from cuentas.models.rol import Rol
    roles = Rol.objects.all().order_by("sistema", "nombre")
    return render(request, "directorio/roles_lista.html", {"roles": roles})


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def rol_nuevo(request):
    import json as _json

    from cuentas.models.rol import Rol
    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        descripcion = (request.POST.get("descripcion") or "").strip()
        permisos_raw = (request.POST.get("permisos_json") or "{}").strip()
        if not nombre:
            messages.error(request, "El nombre del rol es obligatorio.")
            return render(request, "directorio/rol_form.html", {"modo": "nuevo", "nombre": nombre, "descripcion": descripcion, "permisos_json": permisos_raw})
        try:
            permisos = _json.loads(permisos_raw) if permisos_raw else {}
        except _json.JSONDecodeError as e:
            messages.error(request, f"Permisos JSON inválido: {e}")
            return render(request, "directorio/rol_form.html", {"modo": "nuevo", "nombre": nombre, "descripcion": descripcion, "permisos_json": permisos_raw})
        if Rol.objects.filter(nombre=nombre).exists():
            messages.error(request, f"Ya existe un rol llamado «{nombre}».")
            return render(request, "directorio/rol_form.html", {"modo": "nuevo", "nombre": nombre, "descripcion": descripcion, "permisos_json": permisos_raw})
        rol = Rol.objects.create(nombre=nombre, descripcion=descripcion, permisos=permisos, sistema=False)
        emitir(EventoPortavoz(
            tipo="rol.creado", actor_id=request.user.pk, actor_email=request.user.email,
            payload={"rol_id": rol.pk, "nombre": rol.nombre},
        ))
        messages.success(request, f"Rol «{rol.nombre}» creado.")
        return redirect("directorio-roles")
    return render(request, "directorio/rol_form.html", {"modo": "nuevo", "permisos_json": "{}"})


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def rol_editar(request, pk: int):
    import json as _json

    from cuentas.models.rol import Rol
    rol = get_object_or_404(Rol, pk=pk)
    if request.method == "POST":
        if rol.sistema and rol.nombre == "super_admin":
            messages.error(request, "El rol super_admin del sistema no se puede editar.")
            return redirect("directorio-roles")
        descripcion = (request.POST.get("descripcion") or "").strip()
        permisos_raw = (request.POST.get("permisos_json") or "{}").strip()
        try:
            permisos = _json.loads(permisos_raw) if permisos_raw else {}
        except _json.JSONDecodeError as e:
            messages.error(request, f"Permisos JSON inválido: {e}")
            return render(request, "directorio/rol_form.html", {"modo": "editar", "rol": rol, "nombre": rol.nombre, "descripcion": descripcion, "permisos_json": permisos_raw})
        rol.descripcion = descripcion
        rol.permisos = permisos
        rol.save()
        emitir(EventoPortavoz(
            tipo="rol.actualizado", actor_id=request.user.pk, actor_email=request.user.email,
            payload={"rol_id": rol.pk, "nombre": rol.nombre},
        ))
        messages.success(request, f"Rol «{rol.nombre}» actualizado.")
        return redirect("directorio-roles")
    return render(request, "directorio/rol_form.html", {
        "modo": "editar", "rol": rol,
        "nombre": rol.nombre,
        "descripcion": rol.descripcion,
        "permisos_json": __import__("json").dumps(rol.permisos, indent=2, ensure_ascii=False),
    })


@requires_role("super_admin")
@require_http_methods(["POST"])
def rol_borrar(request, pk: int):
    from cuentas.models.rol import Rol
    rol = get_object_or_404(Rol, pk=pk)
    if rol.sistema:
        messages.error(request, f"El rol sistema «{rol.nombre}» no se puede borrar.")
        return redirect("directorio-roles")
    nombre = rol.nombre
    rol.delete()
    emitir(EventoPortavoz(
        tipo="rol.borrado", actor_id=request.user.pk, actor_email=request.user.email,
        payload={"nombre": nombre},
    ))
    messages.success(request, f"Rol «{nombre}» borrado.")
    return redirect("directorio-roles")


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def asignar_roles_extra(request, pk: int):
    from cuentas.models.rol import Rol
    u = get_object_or_404(Usuario, pk=pk)
    if request.method == "POST":
        ids = request.POST.getlist("roles_extra")
        u.roles_extra.set(Rol.objects.filter(pk__in=ids))
        emitir(EventoPortavoz(
            tipo="usuario.roles_extra_actualizados", actor_id=request.user.pk, actor_email=request.user.email,
            payload={"usuario_id": u.pk, "roles_ids": list(ids)},
        ))
        messages.success(request, f"Roles extra actualizados para {u.nombre_completo}.")
        return redirect("directorio-asignar-roles-extra", pk=u.pk)
    return render(request, "directorio/asignar_roles_extra.html", {
        "usuario": u,
        "roles_disponibles": Rol.objects.all().order_by("sistema", "nombre"),
        "roles_actuales_ids": set(u.roles_extra.values_list("pk", flat=True)),
    })
