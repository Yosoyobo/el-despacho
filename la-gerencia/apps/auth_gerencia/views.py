"""Login para La Gerencia: email/password + Google SSO (si está configurado)
con rate-limit 5/15min (regla #5). Solo entran usuarios con rol admin (super_admin/dueno);
contador y diseñador se loguean en El Taller — La Gerencia es exclusiva de mando.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from cuentas.models.usuario import Usuario
from lib import google_oauth
from lib.errors import RateLimitExcedido
from lib.ratelimit import intentar, reset

ROLES_PERMITIDOS_EN_DIRECCION = ("super_admin", "dueno")


@require_http_methods(["GET", "POST"])
@csrf_protect
def sign_in(request):
    if request.user.is_authenticated:
        return redirect("/")

    google_listo = google_oauth.esta_configurado()

    if request.method == "GET":
        return render(request, "auth/sign_in.html", {"google_listo": google_listo})

    email = (request.POST.get("email") or "").strip().lower()
    password = request.POST.get("password") or ""

    if not email or not password:
        messages.error(request, "Email y contraseña requeridos.")
        return render(request, "auth/sign_in.html", {"google_listo": google_listo}, status=400)

    ident = f"gerencia:{email}:{request.META.get('REMOTE_ADDR', '?')}"
    try:
        intentar("login_gerencia", ident, limite=5, ventana_seg=900)
    except RateLimitExcedido as exc:
        messages.error(request, str(exc))
        return render(request, "auth/sign_in.html", {"google_listo": google_listo}, status=429)

    user = authenticate(request, username=email, password=password)
    if user is None or not user.is_active:
        messages.error(request, "Credenciales inválidas.")
        return render(request, "auth/sign_in.html", {"google_listo": google_listo}, status=401)

    if user.rol not in ROLES_PERMITIDOS_EN_DIRECCION:
        messages.error(request, "Esta área es solo para super_admin y dueño.")
        return render(request, "auth/sign_in.html", {"google_listo": google_listo}, status=403)

    login(request, user)
    user.ultimo_acceso_en = timezone.now()
    user.save(update_fields=["ultimo_acceso_en"])
    reset("login_gerencia", ident)
    return redirect("/")


def sign_out(request):
    logout(request)
    return redirect("/sign-in")


# ── Google SSO ─────────────────────────────────────────────────────────────

def google_iniciar(request):
    if not google_oauth.esta_configurado():
        messages.error(request, "Google SSO no está configurado. Pídele al super_admin.")
        return redirect("/sign-in")
    url, state = google_oauth.url_autorizacion()
    request.session["google_oauth_state"] = state
    return redirect(url)


def google_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code or state != request.session.get("google_oauth_state"):
        messages.error(request, "Callback de Google inválido.")
        return redirect("/sign-in")
    request.session.pop("google_oauth_state", None)

    try:
        perfil = google_oauth.intercambiar_code(code)
    except Exception:
        messages.error(request, "Falló el intercambio con Google.")
        return redirect("/sign-in")

    user = _register_or_link(perfil)
    if user is None:
        messages.error(
            request,
            "No hay cuenta con ese email. Pídele a un super_admin que te dé de alta.",
        )
        return redirect("/sign-in")

    if user.rol not in ROLES_PERMITIDOS_EN_DIRECCION:
        messages.error(request, "Esta área es solo para super_admin y dueño.")
        return redirect("/sign-in")

    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)
    user.ultimo_acceso_en = timezone.now()
    user.save(update_fields=["ultimo_acceso_en"])
    return redirect("/")


def _register_or_link(perfil) -> Usuario | None:
    """Si existe usuario con ese email, vincula google_sub.
    Si no existe, devuelve None (el usuario debe crearlo el super_admin)."""
    u = Usuario.objects.filter(email=perfil.email.lower()).first()
    if u is None:
        return None
    cambios = []
    if not u.google_sub:
        u.google_sub = perfil.google_sub
        cambios.append("google_sub")
    if perfil.avatar_url and not u.avatar_url:
        u.avatar_url = perfil.avatar_url
        cambios.append("avatar_url")
    if cambios:
        u.save(update_fields=cambios)
    return u
