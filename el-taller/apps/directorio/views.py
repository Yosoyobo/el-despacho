"""Equipo / Directorio en El Taller.

`lista` (READ-ONLY) — cualquier usuario autenticado consulta a sus compañeros.
`perfil` (S-LC-Feedback-V7) — ficha consolidada de un empleado: contacto,
puesto, modalidad/horario, roles efectivos, jefe directo y subordinados,
dirección + pin de geocerca, y un RESUMEN del Checador. El detalle de
asistencia (jornadas/horas) se muestra solo a la propia persona, a su jefe
directo o a quien tenga permiso de ver equipo (privacidad). La edición de la
ficha vive en La Gerencia → El Directorio.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from cuentas.models.usuario import Usuario


@login_required
def lista(request):
    q = (request.GET.get("q") or "").strip()
    incluir_inactivos = request.GET.get("inactivos") == "1"
    usuarios = Usuario.objects.select_related("jefe_directo").order_by("nombre_completo")
    if not incluir_inactivos:
        usuarios = usuarios.filter(is_active=True)
    if q:
        usuarios = usuarios.filter(
            Q(nombre_completo__icontains=q) | Q(email__icontains=q)
            | Q(puesto__icontains=q) | Q(oficina__icontains=q)
        )

    # Render LC 2026-06-30: la lista es un ACORDEÓN. Cada renglón colapsado
    # muestra nombre + puesto·dirección + badges; al expandir, contacto + horario
    # de la semana. Adjuntamos roles y horario por persona (el equipo es chico —
    # el costo de N consultas es despreciable y la ficha nunca se cae).
    from lib.permisos import roles_display
    try:
        from apps.checador import services as ch
    except Exception:  # noqa: BLE001
        ch = None

    equipo = []
    for u in usuarios:
        try:
            horario = ch.horario_semanal(u) if ch else []
        except Exception:  # noqa: BLE001 — el horario nunca tumba la lista
            horario = []
        equipo.append({"u": u, "roles": roles_display(u), "horario": horario})

    # Template namespaced (directorio_taller/) para no colisionar con el
    # `directorio/lista.html` de La Gerencia en el settings combinado de tests.
    return render(request, "directorio_taller/lista.html", {
        "equipo": equipo,
        "q": q,
        "incluir_inactivos": incluir_inactivos,
        "total": len(equipo),
    })


@login_required
def perfil(request, pk: int):
    """Ficha consolidada del empleado (visible a todo el equipo)."""
    try:
        empleado = Usuario.objects.select_related("jefe_directo").get(pk=pk)
    except Usuario.DoesNotExist as e:
        raise Http404("No existe ese empleado.") from e

    from lib.permisos import (
        puede_ver_equipo_checador,
        puede_ver_horas_trabajadas_de,
        roles_display,
        tiene_rol,
    )

    es_self = request.user.pk == empleado.pk
    # V9 (decisión Oscar): las HORAS TRABAJADAS solo las ve el propio empleado,
    # su jefe directo o super_admin. El resto solo ve el HORARIO de la semana.
    ve_checador = puede_ver_horas_trabajadas_de(request.user, empleado)
    # Acceso al reporte por-persona del Checador (link "ver detalle").
    ve_equipo = tiene_rol(request.user, "super_admin") or puede_ver_equipo_checador(request.user)
    # El detalle por-persona del Checador exige permiso de ver equipo. Si el
    # propio usuario no lo tiene, lo mandamos a su historial personal; un jefe
    # sin ese permiso ve solo el resumen (sin link de detalle).
    if ve_equipo:
        detalle_checador_url = reverse("checador:equipo_persona", args=[empleado.pk])
    elif es_self:
        detalle_checador_url = reverse("checador:historial")
    else:
        detalle_checador_url = ""
    # Quién puede editar la ficha (link a Gerencia): super_admin.
    puede_editar_ficha = tiene_rol(request.user, "super_admin")
    # "Ver como" (impersonar): super_admin, no a uno mismo, no a otro super_admin.
    puede_ver_como = (
        tiene_rol(request.user, "super_admin") and not es_self
        and not tiene_rol(empleado, "super_admin")
    )

    resumen_checador = None
    if ve_checador:
        try:
            from apps.checador import services as ch
            hoy = date.today()
            lunes = hoy - timedelta(days=hoy.weekday())
            primero_mes = hoy.replace(day=1)
            resumen_checador = {
                "semana": ch.horas_de(empleado, lunes, hoy),
                "mes": ch.horas_de(empleado, primero_mes, hoy),
            }
        except Exception:  # noqa: BLE001 — el Checador nunca tumba la ficha
            resumen_checador = None

    # S-Roles-V2: toggle "ver como rol" (debug/QA) en el PROPIO perfil del
    # super_admin. Lista los roles a simular (todos menos super_admin, que es
    # simular "ser uno mismo").
    puede_ver_como_rol = tiene_rol(request.user, "super_admin") and es_self
    roles_simulables = []
    if puede_ver_como_rol:
        from cuentas.models.rol import Rol
        roles_simulables = list(
            Rol.objects.exclude(clave="super_admin").order_by("nombre")
        )

    roles = roles_display(empleado)
    subordinados = list(empleado.subordinados.filter(is_active=True).order_by("nombre_completo"))

    # Horario declarado de la semana (visible a todo el equipo) — week-grid.
    try:
        from apps.checador import services as ch
        horario_semana = ch.horario_semanal(empleado)
    except Exception:  # noqa: BLE001 — la ficha nunca se cae por el Checador
        horario_semana = []

    osm_src = ""
    if empleado.tiene_pin:
        from apps.checador.templatetags.checador_extras import osm_embed_src
        osm_src = osm_embed_src(empleado.geo_lat, empleado.geo_lng)

    # Pendientes de la persona (LC 2026-06-30): hasta 10 tareas pendientes
    # asignadas a ella, ordenadas por vencimiento (la más pronta arriba, sin
    # fecha al final). Defensivo — la ficha nunca se cae por esto.
    tareas_pendientes = []
    try:
        from apps.el_pizarron.models import Tarea
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        from django.db.models import F

        tareas_pendientes = list(
            Tarea.objects.filter(asignada_a=empleado)
            .exclude(estado__in=slugs_terminales_tarea())
            .select_related("proyecto", "proyecto__cliente")
            .order_by(F("fecha_compromiso").asc(nulls_last=True), "hora", "-creado_en")[:10]
        )
    except Exception:  # noqa: BLE001
        tareas_pendientes = []

    return render(request, "directorio_taller/perfil.html", {
        "tareas_pendientes": tareas_pendientes,
        "empleado": empleado,
        "roles": roles,
        "subordinados": subordinados,
        "resumen_checador": resumen_checador,
        "ve_checador": ve_checador,
        "detalle_checador_url": detalle_checador_url,
        "horario_semana": horario_semana,
        "puede_editar_ficha": puede_editar_ficha,
        "puede_ver_como": puede_ver_como,
        "puede_ver_como_rol": puede_ver_como_rol,
        "roles_simulables": roles_simulables,
        "osm_src": osm_src,
        "es_self": es_self,
    })
