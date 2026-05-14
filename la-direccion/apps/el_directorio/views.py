"""El Directorio — CRUD de usuarios internos. Solo super_admin y dueño."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from cuentas.models.usuario import Usuario
from lib.permisos import requires_role
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
