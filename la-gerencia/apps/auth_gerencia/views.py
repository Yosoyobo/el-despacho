"""Login para La Gerencia: email/password con rate-limit 5/15min (regla #5).

El SSO de Google vive en la app raíz `auth_google` (compartida con El Taller
y andamio en La Recepción). El context processor `google_oauth_configurado`
inyecta el flag al template para mostrar/ocultar el botón.

Solo entran roles admin (super_admin/dueno); contador y diseñador se
loguean en El Taller.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from lib.errors import RateLimitExcedido
from lib.permisos import puede
from lib.ratelimit import intentar, reset

# S-LC-Feedback-V5 c5: el acceso a La Gerencia se hereda por permiso
# granular (modulo="gerencia", accion="acceder"). Super_admin y dueno lo
# reciben por default. Cualquier otro rol puede recibirlo manualmente
# desde Directorio en La Gerencia.
ROLES_PERMITIDOS_FAILSAFE = ("super_admin",)


def _puede_entrar_gerencia(user) -> bool:
    """Combina permiso granular + failsafe para super_admin (siempre puede)."""
    if user.rol in ROLES_PERMITIDOS_FAILSAFE:
        return True
    return puede(user, "gerencia", "acceder")


@require_http_methods(["GET", "POST"])
@csrf_protect
def sign_in(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "GET":
        return render(request, "auth/sign_in.html")

    email = (request.POST.get("email") or "").strip().lower()
    password = request.POST.get("password") or ""

    if not email or not password:
        messages.error(request, "Email y contraseña requeridos.")
        return render(request, "auth/sign_in.html", status=400)

    ident = f"gerencia:{email}:{request.META.get('REMOTE_ADDR', '?')}"
    try:
        intentar("login_gerencia", ident, limite=5, ventana_seg=900)
    except RateLimitExcedido as exc:
        messages.error(request, str(exc))
        return render(request, "auth/sign_in.html", status=429)

    user = authenticate(request, username=email, password=password)
    if user is None or not user.is_active:
        messages.error(request, "Credenciales inválidas.")
        return render(request, "auth/sign_in.html", status=401)

    if not _puede_entrar_gerencia(user):
        messages.error(request, "No tienes permiso para entrar a La Gerencia. Pide a un super_admin que te lo asigne.")
        return render(request, "auth/sign_in.html", status=403)

    login(request, user)
    user.ultimo_acceso_en = timezone.now()
    user.save(update_fields=["ultimo_acceso_en"])
    reset("login_gerencia", ident)
    return redirect("/")


def sign_out(request):
    logout(request)
    return redirect("/sign-in")
