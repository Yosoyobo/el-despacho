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

# (slug, etiqueta, descripción, roles_visible). Default: opt-out (activo si no hay fila).
CATEGORIAS = [
    ("recados", "Los Recados (legacy)", "Recibir push cuando me mandan o mencionan en la bandeja vieja.", None),
    ("recados_chat", "Los Recados (chat)", "Recibir push cuando me escriben en una conversación.", None),
    ("buzon", "El Buzón (admins)", "Push cuando un empleado crea un mensaje nuevo.",
     ("super_admin", "dueno")),
    ("proyectos", "Mis proyectos", "Push cuando se crea un proyecto o cambia el estado de uno donde participo.",
     None),
    ("tareas", "Mis tareas", "Push cuando me asignan una tarea nueva.", None),
    ("tesoreria_reembolso", "Reembolsos pendientes",
     "Push cuando se captura un egreso por reembolsar (contador + pagador).",
     ("super_admin", "dueno", "contador")),
    ("cobranza", "Cobranza · facturas vencidas",
     "Push diario cuando una factura cruza su fecha de vencimiento sin cobrarse.",
     ("super_admin", "dueno", "contador")),
]


def _categorias_para(user):
    rol = getattr(user, "rol", None)
    salida = []
    for entrada in CATEGORIAS:
        slug, nombre, desc = entrada[0], entrada[1], entrada[2]
        roles = entrada[3] if len(entrada) > 3 else None
        if roles and rol not in roles:
            continue
        salida.append((slug, nombre, desc))
    return salida


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
        for slug, nombre, desc in _categorias_para(request.user)
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
    for slug, _nombre, _desc in _categorias_para(request.user):
        activo = slug in seleccionadas
        PreferenciaCategoriaPush.objects.update_or_create(
            usuario=request.user, categoria=slug, defaults={"activo": activo}
        )
    messages.success(request, "Preferencias de notificaciones actualizadas.")
    return redirect("perfil-notificaciones")
