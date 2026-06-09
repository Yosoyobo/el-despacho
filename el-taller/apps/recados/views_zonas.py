"""Zonas de Recados (S-Recados-V2 / C5c).

/recados/ se organiza en 3 zonas con tabs:
  - Chat        → views_chat.bandeja (lo de siempre)
  - Buzón       → zona_buzon: mis envíos al Buzón + sus respuestas
  - Actividad   → zona_actividad: menciones ("te taggearon") + actividad de
                  los proyectos del usuario (líder/asignado)
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from lib.permisos import puede


def _gate(request):
    if not puede(request.user, "recados", "ver"):
        return HttpResponse("Sin acceso a Recados.", status=403)
    return None


@login_required
def zona_buzon(request):
    """Mis envíos al Buzón: los mensajes que YO mandé + su estado y respuesta."""
    if (r := _gate(request)) is not None:
        return r
    from buzon.models import MensajeBuzon
    mensajes = list(
        MensajeBuzon.objects.filter(autor=request.user).order_by("-creado_en")[:50]
    )
    return render(request, "recados/zona_buzon.html", {"mensajes": mensajes})


def _url_referencia(ref) -> str:
    """Deep-link al contenedor donde me mencionaron."""
    t, cid = ref.contenedor_tipo, ref.contenedor_id
    if t == "mensaje_chat":
        from .models import Mensaje
        conv = Mensaje.objects.filter(pk=cid).values_list("conversacion_id", flat=True).first()
        return f"/recados/c/{conv}/" if conv else ""
    if t == "recado":
        return f"/recados/legacy/{cid}/"
    if t in ("comentario_tarea", "comentario_proyecto"):
        from apps.el_pizarron.models import Comentario
        c = Comentario.objects.filter(pk=cid).select_related("tarea").first()
        if not c:
            return ""
        if c.proyecto_id:
            return f"/proyectos/{c.proyecto_id}/"
        if c.tarea_id and c.tarea.proyecto_id:
            return f"/proyectos/{c.tarea.proyecto_id}/"
    return ""


_ETIQUETA_FUENTE = {
    "mensaje_chat": "en un chat",
    "recado": "en un recado",
    "comentario_tarea": "en un comentario de tarea",
    "comentario_proyecto": "en un comentario de proyecto",
}


@login_required
def zona_actividad(request):
    """Menciones (te taggearon) + actividad de mis proyectos."""
    if (r := _gate(request)) is not None:
        return r
    from referencias.models import Referencia

    refs = list(
        Referencia.objects.filter(usuario=request.user, tipo="usuario")
        .order_by("-creado_en")[:50]
    )
    menciones = []
    for ref in refs:
        url = _url_referencia(ref)
        if not url:
            continue
        menciones.append({
            "fuente": _ETIQUETA_FUENTE.get(ref.contenedor_tipo, "en el sistema"),
            "url": url,
            "creado_en": ref.creado_en,
        })

    from apps.los_proyectos import servicios_actividad
    actividad = servicios_actividad.feed_para(request.user, limite=50)

    return render(request, "recados/zona_actividad.html", {
        "menciones": menciones,
        "actividad": actividad,
    })
