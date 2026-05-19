from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from interfono.models import (
    InterfonoEntrega,
    InterfonoSuscripcion,
    PreferenciaCategoriaPush,
    categoria_activa,
)
from lib.interfono import InterfonoConfig

HISTORIAL_PAGINA = 25

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
    historial = list(
        InterfonoEntrega.objects.filter(usuario=request.user)[:HISTORIAL_PAGINA]
    )
    tiene_mas = (
        InterfonoEntrega.objects.filter(usuario=request.user).count() > HISTORIAL_PAGINA
    )
    return render(request, "perfil_notificaciones/perfil.html", {
        "suscripciones": suscripciones,
        "configurado": InterfonoConfig.esta_configurado(),
        "categorias": categorias,
        "historial": historial,
        "historial_pagina": HISTORIAL_PAGINA,
        "tiene_mas": tiene_mas,
        "offset_siguiente": HISTORIAL_PAGINA,
    })


@login_required
def historial_pagina(request):
    """HTMX: devuelve un lote más antiguo de entregas."""
    try:
        offset = max(int(request.GET.get("offset", 0)), 0)
    except ValueError:
        offset = 0
    qs = InterfonoEntrega.objects.filter(usuario=request.user)
    items = list(qs[offset : offset + HISTORIAL_PAGINA])
    tiene_mas = qs.count() > offset + HISTORIAL_PAGINA
    return render(request, "perfil_notificaciones/_historial_items.html", {
        "historial": items,
        "tiene_mas": tiene_mas,
        "offset_siguiente": offset + HISTORIAL_PAGINA,
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
