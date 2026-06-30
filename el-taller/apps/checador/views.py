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
    puede_configurar_horarios_checador,
    puede_exportar_checador,
    puede_ver_equipo_checador,
)

from . import services
from .models import Jornada, SolicitudCorreccion, Visita


def _puede_ajustar_directo(user) -> bool:
    """Puede editar/registrar jornadas de OTROS directamente (como un proyecto):
    quien aprueba correcciones o configura horarios."""
    return puede_aprobar_correcciones_checador(user) or puede_configurar_horarios_checador(user)


def _combinar(fecha, hhmm):
    """`fecha` (date) + 'HH:MM' → datetime aware; None si falta o es inválido."""
    if not fecha or not hhmm:
        return None
    try:
        h, m = (int(x) for x in str(hhmm).split(":")[:2])
        return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(h, m)))
    except (ValueError, TypeError):
        return None


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

    # Decisión Oscar: tras checar salida, NO se bloquea el día. Si la persona
    # trabaja más horas puede volver a checar entrada y se acumulan (el auto
    # check-out solo aplica a quien no checó salida antes de las 05:00).
    jornada_cerrada_hoy = bool(jornada and jornada.entrada_en and jornada.salida_en)
    if jornada is None or not jornada.entrada_en:
        accion = "entrada"
    elif not jornada.salida_en:
        accion = "salida"
    else:
        accion = "entrada"  # jornada cerrada → permitir re-entrada (horas extra)

    desde = hoy - datetime.timedelta(days=6)
    filas = services.filas_semana(request.user, desde, hoy)
    visitas_hoy = list(
        Visita.objects.filter(usuario=request.user, registrado_en__date=hoy)
        .select_related("cliente", "proveedor").order_by("-registrado_en"),
    )

    # Sedes activas con pin → para el mini-mapa de verificación antes de checar
    # (item 6) y para que el usuario vea contra qué ubicaciones se valida.
    sedes_mapa = [
        {"n": s.nombre, "lat": float(s.lat), "lng": float(s.lng), "r": s.radio_m}
        for s in services.sedes_activas()
    ]

    return render(request, "checador/tablero.html", {
        "jornada": jornada,
        "accion": accion,
        "jornada_cerrada_hoy": jornada_cerrada_hoy,
        "filas_semana": filas,
        "balance": services.balance_mensual(request.user),
        "balance_semana": services.balance_semana(request.user),
        "visitas_hoy": visitas_hoy,
        "hoy": hoy,
        "timer": services.timer_activo(request.user),
        "proyectos": _proyectos_para(request.user),
        "geocerca_modo": services.modo_geocerca(),
        "sedes_mapa": sedes_mapa,
    })


@login_required
def mapa(request):
    """GET HTMX → modal con el mapa (OpenStreetMap) del punto recibido por
    query (lat, lng, etiqueta, cuando, precision). Solo renderiza coordenadas
    que ya se muestran en la página que abrió el modal — no consulta DB.
    Reusable (Checador, perfiles de cliente/proveedor); solo requiere login."""
    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    return render(request, "checador/_modal_mapa.html", {
        "lat": _num(request.GET.get("lat")),
        "lng": _num(request.GET.get("lng")),
        "etiqueta": (request.GET.get("etiqueta") or "Ubicación")[:60],
        "cuando": (request.GET.get("cuando") or "")[:40],
        "precision": _num(request.GET.get("precision")),
    })


def _puede_ver_registro_de(viewer, dueno) -> bool:
    """Puede ver el detalle de un registro: es suyo, o ve las horas de esa
    persona (jefe directo / super_admin, V9)."""
    if getattr(viewer, "pk", None) == getattr(dueno, "pk", None):
        return True
    from lib.permisos import puede_ver_horas_trabajadas_de
    return puede_ver_horas_trabajadas_de(viewer, dueno)


@login_required
@_requiere_checar
def jornada_detalle(request, pk):
    """GET HTMX → modal con el detalle de una jornada (chequeo)."""
    jornada = get_object_or_404(Jornada.objects.select_related("sede", "ajustado_por", "usuario"), pk=pk)
    if not _puede_ver_registro_de(request.user, jornada.usuario):
        return HttpResponseForbidden("Sin acceso a este registro.")
    return render(request, "checador/_modal_jornada_detalle.html", {
        "j": jornada, "es_propia": jornada.usuario_id == request.user.pk,
    })


@login_required
@_requiere_checar
def visita_detalle(request, pk):
    """GET HTMX → modal con el detalle de una visita/registro de POI."""
    visita = get_object_or_404(
        Visita.objects.select_related("cliente", "proveedor", "contacto", "contacto__cliente", "tarea", "usuario"),
        pk=pk)
    if not _puede_ver_registro_de(request.user, visita.usuario):
        return HttpResponseForbidden("Sin acceso a este registro.")
    return render(request, "checador/_modal_visita_detalle.html", {"v": visita})


@login_required
@_requiere_checar
def sesion_detalle(request, pk):
    """GET HTMX → modal con el detalle de una sesión de proyecto."""
    from .models import SesionProyecto
    sesion = get_object_or_404(SesionProyecto.objects.select_related("proyecto", "usuario"), pk=pk)
    if not _puede_ver_registro_de(request.user, sesion.usuario):
        return HttpResponseForbidden("Sin acceso a este registro.")
    return render(request, "checador/_modal_sesion_detalle.html", {
        "s": sesion, "es_propia": sesion.usuario_id == request.user.pk,
    })


@login_required
@_requiere_checar
def visita_modal(request):
    """GET HTMX → fragmento del modal para registrar una visita/tarea en un POI."""
    from apps.el_catalogo.models import Proveedor
    from apps.el_pizarron.models import Tarea
    from apps.la_cartera.models import Cliente, ClienteContacto
    return render(request, "checador/_modal_visita.html", {
        "clientes": Cliente.objects.filter(activo=True).order_by("razon_social"),
        "proveedores": Proveedor.objects.filter(activo=True).order_by("razon_social"),
        "contactos": (ClienteContacto.objects.select_related("cliente")
                      .filter(cliente__activo=True).order_by("cliente__razon_social", "nombre")),
        # Tareas abiertas asignadas a la persona (para ligar una tarea cumplida).
        "tareas": (Tarea.objects.select_related("proyecto")
                   .filter(asignada_a=request.user, completada_en__isnull=True)
                   .order_by("fecha_compromiso")[:50]),
    })


@login_required
@_requiere_checar
@require_POST
def visita(request):
    from apps.el_catalogo.models import Proveedor
    from apps.el_pizarron.models import Tarea
    from apps.la_cartera.models import Cliente, ClienteContacto

    tipo = request.POST.get("tipo", "cliente")
    proposito = request.POST.get("proposito", "visita")
    nota = (request.POST.get("nota") or "").strip()
    geo = _geo_de_request(request)
    uuid = (request.POST.get("uuid") or "")[:64]

    cliente = proveedor = contacto = None
    if tipo == "cliente":
        cid = request.POST.get("cliente")
        cliente = Cliente.objects.filter(pk=cid).first() if cid else None
    elif tipo == "proveedor":
        pid = request.POST.get("proveedor")
        proveedor = Proveedor.objects.filter(pk=pid).first() if pid else None
    elif tipo == "contacto":
        coid = request.POST.get("contacto")
        contacto = ClienteContacto.objects.filter(pk=coid).select_related("cliente").first() if coid else None

    tarea = None
    tid = request.POST.get("tarea")
    if tid:
        tarea = Tarea.objects.filter(pk=tid, asignada_a=request.user).first()

    try:
        services.registrar_visita(
            request.user, tipo=tipo, cliente=cliente, proveedor=proveedor,
            contacto=contacto, tarea=tarea, proposito=proposito,
            geo=geo, nota=nota, uuid=uuid,
        )
        messages.success(request, "Registro guardado.")
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
    services.iniciar_timer(request.user, proyecto, geo=_geo_de_request(request))
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
            geo=_geo_de_request(request),
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

_PERIODOS_HISTORIAL = {
    "semana": ("Esta semana", None),     # lunes de esta semana → hoy
    "mes": ("Este mes", None),           # día 1 del mes → hoy
    "30d": ("Últimos 30 días", 30),
}


def _rango_historial(periodo: str, hoy):
    if periodo == "mes":
        return hoy.replace(day=1)
    if periodo == "30d":
        return hoy - datetime.timedelta(days=29)
    return hoy - datetime.timedelta(days=hoy.weekday())  # semana (default)


@login_required
@_requiere_checar
def historial(request):
    from .models import SesionProyecto
    hoy = timezone.localdate()
    periodo = request.GET.get("periodo", "semana")
    if periodo not in _PERIODOS_HISTORIAL:
        periodo = "semana"
    desde = _rango_historial(periodo, hoy)
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
        "periodo": periodo,
        "periodo_label": _PERIODOS_HISTORIAL[periodo][0],
        "periodos": [(slug, etq) for slug, (etq, _) in _PERIODOS_HISTORIAL.items()],
        "jornadas": jornadas,
        # LC 2026-06-29: la tabla muestra TODOS los días del periodo (con
        # 'Pendiente'/'Sin información' para los días sin checada).
        "filas_jornadas": services.jornadas_por_dia(request.user, desde, hoy),
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
    """Bandeja de aprobación (Taller). Cada jefe ve solo a sus subordinados;
    super_admin ve todas (S-LC-Feedback-V7)."""
    pendientes, resueltas = services.bandeja_correcciones_para(request.user)
    return render(request, "checador/correcciones.html", {
        "pendientes": pendientes,
        "resueltas": resueltas,
    })


@login_required
@_requiere_aprobar
def correccion_resolver_modal(request, pk: int):
    sol = get_object_or_404(SolicitudCorreccion, pk=pk)
    return render(request, "checador/_modal_resolver.html", {
        "sol": sol, "sedes": services.sedes_todas(),
    })


@login_required
@_requiere_aprobar
@require_POST
def correccion_resolver(request, pk: int):
    sol = get_object_or_404(SolicitudCorreccion, pk=pk)
    aprobar = request.POST.get("decision") == "aprobar"
    comentario = (request.POST.get("comentario") or "").strip()
    try:
        services.resolver_correccion(
            sol, admin=request.user, aprobar=aprobar, comentario=comentario,
            sede=_sede_de_request(request), sede_texto=request.POST.get("sede_texto"),
        )
        messages.success(request, "Corrección aprobada." if aprobar else "Corrección rechazada.")
    except ValueError as exc:
        messages.error(request, str(exc))
    if request.headers.get("HX-Request") == "true":
        from django.http import HttpResponse
        return HttpResponse(status=204, headers={"HX-Redirect": "/checador/correcciones/"})
    return redirect("checador:correcciones")


@login_required
@_requiere_aprobar
@require_POST
def correccion_resolver_chat(request, pk: int):
    """Aprueba/rechaza una corrección DESDE el chat de Recados. Devuelve el
    partial de estado para swap inline en la burbuja (HTMX outerHTML)."""
    sol = get_object_or_404(SolicitudCorreccion, pk=pk)
    mensaje_id = request.POST.get("mensaje_id", "")
    if sol.estado == "pendiente":
        import contextlib
        aprobar = request.POST.get("decision") == "aprobar"
        comentario = (request.POST.get("comentario") or "").strip()
        # Si otro admin la resolvió en paralelo, caemos al render del estado actual.
        with contextlib.suppress(ValueError):
            services.resolver_correccion(sol, admin=request.user, aprobar=aprobar, comentario=comentario)
        sol.refresh_from_db()
    return render(request, "checador/_correccion_chat_estado.html", {
        "sol": sol, "mensaje_id": mensaje_id, "puede_aprobar_corr": True,
    })


# ───────────── ajuste de jornada completa (V1.3) ─────────────

@login_required
@_requiere_checar
def ajuste_jornada_modal(request):
    """Empleado: modal para pedir ajuste de su jornada (entrada+salida) o
    registrar un día que no checó. ?jornada=<pk> prefilla un día existente."""
    jornada = None
    jid = request.GET.get("jornada")
    if jid:
        jornada = Jornada.objects.filter(pk=jid, usuario=request.user).first()
    # ?fecha=YYYY-MM-DD prefilla un día sin checar (botón "Solicitar día" del
    # historial, LC 2026-06-29).
    fecha_prefill = request.GET.get("fecha") or ""
    return render(request, "checador/_modal_ajuste_jornada.html",
                  {"jornada": jornada, "fecha_prefill": fecha_prefill})


@login_required
@_requiere_checar
@require_POST
def ajuste_jornada(request):
    fecha = _parse_date(request.POST.get("fecha"))
    if fecha is None:
        messages.error(request, "Indica el día de la jornada.")
        return redirect("checador:historial")
    entrada = _combinar(fecha, request.POST.get("entrada"))
    salida = _combinar(fecha, request.POST.get("salida"))
    motivo = (request.POST.get("motivo") or "").strip()
    sede_texto = (request.POST.get("sede_texto") or "").strip()
    try:
        services.solicitar_ajuste_jornada(
            request.user, fecha=fecha, valor_entrada=entrada, valor_salida=salida,
            motivo=motivo, sede_texto=sede_texto,
        )
        messages.success(request, "Solicitud de ajuste enviada. Un administrador la revisará.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("checador:historial")


@login_required
def jornada_admin_modal(request, usuario_pk):
    """Admin: modal para editar/registrar DIRECTO la jornada de un empleado."""
    if not _puede_ajustar_directo(request.user):
        return HttpResponseForbidden("Sin permiso para ajustar jornadas.")
    from cuentas.models.usuario import Usuario
    persona = get_object_or_404(Usuario, pk=usuario_pk)
    jornada = None
    jid = request.GET.get("jornada")
    if jid:
        jornada = Jornada.objects.filter(pk=jid, usuario=persona).first()
    return render(request, "checador/_modal_jornada_admin.html", {
        "persona": persona, "jornada": jornada,
        "sedes": services.sedes_todas(),
        "querystring": request.GET.get("q", ""),
    })


@login_required
@require_POST
def jornada_admin_editar(request, usuario_pk):
    if not _puede_ajustar_directo(request.user):
        return HttpResponseForbidden("Sin permiso para ajustar jornadas.")
    from cuentas.models.usuario import Usuario
    persona = get_object_or_404(Usuario, pk=usuario_pk)
    fecha = _parse_date(request.POST.get("fecha"))
    if fecha is None:
        messages.error(request, "Indica el día.")
        return redirect("checador:equipo_persona", pk=persona.pk)
    entrada = _combinar(fecha, request.POST.get("entrada"))
    salida = _combinar(fecha, request.POST.get("salida"))
    if entrada is None and salida is None:
        messages.error(request, "Indica al menos la hora de entrada o de salida.")
        return redirect("checador:equipo_persona", pk=persona.pk)
    sede = _sede_de_request(request)
    services.editar_jornada_directo(
        usuario=persona, fecha=fecha, valor_entrada=entrada, valor_salida=salida,
        admin=request.user, sede=sede, sede_texto=(request.POST.get("sede_texto") or "").strip(),
    )
    messages.success(request, f"Jornada del {fecha:%d/%m} ajustada.")
    return redirect("checador:equipo_persona", pk=persona.pk)


# ───────────────────────── reporte de equipo + export (E6) ─────────────────────────

def _parse_date(valor):
    if not valor:
        return None
    try:
        return datetime.date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


def _sede_de_request(request):
    """SedeLC del POST (`sede`), o None si no se eligió/es inválida."""
    sid = request.POST.get("sede")
    if not sid:
        return None
    from .models import SedeLC
    return SedeLC.objects.filter(pk=sid).first()


@login_required
@_requiere_ver_equipo
def equipo(request):
    from django.db.models import Q

    from cuentas.models.usuario import Usuario
    from lib.permisos import puede_ver_horas_trabajadas_de
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
        # V9: las horas trabajadas solo se muestran a su jefe directo / super_admin.
        filas.append({
            "usuario": u, "sin_geo": sin_geo,
            "ver_horas": puede_ver_horas_trabajadas_de(request.user, u),
            **agg,
        })

    qs = request.GET.urlencode()
    return render(request, "checador/equipo.html", {
        "filas": filas, "desde": desde, "hasta": hasta,
        "querystring": qs,
        "puede_exportar": puede_exportar_checador(request.user),
    })


@login_required
@_requiere_ver_equipo
def equipo_persona(request, pk):
    """Detalle de un miembro del equipo. Las HORAS TRABAJADAS (jornadas con
    mapa, totales, visitas) solo las ve su jefe directo o super_admin (V9). El
    resto solo ve el HORARIO DECLARADO de la semana."""
    from cuentas.models.usuario import Usuario
    from lib.permisos import puede_ver_horas_trabajadas_de

    from .models import SesionProyecto
    persona = get_object_or_404(Usuario, pk=pk)
    hoy = timezone.localdate()
    desde = _parse_date(request.GET.get("desde")) or (hoy - datetime.timedelta(days=hoy.weekday()))
    hasta = _parse_date(request.GET.get("hasta")) or hoy
    ver_horas = puede_ver_horas_trabajadas_de(request.user, persona)

    jornadas, visitas, sesiones, totales = [], [], [], None
    if ver_horas:
        jornadas = list(
            Jornada.objects.filter(usuario=persona, fecha__gte=desde, fecha__lte=hasta).order_by("-fecha"),
        )
        visitas = list(
            Visita.objects.filter(usuario=persona, registrado_en__date__gte=desde, registrado_en__date__lte=hasta)
            .select_related("cliente", "proveedor").order_by("-registrado_en"),
        )
        sesiones = list(
            SesionProyecto.objects.filter(
                usuario=persona, estado="cerrada", inicio__date__gte=desde, inicio__date__lte=hasta,
            ).select_related("proyecto").order_by("-inicio"),
        )
        totales = services.horas_de(persona, desde, hasta)

    return render(request, "checador/equipo_persona.html", {
        "persona": persona, "desde": desde, "hasta": hasta,
        "jornadas": jornadas, "visitas": visitas, "sesiones": sesiones,
        "totales": totales,
        "ver_horas": ver_horas,
        "horario_semana": services.horario_semanal(persona),
        "querystring": request.GET.urlencode(),
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
                from apps.la_cartera.models import ClienteContacto
                vtipo = it.get("visita_tipo", "cliente")
                cliente = proveedor = contacto = None
                if vtipo == "cliente" and it.get("cliente"):
                    cliente = Cliente.objects.filter(pk=it.get("cliente")).first()
                elif vtipo == "proveedor" and it.get("proveedor"):
                    proveedor = Proveedor.objects.filter(pk=it.get("proveedor")).first()
                elif vtipo == "contacto" and it.get("contacto"):
                    contacto = ClienteContacto.objects.filter(pk=it.get("contacto")).select_related("cliente").first()
                services.registrar_visita(
                    request.user, tipo=vtipo, cliente=cliente, proveedor=proveedor,
                    contacto=contacto, proposito=it.get("proposito", "visita"),
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
            if jornada.reabierta:
                messages.success(request, "Entrada registrada. Estas horas se suman a las de hoy.")
            elif jornada.retardo_min:
                messages.warning(request, f"Entrada registrada con {jornada.retardo_min} min de retardo.")
            else:
                messages.success(request, "Entrada registrada. ¡A tiempo!")
        if geo.get("sin_geo"):
            messages.info(request, "Se registró sin ubicación (GPS no disponible).")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("checador:tablero")
