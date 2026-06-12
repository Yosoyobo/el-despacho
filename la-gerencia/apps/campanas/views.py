"""Campañas de correo masivo (V6 Bloque 7C).

Flujo: nueva (plantilla + audiencia con CHECKBOXES — regla #6) → confirmación
explícita con "Vas a enviar a N clientes" + preview del correo → envío
best-effort con auditoría por destinatario. Sin límite por tanda (decisión
Oscar) — la confirmación explícita es el control.

Gating 100% granular: permiso (comunicacion, campanas); super_admin failsafe.
"""

from __future__ import annotations

from apps.la_cartera.models import Cliente
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import es_super_admin, puede_campanas
from lib.sanear import sanear_contexto

from .models import CampanaCorreo
from .services import contexto_para, enviar_campana

PLANTILLAS_CAMPANA = ("generico", "bienvenida", "cobranza")


def _gate(request):
    if not (es_super_admin(request.user) or puede_campanas(request.user)):
        return HttpResponseForbidden("Sin permiso para campañas de correo.")
    return None


def _clientes_con_email():
    return list(
        Cliente.activos.exclude(email_contacto="").order_by("razon_social")
    )


@login_required
def lista(request):
    if (r := _gate(request)) is not None:
        return r
    return render(request, "campanas/lista.html", {
        "campanas": CampanaCorreo.objects.select_related("creado_por")[:100],
    })


@login_required
def nueva(request):
    if (r := _gate(request)) is not None:
        return r
    clientes = _clientes_con_email()

    if request.method == "POST":
        plantilla = (request.POST.get("plantilla") or "generico").strip()
        if plantilla not in PLANTILLAS_CAMPANA:
            plantilla = "generico"
        asunto = sanear_contexto((request.POST.get("asunto") or "").strip())[:200]
        mensaje = sanear_contexto((request.POST.get("mensaje") or "").strip())
        ids = [int(i) for i in request.POST.getlist("clientes") if i.isdigit()]
        seleccion = [c for c in clientes if c.pk in set(ids)]

        if not seleccion:
            messages.error(request, "Selecciona al menos un cliente.")
        elif plantilla == "generico" and not mensaje:
            messages.error(request, "Escribe el mensaje del correo genérico.")
        elif request.POST.get("confirmado") == "1":
            # ── Envío real (segunda pasada, confirmada). ──
            campana = CampanaCorreo.objects.create(
                plantilla_slug=plantilla, asunto_custom=asunto,
                mensaje_custom=mensaje, total_destinatarios=len(seleccion),
                creado_por=request.user,
            )
            enviar_campana(campana, seleccion, request.user)
            messages.success(
                request,
                f"Campaña enviada: {campana.enviados} entregados, {campana.fallidos} fallidos.",
            )
            return redirect("campanas-detalle", pk=campana.pk)
        else:
            # ── Confirmación explícita con preview. ──
            from ajustes.models.plantilla_correo import PlantillaCorreo
            tmp = CampanaCorreo(plantilla_slug=plantilla, asunto_custom=asunto,
                                mensaje_custom=mensaje)
            asunto_prev, html_prev = PlantillaCorreo.obtener(plantilla).render(
                contexto_para(seleccion[0], tmp)
            )
            return render(request, "campanas/confirmar.html", {
                "plantilla": plantilla, "asunto": asunto, "mensaje": mensaje,
                "seleccion": seleccion, "total": len(seleccion),
                "asunto_preview": asunto_prev, "html_preview": html_prev,
            })

    return render(request, "campanas/nueva.html", {
        "clientes": clientes,
        "plantillas": PLANTILLAS_CAMPANA,
    })


@login_required
def detalle(request, pk):
    if (r := _gate(request)) is not None:
        return r
    campana = get_object_or_404(CampanaCorreo, pk=pk)
    return render(request, "campanas/detalle.html", {
        "campana": campana,
        "envios": campana.envios.select_related("cliente"),
    })
