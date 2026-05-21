"""Views de El Dictado: interpretar, preview, aplicar, histórico."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import Dictado
from .services import aplicar, interpretar


@login_required
@require_http_methods(["POST"])
def interpretar_view(request):
    """POST /dictado/interpretar — desde el textarea de Sala de Juntas."""
    texto = (request.POST.get("texto") or "").strip()
    if not texto:
        messages.error(request, "Escribe algo antes de dictarle al Chalán.")
        return redirect("taller-home")
    dictado = interpretar(texto=texto, usuario=request.user, origen="sala_juntas")
    return redirect("dictado-preview", pk=dictado.pk)


@login_required
def preview(request, pk: int):
    """GET /dictado/<id>/ — muestra acciones + botones aplicar/cancelar."""
    dictado = get_object_or_404(Dictado, pk=pk, autor=request.user)
    acciones = list(dictado.acciones.order_by("orden"))
    acciones_view = [
        {
            "id": a.pk,
            "descripcion": a.descripcion,
            "tipo": a.tipo,
            "confianza": a.confianza,
            "sin_permiso": False,  # V1: permisos chequeados al aplicar
        }
        for a in acciones
    ]
    return render(request, "el_dictado/preview.html", {
        "dictado": dictado,
        "acciones": acciones_view,
        "chalan_apodo": dictado.chalan_apodo or "Chalán",
    })


@login_required
@require_http_methods(["POST"])
def aplicar_view(request, pk: int):
    """POST /dictado/<id>/aplicar — ejecuta acciones marcadas."""
    dictado = get_object_or_404(Dictado, pk=pk, autor=request.user)
    if dictado.estado not in ("esperando_confirmacion", "preguntando", "confirmado_parcial"):
        messages.warning(request, "Este dictado ya no se puede aplicar.")
        return redirect("dictado-detalle", pk=pk)

    # Acciones confirmadas vienen como `accion_<id>` checkbox marcado.
    marcadas = {int(k.split("_")[1]) for k in request.POST if k.startswith("accion_")}
    for accion in dictado.acciones.all():
        nueva = accion.pk in marcadas
        if accion.confirmada != nueva:
            accion.confirmada = nueva
            accion.save(update_fields=["confirmada"])

    resultado = aplicar(dictado=dictado, usuario=request.user)
    messages.success(
        request, f"Dictado aplicado: {resultado['aplicadas']} ejecutadas, {resultado['fallidas']} fallidas.",
    )
    return redirect("dictado-detalle", pk=pk)


@login_required
@require_http_methods(["POST"])
def responder_clarificacion(request, pk: int):
    """POST /dictado/<id>/responder — el usuario contesta la pregunta del Chalán."""
    dictado = get_object_or_404(Dictado, pk=pk, autor=request.user)
    if dictado.estado != "preguntando":
        messages.warning(request, "Este dictado no está esperando una clarificación.")
        return redirect("dictado-preview", pk=pk)
    respuesta = (request.POST.get("respuesta") or "").strip()
    if not respuesta:
        messages.error(request, "Escribe la aclaración antes de enviarla.")
        return redirect("dictado-preview", pk=pk)

    historial = list(dictado.historial_clarificaciones or [])
    historial.append({"pregunta": dictado.pregunta_clarificacion, "respuesta": respuesta})
    dictado.historial_clarificaciones = historial
    dictado.save(update_fields=["historial_clarificaciones"])

    interpretar(dictado=dictado, usuario=request.user)
    return redirect("dictado-preview", pk=pk)


@login_required
@require_http_methods(["POST"])
def cancelar(request, pk: int):
    dictado = get_object_or_404(Dictado, pk=pk, autor=request.user)
    if dictado.estado in ("esperando_confirmacion", "preguntando"):
        dictado.estado = "cancelado"
        dictado.save(update_fields=["estado"])
    return redirect("taller-home")


@login_required
def detalle(request, pk: int):
    from django.urls import reverse
    dictado = get_object_or_404(Dictado, pk=pk, autor=request.user)
    acciones = list(dictado.acciones.order_by("orden"))
    info_dictado = [
        {"label": "Estado", "value": dictado.get_estado_display()},
        {"label": "Chalán", "value": f"{dictado.chalan_apodo} ({dictado.modelo})" if dictado.chalan_apodo else "—"},
        {"label": "Latencia", "value": f"{dictado.latencia_interpretacion_ms} ms" if dictado.latencia_interpretacion_ms else "—"},
        {"label": "Creado", "value": dictado.creado_en.strftime("%d %b %Y %H:%M")},
    ]
    return render(request, "el_dictado/detalle.html", {
        "dictado": dictado,
        "acciones": acciones,
        "info_dictado": info_dictado,
        "breadcrumb_items": [
            {"url": reverse("dictado-historial"), "label": "El Dictado · historial"},
            {"label": f"#{dictado.pk}"},
        ],
        "back_url": reverse("dictado-historial"),
        "back_label": "Historial",
    })


@login_required
def historial(request):
    """GET /dictado/historial/ — listado personal de dictados del usuario."""
    dictados = list(Dictado.objects.filter(autor=request.user).order_by("-creado_en")[:50])
    return render(request, "el_dictado/historial.html", {"dictados": dictados})
