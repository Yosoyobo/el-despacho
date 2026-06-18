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
    ("tareas", "Mis tareas", "Push cuando me asignan una tarea nueva o está por vencer.", None),
    ("mandados", "Mandados (envíos)", "Push cuando me asignan un mandado o cuando uno mío avanza (en camino, entregado, cancelado).", None),
    ("novedades", "Novedades del sistema", "Push cuando hay cambios y mejoras nuevas en El Despacho.", None),
    ("tesoreria_reembolso", "Reembolsos pendientes",
     "Push cuando se captura un egreso por reembolsar (contador + pagador).",
     ("super_admin", "dueno", "contador")),
    ("cobranza", "Cobranza · facturas vencidas",
     "Push diario cuando una factura cruza su fecha de vencimiento sin cobrarse.",
     ("super_admin", "dueno", "contador")),
    ("checador", "El Checador",
     "Push de correcciones de checada: solicitudes (a quien aprueba) y resoluciones (a quien solicitó).", None),
    ("chalan_sugerencia", "Sugerencias de El Chalán",
     "Push cuando El Chalán detecta algo que conviene revisar (facturas vencidas, proyectos estancados, mandados sin avance) o te manda el resumen del día.", None),
    ("chalan_analisis", "Opiniones del negocio (El Chalán)",
     "Análisis periódico del negocio (finanzas, cobranza, ventas, márgenes). La notificación abre un modal con la opinión completa del Chalán.", None),
]


def _categorias_para(user):
    # V6 Bloque 10: la comparación contra roles_visible usa los roles
    # efectivos del usuario (rol primario + roles personalizados).
    from lib.permisos import roles_efectivos
    roles_user = roles_efectivos(user)
    salida = []
    for entrada in CATEGORIAS:
        slug, nombre, desc = entrada[0], entrada[1], entrada[2]
        roles = entrada[3] if len(entrada) > 3 else None
        if roles and not (roles_user & set(roles)):
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
    # S-LC-Feedback-V10: abrir esta página marca todo como visto → vacía el
    # contador rojo del sidebar (no toca `clickeado_en`, que mide engagement).
    from django.utils import timezone
    InterfonoEntrega.objects.filter(usuario=request.user, visto_en__isnull=True).update(
        visto_en=timezone.now()
    )
    return render(request, "perfil_notificaciones/perfil.html", {
        "suscripciones": suscripciones,
        "configurado": InterfonoConfig.esta_configurado(),
        "categorias": categorias,
        "historial": historial,
        "historial_pagina": HISTORIAL_PAGINA,
        "tiene_mas": tiene_mas,
        "offset_siguiente": HISTORIAL_PAGINA,
        "formato_hora_actual": getattr(request.user, "formato_hora", "24h") or "24h",
    })


@login_required
@require_http_methods(["POST"])
def guardar_formato_hora(request):
    """S-LC-Feedback-V11: el usuario elige 24h o AM/PM para TODAS las horas."""
    pref = request.POST.get("formato_hora")
    if pref in ("24h", "ampm"):
        request.user.formato_hora = pref
        request.user.save(update_fields=["formato_hora", "actualizado_en"])
        messages.success(request, "Listo, tu formato de hora quedó guardado.")
    else:
        messages.error(request, "Formato inválido.")
    return redirect("perfil-notificaciones")


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
