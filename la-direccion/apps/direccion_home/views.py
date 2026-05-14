from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ajustes.models.credencial import SLOTS_CREDENCIAL, Credencial
from cuentas.models.usuario import Usuario


@login_required
def home(request):
    """Sala de Juntas — at-a-glance. S3 lo llena de KPIs; S1a solo muestra salud básica."""
    total_credenciales = len(SLOTS_CREDENCIAL)
    configuradas = Credencial.objects.count()
    total_usuarios = Usuario.objects.count()
    activos = Usuario.objects.filter(is_active=True).count()
    ctx = {
        "salud_boveda": True,  # si llegamos aquí, La Bóveda importó OK
        "credenciales_configuradas": configuradas,
        "credenciales_total": total_credenciales,
        "usuarios_total": total_usuarios,
        "usuarios_activos": activos,
    }
    return render(request, "direccion_home/home.html", ctx)


def ping(request):
    """Liveness probe sin auth — para healthchecks de Caddy/CI."""
    from django.http import JsonResponse
    return JsonResponse({"ok": True, "app": "la-direccion"})
