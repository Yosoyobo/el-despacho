"""Login para El Taller — staff: super_admin, dueno, contador, disenador.
Mismo patrón que La Gerencia pero acepta los 4 roles."""

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

    ident = f"taller:{email}:{request.META.get('REMOTE_ADDR', '?')}"
    try:
        intentar("login_taller", ident, limite=5, ventana_seg=900)
    except RateLimitExcedido as exc:
        messages.error(request, str(exc))
        return render(request, "auth/sign_in.html", {"google_listo": google_listo}, status=429)

    user = authenticate(request, username=email, password=password)
    if user is None or not user.is_active:
        messages.error(request, "Credenciales inválidas.")
        return render(request, "auth/sign_in.html", {"google_listo": google_listo}, status=401)

    login(request, user)
    user.ultimo_acceso_en = timezone.now()
    user.save(update_fields=["ultimo_acceso_en"])
    reset("login_taller", ident)
    return redirect("/")


def sign_out(request):
    logout(request)
    return redirect("/sign-in")


def google_iniciar(request):
    if not google_oauth.esta_configurado():
        messages.error(request, "Google SSO no está configurado.")
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

    u = Usuario.objects.filter(email=perfil.email.lower()).first()
    if u is None:
        messages.error(request, "No hay cuenta con ese email. Pide a un admin que te dé de alta.")
        return redirect("/sign-in")

    cambios = []
    if not u.google_sub:
        u.google_sub = perfil.google_sub
        cambios.append("google_sub")
    if perfil.avatar_url and not u.avatar_url:
        u.avatar_url = perfil.avatar_url
        cambios.append("avatar_url")
    if cambios:
        u.save(update_fields=cambios)

    u.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, u)
    u.ultimo_acceso_en = timezone.now()
    u.save(update_fields=["ultimo_acceso_en"])
    return redirect("/")
