"""El Directorio — CRUD de usuarios internos. Solo super_admin y dueño."""

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
    qs = Usuario.objects.all().order_by("nombre_completo")
    return render(request, "directorio/lista.html", {"usuarios": qs})


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
        try:
            emitir(EventoPortavoz(
                tipo="permisos.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"usuario_id": u.pk, "email": u.email},
            ))
        except Exception:
            pass
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
