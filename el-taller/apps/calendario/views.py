"""Vista de Calendario: mes actual + siguiente con tareas y entregas."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .services import eventos_por_dia, grid_mes


def _sumar_mes(year: int, month: int):
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _restar_mes(year: int, month: int):
    if month == 1:
        return year - 1, 12
    return year, month - 1


@login_required
def calendario(request):
    hoy = date.today()
    try:
        year = int(request.GET.get("year") or hoy.year)
        month = int(request.GET.get("month") or hoy.month)
    except (TypeError, ValueError):
        year, month = hoy.year, hoy.month

    grid_actual = grid_mes(year, month)
    y2, m2 = _sumar_mes(year, month)
    grid_siguiente = grid_mes(y2, m2)

    eventos_actual = eventos_por_dia(request.user, grid_actual["inicio"], grid_actual["fin"])
    eventos_siguiente = eventos_por_dia(request.user, grid_siguiente["inicio"], grid_siguiente["fin"])

    # Pre-mezcla eventos en cada celda para iteración sin lookup en template.
    def _enriquecer(grid, evmap):
        for semana in grid["semanas"]:
            for celda in semana:
                celda["eventos"] = evmap.get(celda["fecha"], [])
        return grid

    # Lista de eventos a partir de hoy (90 días) para la columna derecha.
    proximos = proximos_eventos(request)

    # Navegación
    y_prev, m_prev = _restar_mes(year, month)
    y_next, m_next = _sumar_mes(year, month)

    return render(request, "calendario/index.html", {
        "grid_actual": _enriquecer(grid_actual, eventos_actual),
        "grid_siguiente": _enriquecer(grid_siguiente, eventos_siguiente),
        "year": year,
        "month": month,
        "hoy": hoy,
        "nombre_mes_actual": _NOMBRES_MESES[month - 1],
        "nombre_mes_siguiente": _NOMBRES_MESES[m2 - 1],
        "year_siguiente": y2,
        "proximos_eventos": proximos,
        "nav": {
            "prev_url": f"?year={y_prev}&month={m_prev}",
            "next_url": f"?year={y_next}&month={m_next}",
            "hoy_url": "?",
        },
        "meses": _NOMBRES_MESES,
    })


_NOMBRES_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


@login_required
def dia_popover(request, fecha_iso: str):
    """GET /calendario/dia/<YYYY-MM-DD>/ — modal HTMX con eventos del día.

    Usado por el mini-calendario del Dashboard: click en un día con eventos
    inyecta este partial en #modal-slot.
    """
    try:
        f = datetime.strptime(fecha_iso, "%Y-%m-%d").date()
    except ValueError as e:
        raise Http404("fecha inválida") from e
    eventos = eventos_por_dia(request.user, f, f).get(f, [])
    nombre = f.strftime("%d") + " " + _NOMBRES_MESES[f.month - 1] + f" {f.year}"
    return render(request, "calendario/_modal_dia.html", {
        "fecha": f,
        "fecha_etiqueta": nombre,
        "eventos": eventos,
    })


@login_required
def nuevo_evento_modal(request):
    """GET /calendario/nuevo/ — modal HTMX con dos opciones (Tarea o Proyecto).

    Decisión S-LC-Feedback-V2: no creamos modelo Evento — reusamos Tarea
    y Proyecto existentes. El modal redirige al form correspondiente con
    la fecha pre-cargada si viene en la querystring.
    """
    fecha_default = request.GET.get("fecha") or ""
    return render(request, "calendario/_modal_nuevo_evento.html", {
        "fecha_default": fecha_default,
    })


@login_required
def evento_form(request, pk: int | None = None):
    """Crear/editar un Evento genérico del calendario (feriado, vacaciones,
    evento operativo). GET HTMX → modal; POST → guarda y refresca el calendario.
    S-LC-Feedback-V13.
    """
    from apps.el_pizarron.models import Evento

    from .forms import EventoForm
    evento = get_object_or_404(Evento, pk=pk) if pk else None
    es_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        form = EventoForm(request.POST, instance=evento)
        if form.is_valid():
            nuevo = evento is None
            ev = form.save(commit=False)
            if nuevo:
                ev.creado_por = request.user
            ev.save()
            emitir(EventoPortavoz(
                tipo="evento.creado" if nuevo else "evento.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"evento_id": ev.pk, "titulo": ev.titulo},
            ))
            destino = reverse("calendario-index") + f"?year={ev.fecha_inicio.year}&month={ev.fecha_inicio.month}"
            return HttpResponse(status=204, headers={"HX-Redirect": destino}) if es_htmx else redirect(destino)
        return render(request, "calendario/_modal_evento.html", {"form": form, "evento": evento})
    # GET → modal con fecha precargada (?fecha=YYYY-MM-DD) si es nuevo.
    initial = {}
    if evento is None:
        f = request.GET.get("fecha") or ""
        if f:
            initial = {"fecha_inicio": f, "fecha_fin": f}
    form = EventoForm(instance=evento, initial=initial)
    return render(request, "calendario/_modal_evento.html", {"form": form, "evento": evento})


@login_required
def evento_eliminar(request, pk: int):
    """Borra un Evento genérico. POST. S-LC-Feedback-V13."""
    from apps.el_pizarron.models import Evento
    evento = get_object_or_404(Evento, pk=pk)
    if request.method != "POST":
        return HttpResponseForbidden("Solo POST.")
    anio, mes = evento.fecha_inicio.year, evento.fecha_inicio.month
    emitir(EventoPortavoz(
        tipo="evento.eliminado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"evento_id": evento.pk, "titulo": evento.titulo},
    ))
    evento.delete()
    destino = reverse("calendario-index") + f"?year={anio}&month={mes}"
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(status=204, headers={"HX-Redirect": destino})
    return redirect(destino)


@login_required
def resumen_modal(request):
    """GET /calendario/resumen/ — El Chalán resume el calendario (estación
    `calendario_resumen`). Modal HTMX. No persiste. Gated por (chalan, usar)."""
    from django.http import HttpResponseForbidden
    from django.utils.html import format_html

    from lib.permisos import puede_usar_chalan

    from .resumen_ia import resumir_calendario

    if not puede_usar_chalan(request.user):
        return HttpResponseForbidden("No tienes permiso para usar El Chalán.")
    try:
        dias = int(request.GET.get("dias") or 14)
    except (TypeError, ValueError):
        dias = 14
    res = resumir_calendario(usuario=request.user, dias=dias)
    if res.get("ok"):
        cuerpo = format_html('<p class="whitespace-pre-line">{}</p>', res["resumen"])
    else:
        cuerpo = format_html(
            '<p class="text-error-600 dark:text-error-400">{}</p>',
            res.get("error") or "El Chalán no respondió.",
        )
    return render(request, "_componentes_tailadmin/_modal_htmx.html", {
        "titulo": f"Resumen del calendario · próximos {res.get('dias', dias)} días",
        "cuerpo": cuerpo,
        "tamano": "lg",
    })


def proximos_eventos(request):
    """Lista de tareas/entregas desde hoy en adelante (para la página Calendario)."""
    hoy = date.today()
    fin = hoy + timedelta(days=90)  # ventana de 90 días para no inflar el render
    evs = eventos_por_dia(request.user, hoy, fin)
    items = []
    for f in sorted(evs.keys()):
        for ev in evs[f]:
            items.append({**ev, "fecha": f})
    return items


@login_required
def mover_evento(request):
    """D7 (LC 2026-07): recolocar un evento a otro día por drag&drop en el grid.
    POST {tipo, id, fecha}. Devuelve JSON; el front recarga. Respeta permisos."""
    from django.http import JsonResponse
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "método"}, status=405)
    tipo = request.POST.get("tipo", "")
    obj_id = request.POST.get("id", "")
    try:
        nueva = date.fromisoformat(request.POST.get("fecha", ""))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Fecha inválida."}, status=400)

    if tipo == "tarea":
        from apps.el_pizarron.models import Tarea

        from lib.permisos import puede_ver_tarea
        t = get_object_or_404(Tarea, pk=obj_id)
        if not puede_ver_tarea(request.user, t):
            return JsonResponse({"ok": False, "error": "Sin permiso."}, status=403)
        t.fecha_compromiso = nueva
        t.save(update_fields=["fecha_compromiso"])
    elif tipo == "entrega":  # entrega/cierre de proyecto
        from apps.los_proyectos.models import Proyecto
        from django.utils import timezone as _tz

        from lib.permisos import puede_editar_proyecto
        p = get_object_or_404(Proyecto, pk=obj_id)
        if not puede_editar_proyecto(request.user, p):
            return JsonResponse({"ok": False, "error": "Sin permiso."}, status=403)
        hora = _tz.localtime(p.fecha_compromiso).time() if p.fecha_compromiso else datetime.min.time().replace(hour=12)
        dt_ = datetime.combine(nueva, hora)
        p.fecha_compromiso = _tz.make_aware(dt_) if _tz.is_naive(dt_) else dt_
        p.save(update_fields=["fecha_compromiso"])
    elif tipo == "evento":
        from apps.el_pizarron.models import Evento
        ev = get_object_or_404(Evento, pk=obj_id)
        delta = (ev.fecha_fin - ev.fecha_inicio) if ev.fecha_fin else timedelta(0)
        ev.fecha_inicio = nueva
        ev.fecha_fin = nueva + delta
        ev.save()
    else:
        return JsonResponse({"ok": False, "error": "Tipo desconocido."}, status=400)
    return JsonResponse({"ok": True})
