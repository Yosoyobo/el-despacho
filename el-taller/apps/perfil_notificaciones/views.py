from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from interfono.models import InterfonoSuscripcion
from lib.interfono import InterfonoConfig


@login_required
def perfil(request):
    suscripciones = InterfonoSuscripcion.objects.filter(usuario=request.user, activa=True).order_by("-creada_en")
    return render(request, "perfil_notificaciones/perfil.html", {
        "suscripciones": suscripciones,
        "configurado": InterfonoConfig.esta_configurado(),
    })
