"""Login para El Taller — staff: los 4 roles. SSO de Google vive en `auth_google`."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from lib.errors import RateLimitExcedido
from lib.ratelimit import intentar, reset


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

    ident = f"taller:{email}:{request.META.get('REMOTE_ADDR', '?')}"
    try:
        intentar("login_taller", ident, limite=5, ventana_seg=900)
    except RateLimitExcedido as exc:
        messages.error(request, str(exc))
        return render(request, "auth/sign_in.html", status=429)

    user = authenticate(request, username=email, password=password)
    if user is None or not user.is_active:
        messages.error(request, "Credenciales inválidas.")
        return render(request, "auth/sign_in.html", status=401)

    login(request, user)
    user.ultimo_acceso_en = timezone.now()
    user.save(update_fields=["ultimo_acceso_en"])
    reset("login_taller", ident)
    return redirect("/")


def sign_out(request):
    logout(request)
    return redirect("/sign-in")
