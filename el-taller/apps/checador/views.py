"""Vistas de El Checador (El Taller) — móvil-first.

E2: tablero con botón Entrada/Salida + snapshot geo + Mi semana.
"""

from __future__ import annotations

import datetime
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from lib.permisos import (
    puede_aprobar_correcciones_checador,
    puede_checar,
    puede_exportar_checador,
    puede_ver_equipo_checador,
)

from . import services
from .models import Jornada, SolicitudCorreccion, Visita


def _requiere_checar(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not puede_checar(request.user):
            return HttpResponseForbidden("Sin acceso a El Checador.")
        return view(request, *args, **kwargs)
    return inner


def _requiere_aprobar(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not puede_aprobar_correcciones_checador(request.user):
            return HttpResponseForbidden("Sin permiso para aprobar correcciones.")
        return view(request, *args, **kwargs)
    return inner


def _requiere_ver_equipo(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not puede_ver_equipo_checador(request.user):
            return HttpResponseForbidden("Sin permiso para ver el equipo.")
        return view(request, *args, **kwargs)
    return inner


def _geo_de_request(request) -> dict:
    """Arma el dict geo desde el POST. Si falta o el cliente reporta `sin_geo`,
    devuelve `{"sin_geo": True}` (la checada se registra igual)."""
    if request.POST.get("sin_geo") == "1":
        return {"sin_geo": True}
    lat = request.POST.get("lat")
    lng = request.POST.get("lng")
    if not lat or not lng:
        return {"sin_geo": True}
    try:
        precision = request.POST.get("precision")
        return {
            "lat": float(lat),
            "lng": float(lng),
            "precision": float(precision) if precision else None,
            "sin_geo": False,
        }
    except (TypeError, ValueError):
        return {"sin_geo": True}


@login_required
@_requiere_checar
def tablero(request):
    hoy = timezone.localdate()
    jornada = Jornada.objects.filter(usuario=request.user, fecha=hoy).first()

    if jornada is None or not jornada.entrada_en:
        accion = "entrada"
    elif not jornada.salida_en:
        accion = "salida"
    else:
        accion = "completa"

    desde = hoy - datetime.timedelta(days=6)
    semana = list(
        Jornada.objects.filter(usuario=request.user, fecha__gte=desde, fecha__lte=hoy).order_by("-fecha"),
    )
    visitas_hoy = list(
        Visita.objects.filter(usuario=request.user, registrado_en__date=hoy)
        .select_related("cliente", "proveedor").order_by("-registrado_en"),
    )

    return render(request, "checador/tablero.html", {
        "jornada": jornada,
        "accion": accion,
        "semana": semana,
        "visitas_hoy": visitas_hoy,
        "hoy": hoy,
        "timer": services.timer_activo(request.user),
        "proyectos": _proyectos_para(request.user),
    })


@login_required
@_requiere_checar
def visita_modal(request):
    """GET HTMX → fragmento del modal para registrar una visita."""
    from apps.el_catalogo.models import Proveedor
    from apps.la_cartera.models import Cliente
    return render(request, "checador/_modal_visita.html", {
        "clientes": Cliente.objects.filter(activo=True).order_by("razon_social"),
        "proveedores": Proveedor.objects.filter(activo=True).order_by("razon_social"),
    })


@login_required
@_requiere_checar
@require_POST
def visita(request):
    from apps.el_catalogo.models import Proveedor
    from apps.la_cartera.models import Cliente

    tipo = request.POST.get("tipo", "cliente")
    nota = (request.POST.get("nota") or "").strip()
    geo = _geo_de_request(request)
    uuid = (request.POST.get("uuid") or "")[:64]

    cliente = proveedor = None
    if tipo == "cliente":
        cid = request.POST.get("cliente")
        cliente = Cliente.objects.filter(pk=cid).first() if cid else None
    elif tipo == "proveedor":
        pid = request.POST.get("proveedor")
        proveedor = Proveedor.objects.filter(pk=pid).first() if pid else None

    try:
        services.registrar_visita(
            request.user, tipo=tipo, cliente=cliente, proveedor=proveedor,
            geo=geo, nota=nota, uuid=uuid,
        )
        messages.success(request, "Visita registrada.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("checador:tablero")


# ───────────────────────── timer de proyecto (E4) ─────────────────────────

def _proyectos_para(user):
    """Proyectos que el usuario puede ver (para el selector del timer)."""
    from apps.los_proyectos.models import Proyecto

    from lib.permisos import roles_efectivos
    roles = roles_efectivos(user)
    qs = Proyecto.objects.all()
    if "disenador" in roles and not (roles & {"super_admin", "dueno", "contador"}):
        qs = qs.filter(asignaciones__usuario=user).distinct()
    return qs.order_by("codigo")


@login_required
@_requiere_checar
@require_POST
def timer_iniciar(request):
    proyecto = _proyectos_para(request.user).filter(pk=request.POST.get("proyecto")).first()
    if proyecto is None:
        messages.error(request, "Selecciona un proyecto válido.")
        return redirect("checador:tablero")
    services.iniciar_timer(request.user, proyecto)
    messages.success(request, f"Cronómetro iniciado en {proyecto.codigo}.")
    return redirect("checador:tablero")


@login_required
@_requiere_checar
@require_POST
def timer_detener(request):
    try:
        sesion = services.detener_timer(request.user)
        messages.success(request, f"Cronómetro detenido: {sesion.duracion_min} min registrados.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("checador:tablero")


@login_required
@_requiere_checar
def sesion_modal(request):
    """GET HTMX → modal de captura manual de tiempo por proyecto."""
    return render(request, "checador/_modal_sesion.html", {
        "proyectos": _proyectos_para(request.user),
    })


@login_required
@_requiere_checar
@require_POST
def sesion(request):
    proyecto = _proyectos_para(request.user).filter(pk=request.POST.get("proyecto")).first()
    if proyecto is None:
        messages.error(request, "Selecciona un proyecto válido.")
        return redirect("checador:historial")
    inicio = _parse_dt(request.POST.get("inicio"))
    fin = _parse_dt(request.POST.get("fin"))
    if inicio is None or fin is None:
        messages.error(request, "Indica inicio y fin válidos.")
        return redirect("checador:historial")
    try:
        services.capturar_sesion_manual(
            request.user, proyecto, inicio=inicio, fin=fin,
            nota=(request.POST.get("nota") or "").strip(),
        )
        messages.success(request, "Tiempo registrado.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("checador:historial")


def _parse_dt(valor):
    """Parsea un <input type=datetime-local> ('YYYY-MM-DDTHH:MM') a aware MX."""
    if not valor:
        return None
    try:
        naive = datetime.datetime.fromisoformat(valor)
    except ValueError:
        return None
    return timezone.make_aware(naive) if timezone.is_naive(naive) else naive


# ───────────────────────── historial personal (E4) ─────────────────────────

@login_required
@_requiere_checar
def historial(request):
    from .models import SesionProyecto
    hoy = timezone.localdate()
    desde = hoy - datetime.timedelta(days=hoy.weekday())  # lunes de esta semana
    jornadas = list(
        Jornada.objects.filter(usuario=request.user, fecha__gte=desde, fecha__lte=hoy).order_by("-fecha"),
    )
    visitas = list(
        Visita.objects.filter(usuario=request.user, registrado_en__date__gte=desde, registrado_en__date__lte=hoy)
        .select_related("cliente", "proveedor").order_by("-registrado_en"),
    )
    sesiones = list(
        SesionProyecto.objects.filter(
            usuario=request.user, estado="cerrada", inicio__date__gte=desde, inicio__date__lte=hoy,
        ).select_related("proyecto").order_by("-inicio"),
    )
    mis_correcciones = list(
        SolicitudCorreccion.objects.filter(usuario=request.user).order_by("-creado_en")[:10],
    )
    return render(request, "checador/historial.html", {
        "desde": desde,
        "hoy": hoy,
        "jornadas": jornadas,
        "visitas": visitas,
        "sesiones": sesiones,
        "totales": services.horas_de(request.user, desde, hoy),
        "proyectos": _proyectos_para(request.user),
        "mis_correcciones": mis_correcciones,
        "puede_aprobar": puede_aprobar_correcciones_checador(request.user),
        "puede_ver_equipo": puede_ver_equipo_checador(request.user),
    })


# ───────────────────────── correcciones (E5) ─────────────────────────

@login_required
@_requiere_checar
def correccion_modal(request):
    """GET HTMX → modal para solicitar corrección de una jornada o sesión propia."""
    from .models import SesionProyecto
    jornada = sesion = None
    jid = request.GET.get("jornada")
    sid = request.GET.get("sesion")
    if jid:
        jornada = Jornada.objects.filter(pk=jid, usuario=request.user).first()
    elif sid:
        sesion = SesionProyecto.objects.filter(pk=sid, usuario=request.user).select_related("proyecto").first()
    if jornada is None and sesion is None:
        return HttpResponseForbidden("Registro no encontrado.")
    return render(request, "checador/_modal_correccion.html", {"jornada": jornada, "sesion": sesion})


@login_required
@_requiere_checar
@require_POST
def correccion(request):
    from .models import SesionProyecto
    tipo = request.POST.get("tipo", "")
    motivo = (request.POST.get("motivo") or "").strip()
    valor = _parse_dt(request.POST.get("valor_propuesto"))

    jornada = sesion = None
    jid = request.POST.get("jornada")
    sid = request.POST.get("sesion")
    if jid:
        jornada = Jornada.objects.filter(pk=jid, usuario=request.user).first()
    elif sid:
        sesion = SesionProyecto.objects.filter(pk=sid, usuario=request.user).first()

    if valor is None or not motivo or (jornada is None and sesion is None):
        messages.error(request, "Indica el nuevo valor y el motivo.")
        return redirect("checador:historial")
    if tipo not in ("entrada", "salida", "sesion", "visita"):
        tipo = "sesion" if sesion else "entrada"

    try:
        services.solicitar_correccion(
            request.user, tipo=tipo, valor_propuesto=valor, motivo=motivo,
            jornada=jornada, sesion=sesion,
        )
        messages.success(request, "Solicitud de corrección enviada. Un administrador la revisará.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("checador:historial")


@login_required
@_requiere_aprobar
def correcciones(request):
    """Bandeja de aprobación (Taller) para quien tiene aprobar_correcciones."""
    pendientes = list(
        SolicitudCorreccion.objects.filter(estado="pendiente")
        .select_related("usuario", "jornada", "sesion").order_by("creado_en"),
    )
    resueltas = list(
        SolicitudCorreccion.objects.exclude(estado="pendiente")
        .select_related("usuario", "resuelto_por").order_by("-resuelto_en")[:20],
    )
    return render(request, "checador/correcciones.html", {
        "pendientes": pendientes,
        "resueltas": resueltas,
    })


@login_required
@_requiere_aprobar
def correccion_resolver_modal(request, pk: int):
    sol = get_object_or_404(SolicitudCorreccion, pk=pk)
    return render(request, "checador/_modal_resolver.html", {"sol": sol})


@login_required
@_requiere_aprobar
@require_POST
def correccion_resolver(request, pk: int):
    sol = get_object_or_404(SolicitudCorreccion, pk=pk)
    aprobar = request.POST.get("decision") == "aprobar"
    comentario = (request.POST.get("comentario") or "").strip()
    try:
        services.resolver_correccion(sol, admin=request.user, aprobar=aprobar, comentario=comentario)
        messages.success(request, "Corrección aprobada." if aprobar else "Corrección rechazada.")
    except ValueError as exc:
        messages.error(request, str(exc))
    if request.headers.get("HX-Request") == "true":
        from django.http import HttpResponse
        return HttpResponse(status=204, headers={"HX-Redirect": "/checador/correcciones/"})
    return redirect("checador:correcciones")


# ───────────────────────── reporte de equipo + export (E6) ─────────────────────────

def _parse_date(valor):
    if not valor:
        return None
    try:
        return datetime.date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


@login_required
@_requiere_ver_equipo
def equipo(request):
    from django.db.models import Q

    from cuentas.models.usuario import Usuario
    hoy = timezone.localdate()
    desde = _parse_date(request.GET.get("desde")) or (hoy - datetime.timedelta(days=hoy.weekday()))
    hasta = _parse_date(request.GET.get("hasta")) or hoy

    filas = []
    for u in Usuario.objects.filter(is_active=True).order_by("nombre_completo"):
        agg = services.horas_de(u, desde, hasta)
        if not (agg["dias"] or agg["visitas"] or agg["sesiones_min"]):
            continue
        sin_geo = (
            Jornada.objects.filter(usuario=u, fecha__gte=desde, fecha__lte=hasta)
            .filter(Q(entrada_sin_geo=True) | Q(salida_sin_geo=True)).count()
        )
        filas.append({"usuario": u, "sin_geo": sin_geo, **agg})

    qs = request.GET.urlencode()
    return render(request, "checador/equipo.html", {
        "filas": filas, "desde": desde, "hasta": hasta,
        "querystring": qs,
        "puede_exportar": puede_exportar_checador(request.user),
    })


@login_required
@_requiere_ver_equipo
def equipo_export(request):
    if not puede_exportar_checador(request.user):
        return HttpResponseForbidden("Sin permiso para exportar.")
    from .exports import VISTAS, responder_csv
    vista = request.GET.get("vista", "jornadas")
    if vista not in VISTAS:
        vista = "jornadas"
    response, n = responder_csv(vista, request.GET.dict())
    emitir_kwargs = {"vista": vista, "filas": n, "desde": request.GET.get("desde", ""), "hasta": request.GET.get("hasta", "")}
    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz
    emitir(EventoPortavoz(
        tipo="checador.exportado",
        actor_id=request.user.pk, actor_email=request.user.email, payload=emitir_kwargs,
    ))
    return response


# ───────────────────────── cola offline / sync (E7) ─────────────────────────

@login_required
@_requiere_checar
@require_POST
def api_sync(request):
    """Recibe un lote de checadas/visitas encoladas offline y las aplica.

    Idempotente por `uuid` (los services ya lo son). Responde el estado por
    item para que el cliente borre los aplicados y reintente los que fallen.
    El lote se procesa en orden (la entrada antes que la salida).
    """
    import json

    from apps.el_catalogo.models import Proveedor
    from apps.la_cartera.models import Cliente
    from django.http import JsonResponse

    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return JsonResponse({"error": "JSON inválido"}, status=400)

    items = data.get("items") or []
    if not isinstance(items, list):
        return JsonResponse({"error": "items debe ser una lista"}, status=400)

    resultados = []
    for it in items[:100]:
        if not isinstance(it, dict):
            continue
        uuid = (str(it.get("uuid") or ""))[:64]
        tipo = it.get("tipo")
        reg = _parse_dt(it.get("registrado_en"))
        geo = {
            "lat": it.get("lat"), "lng": it.get("lng"),
            "precision": it.get("precision"), "sin_geo": bool(it.get("sin_geo")),
        }
        try:
            if tipo == "entrada":
                services.checar_entrada(request.user, geo=geo, registrado_en=reg, uuid=uuid, offline=True)
            elif tipo == "salida":
                services.checar_salida(request.user, geo=geo, registrado_en=reg, uuid=uuid, offline=True)
            elif tipo == "visita":
                vtipo = it.get("visita_tipo", "cliente")
                cliente = proveedor = None
                if vtipo == "cliente" and it.get("cliente"):
                    cliente = Cliente.objects.filter(pk=it.get("cliente")).first()
                elif vtipo == "proveedor" and it.get("proveedor"):
                    proveedor = Proveedor.objects.filter(pk=it.get("proveedor")).first()
                services.registrar_visita(
                    request.user, tipo=vtipo, cliente=cliente, proveedor=proveedor,
                    geo=geo, registrado_en=reg, nota=(it.get("nota") or ""), uuid=uuid, offline=True,
                )
            else:
                raise ValueError("Tipo de checada desconocido.")
            resultados.append({"uuid": uuid, "ok": True})
        except ValueError as exc:
            resultados.append({"uuid": uuid, "ok": False, "error": str(exc)})

    return JsonResponse({"resultados": resultados})


@login_required
@_requiere_checar
@require_POST
def checar(request):
    accion = request.POST.get("accion", "entrada")
    geo = _geo_de_request(request)
    uuid = (request.POST.get("uuid") or "")[:64]

    try:
        if accion == "salida":
            services.checar_salida(request.user, geo=geo, uuid=uuid)
            messages.success(request, "Registramos tu salida. ¡Buen descanso!")
        else:
            jornada = services.checar_entrada(request.user, geo=geo, uuid=uuid)
            if jornada.retardo_min:
                messages.warning(request, f"Entrada registrada con {jornada.retardo_min} min de retardo.")
            else:
                messages.success(request, "Entrada registrada. ¡A tiempo!")
        if geo.get("sin_geo"):
            messages.info(request, "Se registró sin ubicación (GPS no disponible).")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("checador:tablero")
