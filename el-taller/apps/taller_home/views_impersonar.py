"""Impersonación: el super_admin "ve como" otro usuario (S-LC-Feedback-V8).

Solo para reproducir bugs / soporte. Empieza desde el perfil del Equipo.
El swap real lo hace ImpersonacionMiddleware; aquí solo se setea/limpia la
sesión. Auditado vía Portavoz.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from cuentas.models.usuario import Usuario

from .middleware import SESSION_KEY


def _emitir(tipo, actor, payload):
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo=tipo, actor_id=getattr(actor, "pk", None),
            actor_email=getattr(actor, "email", None), payload=payload))
    except Exception:  # noqa: BLE001
        pass


@login_required
@require_POST
def impersonar(request, pk):
    from lib.permisos import tiene_rol
    # request.user es el super_admin real (aún no impersona, o ya salió).
    if not tiene_rol(request.user, "super_admin"):
        messages.error(request, "Solo un super admin puede ver como otro usuario.")
        return redirect("/")
    objetivo = get_object_or_404(Usuario, pk=pk, is_active=True)
    if tiene_rol(objetivo, "super_admin"):
        messages.error(request, "No puedes ver como otro super admin.")
        return redirect("directorio-perfil", pk=pk)
    request.session[SESSION_KEY] = objetivo.pk
    _emitir("sesion.impersonacion_iniciada", request.user,
            {"objetivo_id": objetivo.pk, "objetivo_email": objetivo.email})
    messages.info(request, f"Ahora ves el sistema como {objetivo.nombre_completo}.")
    return redirect("/")


@login_required
@require_POST
def salir_impersonacion(request):
    # Mientras impersona, request.user es el objetivo y request.impersonador el real.
    real = getattr(request, "impersonador", None)
    objetivo = getattr(request, "impersonando", None)
    request.session.pop(SESSION_KEY, None)
    if real and objetivo:
        _emitir("sesion.impersonacion_terminada", real,
                {"objetivo_id": objetivo.pk, "objetivo_email": objetivo.email})
    messages.success(request, "Volviste a tu cuenta.")
    return redirect("/")
