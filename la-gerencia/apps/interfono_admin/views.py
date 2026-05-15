"""El Interfono — UI admin: enviar manuales + historial + perfil del propio usuario."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from cuentas.models.usuario import Usuario
from interfono.models import InterfonoEnvio, InterfonoSuscripcion
from lib.interfono import InterfonoConfig, enviar_a_audiencia
from lib.permisos import requires_role

from .forms import EnvioInterfonoForm


@requires_role("super_admin", "dueno")
def tablero(request):
    form = EnvioInterfonoForm()
    envios = InterfonoEnvio.objects.select_related("autor").order_by("-creado_en")[:50]
    usuarios = Usuario.objects.filter(is_active=True).order_by("email").only("id", "email", "nombre_completo")
    return render(request, "interfono/tablero.html", {
        "form": form,
        "envios": envios,
        "usuarios": usuarios,
        "configurado": InterfonoConfig.esta_configurado(),
    })


@requires_role("super_admin", "dueno")
@require_http_methods(["POST"])
def enviar(request):
    form = EnvioInterfonoForm(request.POST)
    if not form.is_valid():
        for err in form.errors.values():
            messages.error(request, " ".join(err))
        return redirect("interfono-tablero")

    if not InterfonoConfig.esta_configurado():
        messages.error(request, "Llaves VAPID no configuradas. Generarlas con `interfono_generar_vapid`.")
        return redirect("interfono-tablero")

    audiencia, label = form.audiencia_resuelta()
    titulo = form.cleaned_data["titulo"]
    cuerpo = form.cleaned_data["cuerpo"]
    url_destino = form.cleaned_data.get("url_destino") or ""

    # Crear el registro primero para poder usar su id como tag.
    envio = InterfonoEnvio.objects.create(
        autor=request.user,
        audiencia=audiencia,
        audiencia_label=label,
        titulo=titulo,
        cuerpo=cuerpo,
        url_destino=url_destino,
    )

    if request.POST.get("modo") == "prueba":
        # Override: solo me llega a mí, sin tocar la audiencia seleccionada.
        from lib.interfono import enviar_a_usuario

        totales = enviar_a_usuario(
            request.user, titulo=titulo, cuerpo=cuerpo, url=url_destino,
            tag=f"prueba-manual-{envio.pk}",
        )
        envio.audiencia = f"usuario:{request.user.pk}"
        envio.audiencia_label = f"Prueba a {request.user.email}"
    else:
        totales = enviar_a_audiencia(
            audiencia, titulo=titulo, cuerpo=cuerpo, url=url_destino,
            tag=f"manual-{envio.pk}",
        )

    envio.entregadas = totales["entregadas"]
    envio.fallidas = totales["fallidas"]
    envio.suscripciones_invalidadas = totales["invalidadas"]
    envio.save(update_fields=["audiencia", "audiencia_label", "entregadas", "fallidas", "suscripciones_invalidadas"])

    messages.success(
        request,
        f"Notificación enviada — {totales['entregadas']} entregadas, "
        f"{totales['fallidas']} fallidas, {totales['invalidadas']} suscripciones invalidadas.",
    )
    return redirect("interfono-tablero")


@login_required
def perfil_notificaciones(request):
    suscripciones = InterfonoSuscripcion.objects.filter(usuario=request.user, activa=True).order_by("-creada_en")
    return render(request, "interfono/perfil_notificaciones.html", {
        "suscripciones": suscripciones,
        "configurado": InterfonoConfig.esta_configurado(),
    })
