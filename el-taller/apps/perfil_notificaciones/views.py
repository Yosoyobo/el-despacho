from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from interfono.models import (
    InterfonoSuscripcion,
    PreferenciaCategoriaPush,
    categoria_activa,
)
from lib.interfono import InterfonoConfig

# (slug, etiqueta, descripción). Default: opt-out (activo si no hay fila).
CATEGORIAS = [
    ("recados", "Los Recados", "Recibir push cuando me mandan o mencionan."),
]


@login_required
def perfil(request):
    suscripciones = InterfonoSuscripcion.objects.filter(
        usuario=request.user, activa=True
    ).order_by("-creada_en")
    categorias = [
        {
            "slug": slug,
            "nombre": nombre,
            "descripcion": desc,
            "activo": categoria_activa(request.user, slug),
        }
        for slug, nombre, desc in CATEGORIAS
    ]
    return render(request, "perfil_notificaciones/perfil.html", {
        "suscripciones": suscripciones,
        "configurado": InterfonoConfig.esta_configurado(),
        "categorias": categorias,
    })


@login_required
@require_http_methods(["POST"])
def guardar_categorias(request):
    seleccionadas = set(request.POST.getlist("categoria"))
    for slug, _nombre, _desc in CATEGORIAS:
        activo = slug in seleccionadas
        PreferenciaCategoriaPush.objects.update_or_create(
            usuario=request.user, categoria=slug, defaults={"activo": activo}
        )
    messages.success(request, "Preferencias de notificaciones actualizadas.")
    return redirect("perfil-notificaciones")
