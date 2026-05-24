"""Dashboard ejecutivo (espejo) de La Gerencia — Pre-S2b.2.

La Sala de Juntas con slot del Chalán y datos operativos se mudó a El
Taller. Aquí queda un dashboard ejecutivo compacto para super_admin/dueño
con: KPIs placeholder (hasta S2b.4), CTA "Ver Sala de Juntas en El Taller",
y mini-resumen de estado del sistema (counts de Credencial/Usuario;
estado real de integraciones lo da El Site).
"""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from ajustes.models.credencial import SLOTS_CREDENCIAL, Credencial
from cuentas.models.usuario import Usuario
from lib.graficas import donut_desde_conteo


@login_required
def home(request):
    user = request.user
    rol = getattr(user, "rol", None)

    if rol not in ("super_admin", "dueno"):
        # contador/disenador no entran a Gerencia (middleware redirige).
        return render(request, "gerencia_home/home.html", {"kpis": []})

    # Salud de integraciones (última lectura por plataforma).
    integraciones_ok = 0
    integraciones_error = 0
    try:
        from lib.site.almacen import ultimo_por_plataforma
        for v in ultimo_por_plataforma().values():
            if v.get("estado") == "ok":
                integraciones_ok += 1
            elif v.get("estado") == "error":
                integraciones_error += 1
    except Exception:  # noqa: BLE001
        pass

    # Donut: usuarios por rol.
    usuarios_por_rol = dict(
        Usuario.objects.filter(is_active=True)
        .values_list("rol")
        .annotate(c=Count("id"))
        .values_list("rol", "c")
    )
    etiquetas_rol = {
        "super_admin": "Super admin",
        "dueno": "Admin",
        "contador": "Contador",
        "disenador": "Diseñador",
    }

    return render(request, "gerencia_home/home.html", {
        "kpis_hero": {
            "usuarios_activos": Usuario.objects.filter(is_active=True).count(),
            "usuarios_total": Usuario.objects.count(),
            "credenciales_configuradas": Credencial.objects.count(),
            "credenciales_total": len(SLOTS_CREDENCIAL),
            "integraciones_ok": integraciones_ok,
            "integraciones_error": integraciones_error,
        },
        "donut_usuarios_json": donut_desde_conteo(usuarios_por_rol, etiquetas=etiquetas_rol),
        "salud_boveda": True,
        "credenciales_configuradas": Credencial.objects.count(),
        "credenciales_total": len(SLOTS_CREDENCIAL),
        "usuarios_total": Usuario.objects.count(),
        "usuarios_activos": Usuario.objects.filter(is_active=True).count(),
        "taller_url": getattr(settings, "TALLER_URL", "https://taller.ninomeando.com/"),
    })


def ping(request):
    """Liveness probe sin auth — para healthchecks de Caddy/CI."""
    from django.http import JsonResponse
    return JsonResponse({"ok": True, "app": "la-gerencia"})
