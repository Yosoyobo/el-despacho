"""Dashboard ejecutivo (espejo) de La Gerencia — Pre-S2b.2.

La Sala de Juntas con slot del Chalán y datos operativos se mudó a El
Taller. Aquí queda un dashboard ejecutivo compacto para super_admin/dueño
con: KPIs placeholder (hasta S2b.4), CTA "Ver Sala de Juntas en El Taller",
y mini-resumen de estado del sistema (counts de Credencial/Usuario;
estado real de integraciones lo da El Site).
"""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ajustes.models.credencial import SLOTS_CREDENCIAL, Credencial
from cuentas.models.usuario import Usuario


@login_required
def home(request):
    user = request.user
    rol = getattr(user, "rol", None)

    # Mismos KPIs que la Sala de Juntas del Taller — visual espejo.
    if rol in ("super_admin", "dueno"):
        kpis = [
            {"etiqueta": "Pipeline ganado (mes)", "valor": "—", "nota": "S2b.4"},
            {"etiqueta": "Pipeline prospectado", "valor": "—", "nota": "S2b.4"},
            {"etiqueta": "Ingresos del mes", "valor": "—", "nota": "S2b.4"},
            {"etiqueta": "Cuentas por cobrar", "valor": "—", "nota": "S2b.4"},
        ]
    else:
        kpis = []  # contador/disenador no entran a Gerencia (middleware redirige).

    return render(request, "gerencia_home/home.html", {
        "kpis": kpis,
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
