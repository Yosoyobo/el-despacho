"""El Buzón — vista para empleados (los 4 roles autenticados)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from buzon.models import MensajeBuzon
from lib.colador import colar_reporte
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.sanear import sanear_contexto

from .forms import NuevoMensajeForm


@login_required
@require_http_methods(["GET", "POST"])
def nuevo(request):
    inicial = {
        "tipo": request.GET.get("tipo") or "sugerencia",
        "asunto": request.GET.get("asunto") or "",
        "cuerpo": request.GET.get("cuerpo") or "",
    }
    if request.method == "POST":
        form = NuevoMensajeForm(request.POST)
        if form.is_valid():
            msg: MensajeBuzon = form.save(commit=False)
            msg.autor = request.user
            # Saneamiento: type problema usa El Colador (puede traer trace);
            # los otros usan sanear_contexto para neutralizar payload obvio.
            if msg.tipo == "problema":
                msg.cuerpo = colar_reporte(msg.cuerpo)[:5000]
            else:
                msg.cuerpo = sanear_contexto(msg.cuerpo, max_len=5000)
            msg.asunto = sanear_contexto(msg.asunto, max_len=200) or msg.asunto[:200]
            msg.save()
            emitir(EventoPortavoz(
                tipo="buzon.nuevo_mensaje",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"mensaje_id": msg.pk, "tipo": msg.tipo},
            ))
            messages.success(request, "Mensaje enviado al Buzón. Gracias por escribirnos.")
            return redirect("buzon-empleado-mios")
    else:
        form = NuevoMensajeForm(initial=inicial)
    return render(request, "buzon_empleado/nuevo.html", {"form": form})


@login_required
def mios_lista(request):
    qs = MensajeBuzon.objects.filter(autor=request.user)
    return render(request, "buzon_empleado/mios_lista.html", {"mensajes": qs})


@login_required
def mios_detalle(request, pk: int):
    msg = get_object_or_404(MensajeBuzon, pk=pk)
    if msg.autor_id != request.user.pk:
        raise Http404
    return render(request, "buzon_empleado/mios_detalle.html", {"mensaje": msg})
