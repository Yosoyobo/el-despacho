"""El Checador desde La Gerencia (E5): CRUD de horarios + bandeja de correcciones.

Los modelos viven en El Taller (apps.checador); Gerencia los administra.
Horarios → gated por `configurar_horarios`. Correcciones → `aprobar_correcciones`.
"""

from __future__ import annotations

from apps.checador import services
from apps.checador.models import HorarioLaboral, SolicitudCorreccion
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from lib.permisos import (
    puede_aprobar_correcciones_checador,
    puede_configurar_horarios_checador,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import HorarioBulkForm, HorarioLaboralForm


def _gate_horarios(request):
    if not puede_configurar_horarios_checador(request.user):
        return HttpResponseForbidden("Sin permiso para configurar horarios.")
    return None


def _gate_correcciones(request):
    if not puede_aprobar_correcciones_checador(request.user):
        return HttpResponseForbidden("Sin permiso para aprobar correcciones.")
    return None


# ───────────────────────── geocoding (Nominatim) ─────────────────────────

def _sedes_poi(texto: str = "", limite: int = 8) -> list[dict]:
    """POIs internos para La Gerencia = sedes activas con pin, filtradas por
    `texto` (sin acentos). Defensivo: `[]` si el catálogo no está disponible."""
    import contextlib
    import unicodedata

    def _na(s: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFD", (s or "").lower())
            if unicodedata.category(c) != "Mn"
        )

    out: list[dict] = []
    with contextlib.suppress(Exception):
        from apps.checador.models.sede import SedeLC
        q = _na(texto.strip())
        for s in SedeLC.objects.filter(
            activa=True, lat__isnull=False, lng__isnull=False,
        ).order_by("orden", "nombre"):
            if q and q not in _na(s.nombre):
                continue
            out.append({
                "label": s.nombre, "lat": float(s.lat), "lng": float(s.lng),
                "fuente": "sede", "clave": f"sede:{s.pk}",
            })
            if len(out) >= max(1, limite):
                break
    return out


@login_required
def geocoding_buscar(request):
    """Proxy server-side a Nominatim (OSM) + POIs (sedes) para La Gerencia.
    Reusa `lib.geocoding`. Con `?q=` → `{pois, resultados}` (sedes + direcciones;
    `&pois=0` omite las sedes); con `?lat=&lng=` → `{punto}` (al picar el mapa).
    Espejo del endpoint del Taller (los Django projects no comparten urlconf)."""
    from django.http import JsonResponse
    lat, lng = request.GET.get("lat"), request.GET.get("lng")
    if lat and lng:
        from lib.geocoding import identificar
        return JsonResponse({"punto": identificar(lat, lng)})
    from lib.geocoding import buscar
    q = request.GET.get("q", "")
    pois = [] if request.GET.get("pois") == "0" else _sedes_poi(q)
    return JsonResponse({"pois": pois, "resultados": buscar(q)})


# ───────────────────────── horarios ─────────────────────────

@login_required
def horarios(request):
    if (r := _gate_horarios(request)) is not None:
        return r
    globales = list(HorarioLaboral.objects.filter(usuario__isnull=True).order_by("dia_semana"))
    overrides = list(
        HorarioLaboral.objects.filter(usuario__isnull=False)
        .select_related("usuario").order_by("usuario__nombre_completo", "dia_semana"),
    )
    return render(request, "checador_admin/horarios.html", {
        "globales": globales, "overrides": overrides,
        "formato_hora_actual": getattr(request.user, "formato_hora", "24h") or "24h",
    })


@login_required
def guardar_formato_hora(request):
    """S-Finanzas-UX: el formato de hora del usuario (24h / AM-PM) se mudó aquí
    desde 'Mis notificaciones'. Es una preferencia personal — cada usuario que
    entra a Horarios laborales elige la suya. POST → guarda y vuelve."""
    if request.method != "POST":
        return HttpResponse(status=405)
    pref = request.POST.get("formato_hora")
    if pref in ("24h", "ampm"):
        request.user.formato_hora = pref
        request.user.save(update_fields=["formato_hora", "actualizado_en"])
        messages.success(request, "Listo, tu formato de hora quedó guardado.")
    else:
        messages.error(request, "Formato inválido.")
    return redirect("checador-admin-horarios")


@login_required
def horario_nuevo(request):
    if (r := _gate_horarios(request)) is not None:
        return r
    if request.method == "POST":
        form = HorarioBulkForm(request.POST)
        if form.is_valid():
            n = form.guardar()
            emitir(EventoPortavoz(
                tipo="checador.horario_actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"accion": "alta_masiva", "registros": n},
            ))
            messages.success(request, f"{n} horario(s) guardado(s).")
            return redirect("checador-admin-horarios")
    else:
        form = HorarioBulkForm()
    return render(request, "checador_admin/horario_form.html", {"form": form, "modo": "nuevo"})


@login_required
def horario_editar(request, pk):
    if (r := _gate_horarios(request)) is not None:
        return r
    obj = get_object_or_404(HorarioLaboral, pk=pk)
    if request.method == "POST":
        form = HorarioLaboralForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            _emit_horario(request, obj, "actualizado")
            messages.success(request, "Horario actualizado.")
            return redirect("checador-admin-horarios")
    else:
        form = HorarioLaboralForm(instance=obj)
    return render(request, "checador_admin/horario_form.html", {"form": form, "modo": "editar", "obj": obj})


@login_required
def horario_borrar(request, pk):
    if (r := _gate_horarios(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("checador-admin-horarios")
    obj = get_object_or_404(HorarioLaboral, pk=pk)
    if obj.usuario_id is None:
        messages.error(request, "No se puede borrar un horario global. Desactívalo si no aplica.")
        return redirect("checador-admin-horarios")
    obj.delete()
    _emit_horario(request, obj, "borrado")
    messages.success(request, "Horario eliminado.")
    return redirect("checador-admin-horarios")


def _emit_horario(request, obj, accion):
    emitir(EventoPortavoz(
        tipo="checador.horario_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"horario_id": obj.pk, "usuario_id": obj.usuario_id, "dia": obj.dia_semana, "accion": accion},
    ))


# ───────────────────────── correcciones (bandeja espejo) ─────────────────────────

@login_required
def correcciones(request):
    if (r := _gate_correcciones(request)) is not None:
        return r
    # S-LC-Feedback-V7: cada jefe ve solo a sus subordinados; super_admin todas.
    pendientes, resueltas = services.bandeja_correcciones_para(request.user)
    return render(request, "checador_admin/correcciones.html", {
        "pendientes": pendientes, "resueltas": resueltas,
    })


@login_required
def correccion_resolver_modal(request, pk):
    if (r := _gate_correcciones(request)) is not None:
        return r
    sol = get_object_or_404(SolicitudCorreccion, pk=pk)
    return render(request, "checador_admin/_modal_resolver.html", {
        "sol": sol, "sedes": services.sedes_todas(),
    })


@login_required
def correccion_resolver(request, pk):
    if (r := _gate_correcciones(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("checador-admin-correcciones")
    sol = get_object_or_404(SolicitudCorreccion, pk=pk)
    aprobar = request.POST.get("decision") == "aprobar"
    comentario = (request.POST.get("comentario") or "").strip()
    sede = None
    if request.POST.get("sede"):
        from apps.checador.models import SedeLC
        sede = SedeLC.objects.filter(pk=request.POST.get("sede")).first()
    try:
        services.resolver_correccion(
            sol, admin=request.user, aprobar=aprobar, comentario=comentario,
            sede=sede, sede_texto=request.POST.get("sede_texto"))
        messages.success(request, "Corrección aprobada." if aprobar else "Corrección rechazada.")
    except ValueError as exc:
        messages.error(request, str(exc))
    if request.headers.get("HX-Request") == "true":
        from django.urls import reverse
        return HttpResponse(status=204, headers={"HX-Redirect": reverse("checador-admin-correcciones")})
    return redirect("checador-admin-correcciones")


# ───────────────────────── Sedes / POI de LC (V12) ─────────────────────────
# Directorio de ubicaciones válidas de LC + modo de geocerca global. Reusa el
# permiso `configurar_horarios` (misma capacidad: configurar El Checador).

def _emit_sede(request, obj, accion):
    emitir(EventoPortavoz(
        tipo=f"checador.sede_{accion}",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"sede_id": obj.pk, "nombre": obj.nombre, "activa": obj.activa},
    ))


@login_required
def sedes(request):
    if (r := _gate_horarios(request)) is not None:
        return r
    from apps.checador.models import ConfiguracionGeocerca, SedeLC
    return render(request, "checador_admin/sedes.html", {
        "sedes": list(SedeLC.objects.all()),
        "config": ConfiguracionGeocerca.obtener(),
    })


@login_required
def sede_nuevo(request):
    if (r := _gate_horarios(request)) is not None:
        return r
    from .forms import SedeLCForm
    if request.method == "POST":
        form = SedeLCForm(request.POST)
        if form.is_valid():
            obj = form.save()
            _emit_sede(request, obj, "creada")
            messages.success(request, f"Sede «{obj.nombre}» creada.")
            return redirect("checador-admin-sedes")
    else:
        form = SedeLCForm()
    return render(request, "checador_admin/sede_form.html", {"form": form, "modo": "nueva"})


@login_required
def sede_editar(request, pk):
    if (r := _gate_horarios(request)) is not None:
        return r
    from apps.checador.models import SedeLC

    from .forms import SedeLCForm
    obj = get_object_or_404(SedeLC, pk=pk)
    if request.method == "POST":
        form = SedeLCForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            _emit_sede(request, obj, "actualizada")
            messages.success(request, "Sede actualizada.")
            return redirect("checador-admin-sedes")
    else:
        form = SedeLCForm(instance=obj)
    return render(request, "checador_admin/sede_form.html", {"form": form, "modo": "editar", "obj": obj})


@login_required
def sede_borrar(request, pk):
    if (r := _gate_horarios(request)) is not None:
        return r
    if request.method != "POST":
        return redirect("checador-admin-sedes")
    from apps.checador.models import SedeLC
    obj = get_object_or_404(SedeLC, pk=pk)
    _emit_sede(request, obj, "borrada")
    obj.delete()
    messages.success(request, "Sede eliminada.")
    return redirect("checador-admin-sedes")


@login_required
def geocerca_config(request):
    if (r := _gate_horarios(request)) is not None:
        return r
    from apps.checador.models import ConfiguracionGeocerca

    from .forms import ConfiguracionGeocercaForm
    config = ConfiguracionGeocerca.obtener()
    if request.method == "POST":
        form = ConfiguracionGeocercaForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="checador.geocerca_configurada",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"modo": config.modo},
            ))
            messages.success(request, "Modo de geocerca guardado.")
            return redirect("checador-admin-sedes")
    else:
        form = ConfiguracionGeocercaForm(instance=config)
    return render(request, "checador_admin/geocerca_config.html", {"form": form, "config": config})
