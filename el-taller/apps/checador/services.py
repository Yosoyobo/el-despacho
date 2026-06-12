"""Servicios de El Checador — jornada, visitas, timer, correcciones, horarios.

Reglas clave (handoff S-Checador):
- Geo es un snapshot puntual al checar; si falla, se registra `sin_geo=True`
  y la checada NO se bloquea.
- Idempotencia: cada checada/visita generada en el cliente lleva un `uuid`;
  reintentar con el mismo uuid devuelve el registro existente (soporte para
  la cola offline de E7).
- La jornada se calcula con `registrado_en` (hora del dispositivo); en
  offline el flag correspondiente queda auditado.
- Errores de usuario se levantan como `ValueError` con mensaje claro
  (dummy proof) — las vistas los muestran al usuario.

Todos los servicios que mutan emiten un evento del Portavoz vía
`transaction.on_commit` (best-effort; nunca tumban la operación).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from lib.fecha import ahora_mx

from .models import HorarioLaboral, Jornada, SesionProyecto, SolicitudCorreccion, Visita

# ───────────────────────── helpers ─────────────────────────

def _emitir(tipo: str, *, actor, payload: dict) -> None:
    """Encola un evento del Portavoz tras el commit. Best-effort."""

    def _post():
        try:
            from lib.portavoz import emitir
            from lib.portavoz_eventos import EventoPortavoz
            emitir(EventoPortavoz(
                tipo=tipo,
                actor_id=getattr(actor, "id", None),
                actor_email=getattr(actor, "email", None),
                payload=payload,
            ))
        except Exception:  # noqa: BLE001 — el evento nunca debe tumbar la checada
            pass

    transaction.on_commit(_post)


def _push(usuario, titulo: str, cuerpo: str, *, url: str = "") -> None:
    """Push del Interfón (categoría 'checador', opt-out). Best-effort tras commit."""

    def _post():
        try:
            from lib.interfono import enviar_a_usuario
            enviar_a_usuario(usuario, titulo, cuerpo, url=url, categoria="checador", origen_modulo="checador")
        except Exception:  # noqa: BLE001 — el push nunca debe tumbar la operación
            pass

    transaction.on_commit(_post)


def _aprobadores():
    """Usuarios activos con permiso de aprobar correcciones."""
    from cuentas.models.usuario import Usuario
    from lib.permisos import puede_aprobar_correcciones_checador
    return [u for u in Usuario.objects.filter(is_active=True) if puede_aprobar_correcciones_checador(u)]


def _aplicar_geo(obj, prefijo: str, geo: dict | None) -> None:
    """Copia lat/lng/precision/sin_geo del dict `geo` a los campos del objeto.

    `prefijo` es "" (Visita) o "entrada_"/"salida_" (Jornada). Si `geo` viene
    vacío o sin coordenadas, marca `sin_geo=True`.
    """
    geo = geo or {}
    lat = geo.get("lat")
    lng = geo.get("lng")
    setattr(obj, f"{prefijo}lat", lat)
    setattr(obj, f"{prefijo}lng", lng)
    setattr(obj, f"{prefijo}precision", geo.get("precision"))
    setattr(obj, f"{prefijo}sin_geo", bool(geo.get("sin_geo")) or lat is None or lng is None)


def horario_vigente(usuario, fecha) -> HorarioLaboral | None:
    """Horario esperado para `usuario` en `fecha`: override del usuario > global."""
    dia = fecha.weekday()  # 0=lunes
    override = HorarioLaboral.objects.filter(usuario=usuario, dia_semana=dia, activo=True).first()
    if override:
        return override
    return HorarioLaboral.objects.filter(usuario__isnull=True, dia_semana=dia, activo=True).first()


def calcular_retardo(horario: HorarioLaboral | None, entrada_dt) -> int:
    """Minutos de retardo de `entrada_dt` contra el horario, descontando
    la tolerancia. 0 si llega a tiempo (o no hay horario para ese día)."""
    if horario is None:
        return 0
    local = timezone.localtime(entrada_dt)
    esperado = local.replace(
        hour=horario.hora_entrada.hour, minute=horario.hora_entrada.minute,
        second=0, microsecond=0,
    )
    minutos_tarde = (local - esperado).total_seconds() / 60
    if minutos_tarde <= horario.tolerancia_min:
        return 0
    return int(minutos_tarde - horario.tolerancia_min)


# ───────────────────────── jornada ─────────────────────────

def checar_entrada(usuario, *, geo=None, registrado_en=None, uuid: str = "", offline: bool = False) -> Jornada:
    """Registra la entrada del día. Idempotente por `uuid`."""
    registrado_en = registrado_en or ahora_mx()
    fecha = timezone.localtime(registrado_en).date()

    with transaction.atomic():
        jornada, _ = Jornada.objects.get_or_create(usuario=usuario, fecha=fecha)
        if jornada.entrada_en:
            if uuid and jornada.entrada_uuid == uuid:
                return jornada  # reintento de la misma checada
            raise ValueError("Ya checaste tu entrada hoy.")
        jornada.entrada_en = registrado_en
        jornada.entrada_offline = offline
        jornada.entrada_uuid = uuid
        _aplicar_geo(jornada, "entrada_", geo)
        jornada.retardo_min = calcular_retardo(horario_vigente(usuario, fecha), registrado_en)
        jornada.estado = "abierta"
        jornada.save()

    _emitir("checador.entrada", actor=usuario, payload={
        "jornada_id": jornada.pk, "fecha": str(fecha),
        "retardo_min": jornada.retardo_min, "sin_geo": jornada.entrada_sin_geo,
    })
    if jornada.retardo_min > 0:
        _emitir("checador.retardo", actor=usuario, payload={
            "jornada_id": jornada.pk, "fecha": str(fecha), "retardo_min": jornada.retardo_min,
        })
    return jornada


def checar_salida(usuario, *, geo=None, registrado_en=None, uuid: str = "", offline: bool = False) -> Jornada:
    """Cierra la jornada abierta del día. Idempotente por `uuid`."""
    registrado_en = registrado_en or ahora_mx()
    fecha = timezone.localtime(registrado_en).date()

    with transaction.atomic():
        try:
            jornada = Jornada.objects.select_for_update().get(usuario=usuario, fecha=fecha)
        except Jornada.DoesNotExist:
            raise ValueError("No has checado entrada hoy.") from None
        if not jornada.entrada_en:
            raise ValueError("No has checado entrada hoy.")
        if jornada.salida_en:
            if uuid and jornada.salida_uuid == uuid:
                return jornada
            raise ValueError("Ya checaste tu salida hoy.")
        jornada.salida_en = registrado_en
        jornada.salida_offline = offline
        jornada.salida_uuid = uuid
        _aplicar_geo(jornada, "salida_", geo)
        jornada.estado = "cerrada"
        jornada.save()

    _emitir("checador.salida", actor=usuario, payload={
        "jornada_id": jornada.pk, "fecha": str(fecha),
        "minutos": jornada.minutos_trabajados, "sin_geo": jornada.salida_sin_geo,
    })
    return jornada


# ───────────────────────── visitas ─────────────────────────

def registrar_visita(usuario, *, tipo: str, cliente=None, proveedor=None, geo=None,
                     registrado_en=None, nota: str = "", uuid: str = "", offline: bool = False) -> Visita:
    """Registra una visita puntual. Valida cliente XOR proveedor según `tipo`.
    Idempotente por `uuid`."""
    registrado_en = registrado_en or ahora_mx()

    if tipo == "cliente":
        if cliente is None:
            raise ValueError("Selecciona el cliente de la visita.")
        proveedor = None
    elif tipo == "proveedor":
        if proveedor is None:
            raise ValueError("Selecciona el proveedor de la visita.")
        cliente = None
    else:  # otro
        cliente = proveedor = None

    if uuid:
        existente = Visita.objects.filter(usuario=usuario, uuid_cliente=uuid).first()
        if existente:
            return existente

    fecha = timezone.localtime(registrado_en).date()
    jornada = Jornada.objects.filter(usuario=usuario, fecha=fecha).first()

    visita = Visita(
        usuario=usuario, jornada=jornada, registrado_en=registrado_en,
        tipo=tipo, cliente=cliente, proveedor=proveedor, nota=nota,
        capturada_offline=offline, uuid_cliente=uuid,
    )
    _aplicar_geo(visita, "", geo)
    visita.save()

    _emitir("checador.visita", actor=usuario, payload={
        "visita_id": visita.pk, "tipo": tipo, "destino": visita.destino,
        "sin_geo": visita.sin_geo,
    })
    return visita


# ───────────────────────── timer de proyecto ─────────────────────────

def iniciar_timer(usuario, proyecto, *, inicio=None) -> SesionProyecto:
    """Inicia un cronómetro. Si hay otro activo, lo cierra automáticamente
    (un solo timer activo por usuario — decisión #2 del handoff)."""
    inicio = inicio or ahora_mx()
    with transaction.atomic():
        activa = SesionProyecto.objects.select_for_update().filter(
            usuario=usuario, estado="activa",
        ).first()
        if activa:
            activa.cerrar(fin=inicio)
            activa.save()
        sesion = SesionProyecto.objects.create(
            usuario=usuario, proyecto=proyecto, inicio=inicio, origen="timer", estado="activa",
        )
    _emitir("checador.sesion_iniciada", actor=usuario, payload={
        "sesion_id": sesion.pk, "proyecto_id": proyecto.pk,
    })
    return sesion


def detener_timer(usuario, *, fin=None) -> SesionProyecto:
    """Detiene el cronómetro activo del usuario. Error claro si no hay ninguno."""
    fin = fin or ahora_mx()
    with transaction.atomic():
        activa = SesionProyecto.objects.select_for_update().filter(
            usuario=usuario, estado="activa",
        ).first()
        if not activa:
            raise ValueError("No tienes un cronómetro activo.")
        activa.cerrar(fin=fin)
        activa.save()
    _emitir("checador.sesion_cerrada", actor=usuario, payload={
        "sesion_id": activa.pk, "proyecto_id": activa.proyecto_id, "duracion_min": activa.duracion_min,
    })
    return activa


def timer_activo(usuario) -> SesionProyecto | None:
    return SesionProyecto.objects.filter(usuario=usuario, estado="activa").select_related("proyecto").first()


def capturar_sesion_manual(usuario, proyecto, *, inicio, fin, nota: str = "") -> SesionProyecto:
    """Captura manual de tiempo por proyecto (sin cronómetro)."""
    if fin <= inicio:
        raise ValueError("La hora de fin debe ser posterior a la de inicio.")
    sesion = SesionProyecto(
        usuario=usuario, proyecto=proyecto, inicio=inicio, origen="manual", nota=nota,
    )
    sesion.cerrar(fin=fin)
    sesion.save()
    _emitir("checador.sesion_cerrada", actor=usuario, payload={
        "sesion_id": sesion.pk, "proyecto_id": proyecto.pk,
        "duracion_min": sesion.duracion_min, "origen": "manual",
    })
    return sesion


# ───────────────────────── correcciones ─────────────────────────

def solicitar_correccion(usuario, *, tipo: str, valor_propuesto, motivo: str,
                         jornada=None, sesion=None, visita=None) -> SolicitudCorreccion:
    """Crea una solicitud de corrección en estado pendiente."""
    if not motivo.strip():
        raise ValueError("Explica el motivo de la corrección.")
    sol = SolicitudCorreccion.objects.create(
        usuario=usuario, tipo=tipo, valor_propuesto=valor_propuesto, motivo=motivo.strip(),
        jornada=jornada, sesion=sesion, visita=visita,
    )
    _emitir("checador.correccion_solicitada", actor=usuario, payload={
        "solicitud_id": sol.pk, "tipo": tipo,
    })
    quien = getattr(usuario, "nombre_completo", "") or getattr(usuario, "email", "Alguien")
    for admin in _aprobadores():
        if admin.pk != getattr(usuario, "pk", None):
            _push(admin, "Corrección de checada pendiente",
                  f"{quien} pide corregir su {sol.get_tipo_display().lower()}.",
                  url="/checador/correcciones/")
    _publicar_correccion_en_recados(sol)
    return sol


def _publicar_correccion_en_recados(sol: SolicitudCorreccion) -> None:
    """Abre/usa una conversación directa (solicitante ↔ cada admin con el
    privilegio) y publica la solicitud con el FK para los botones en la
    burbuja. Best-effort: nunca tumba la solicitud."""
    def _post():
        try:
            from apps.recados import services_chat
            quien = getattr(sol.usuario, "nombre_completo", "") or getattr(sol.usuario, "email", "Alguien")
            from django.utils import timezone as _tz
            valor = _tz.localtime(sol.valor_propuesto).strftime("%d/%m %H:%M")
            cuerpo = (f"🕐 Solicitud de corrección — {sol.get_tipo_display()} → {valor}\n"
                      f"Motivo: {sol.motivo}")
            for admin in _aprobadores():
                if admin.pk == sol.usuario_id:
                    continue
                conv = services_chat.obtener_o_crear_directa(sol.usuario, admin)
                msg = services_chat.enviar_mensaje(conversacion=conv, autor=sol.usuario, cuerpo=cuerpo)
                msg.correccion = sol
                msg.save(update_fields=["correccion"])
            _ = quien  # nombre disponible si se quiere enriquecer el cuerpo
        except Exception:  # noqa: BLE001 — Recados no debe tumbar el Checador
            pass

    transaction.on_commit(_post)


def _publicar_resolucion_en_recados(sol: SolicitudCorreccion, aprobar: bool) -> None:
    """Publica la respuesta del admin en las conversaciones que llevan esta
    corrección, para que el solicitante la vea en Recados. Best-effort."""
    def _post():
        try:
            from apps.recados import services_chat
            estado = "aprobada ✅" if aprobar else "rechazada ❌"
            cuerpo = f"Tu corrección de {sol.get_tipo_display().lower()} fue {estado}."
            if sol.comentario_admin:
                cuerpo += f"\n{sol.comentario_admin}"
            convs = {m.conversacion_id: m.conversacion for m in sol.mensajes_chat.select_related("conversacion").all()}
            for conv in convs.values():
                services_chat.enviar_mensaje(
                    conversacion=conv, autor=sol.resuelto_por, cuerpo=cuerpo, permitir_vacio=True)
        except Exception:  # noqa: BLE001
            pass

    transaction.on_commit(_post)


def _aplicar_correccion(sol: SolicitudCorreccion) -> None:
    """Aplica el valor propuesto a la entidad y recalcula retardo/duración."""
    if sol.tipo == "entrada" and sol.jornada:
        sol.jornada.entrada_en = sol.valor_propuesto
        sol.jornada.retardo_min = calcular_retardo(
            horario_vigente(sol.jornada.usuario, sol.jornada.fecha), sol.valor_propuesto,
        )
        sol.jornada.save(update_fields=["entrada_en", "retardo_min", "actualizado_en"])
    elif sol.tipo == "salida" and sol.jornada:
        sol.jornada.salida_en = sol.valor_propuesto
        if sol.jornada.estado != "cerrada":
            sol.jornada.estado = "cerrada"
        sol.jornada.save(update_fields=["salida_en", "estado", "actualizado_en"])
    elif sol.tipo == "sesion" and sol.sesion:
        # V1: la corrección de sesión ajusta el `fin` y recalcula la duración.
        sol.sesion.cerrar(fin=sol.valor_propuesto)
        sol.sesion.save(update_fields=["fin", "duracion_min", "estado"])
    elif sol.tipo == "visita" and sol.visita:
        sol.visita.registrado_en = sol.valor_propuesto
        sol.visita.save(update_fields=["registrado_en"])


def resolver_correccion(solicitud: SolicitudCorreccion, *, admin, aprobar: bool,
                        comentario: str = "") -> SolicitudCorreccion:
    """Aprueba o rechaza una corrección. Al aprobar aplica el valor."""
    if solicitud.estado != "pendiente":
        raise ValueError("Esta solicitud ya fue resuelta.")
    with transaction.atomic():
        solicitud.estado = "aprobada" if aprobar else "rechazada"
        solicitud.resuelto_por = admin
        solicitud.resuelto_en = ahora_mx()
        solicitud.comentario_admin = comentario
        if aprobar:
            _aplicar_correccion(solicitud)
        solicitud.save()
    _emitir("checador.correccion_resuelta", actor=admin, payload={
        "solicitud_id": solicitud.pk, "aprobada": aprobar,
        "solicitante_id": solicitud.usuario_id,
    })
    estado_txt = "aprobada" if aprobar else "rechazada"
    _push(solicitud.usuario, f"Tu corrección fue {estado_txt}",
          f"La corrección de tu {solicitud.get_tipo_display().lower()} fue {estado_txt}.",
          url="/checador/historial/")
    _publicar_resolucion_en_recados(solicitud, aprobar)
    return solicitud


# ───────────────────────── reportes / agregados ─────────────────────────

def horas_de(usuario, desde, hasta) -> dict:
    """Agregados de jornada y sesiones de proyecto entre `desde` y `hasta`
    (fechas inclusivas). Base de KPIs y reportes."""
    jornadas = list(Jornada.objects.filter(usuario=usuario, fecha__gte=desde, fecha__lte=hasta))
    jornada_min = sum(j.minutos_trabajados or 0 for j in jornadas)
    retardos = sum(1 for j in jornadas if j.retardo_min > 0)

    sesiones = SesionProyecto.objects.filter(
        usuario=usuario, estado="cerrada", inicio__date__gte=desde, inicio__date__lte=hasta,
    )
    sesion_min = sum(s.duracion_min or 0 for s in sesiones)

    visitas = Visita.objects.filter(
        usuario=usuario, registrado_en__date__gte=desde, registrado_en__date__lte=hasta,
    ).count()

    return {
        "dias": len(jornadas),
        "jornada_min": jornada_min,
        "jornada_horas": round(jornada_min / 60, 2),
        "retardos": retardos,
        "sesiones_min": sesion_min,
        "sesiones_horas": round(sesion_min / 60, 2),
        "visitas": visitas,
    }


# ─────────────── recordatorio de entrada no checada (S-Checador-V1.2) ───────────────

def _checadores_candidatos(hoy):
    """Usuarios a los que tiene sentido recordarles checar: habituales (con
    jornada en los últimos 14 días) o con horario propio para hoy. Evita
    molestar a quien nunca usa el Checador."""
    from datetime import timedelta

    from cuentas.models.usuario import Usuario
    desde = hoy - timedelta(days=14)
    ids = set(
        Jornada.objects.filter(fecha__gte=desde).values_list("usuario_id", flat=True),
    )
    ids |= set(
        HorarioLaboral.objects.filter(
            usuario__isnull=False, dia_semana=hoy.weekday(), activo=True,
        ).values_list("usuario_id", flat=True),
    )
    return Usuario.objects.filter(pk__in=ids, is_active=True)


def recordar_entradas_pendientes(*, ahora=None, ventana_horas: int = 6) -> int:
    """Avisa por el Interfón a quien ya pasó su hora de entrada (más la
    tolerancia) y aún no ha checado. Idempotente por día (RecordatorioEntrada).
    No molesta si ya pasó `ventana_horas` desde la hora de entrada (asume que
    no trabaja hoy). Devuelve cuántos avisos se enviaron."""
    from datetime import timedelta

    from .models import RecordatorioEntrada

    ahora = ahora or timezone.now()
    local = timezone.localtime(ahora)
    hoy = local.date()
    enviados = 0

    for u in _checadores_candidatos(hoy):
        horario = horario_vigente(u, hoy)
        if horario is None:
            continue  # no trabaja ese día (p.ej. fin de semana)
        esperado = local.replace(
            hour=horario.hora_entrada.hour, minute=horario.hora_entrada.minute,
            second=0, microsecond=0,
        )
        limite = esperado + timedelta(minutes=horario.tolerancia_min)
        if local < limite:
            continue  # aún no es tarde
        if local > esperado + timedelta(hours=ventana_horas):
            continue  # demasiado tarde — probablemente no trabaja hoy
        jornada = Jornada.objects.filter(usuario=u, fecha=hoy).first()
        if jornada and jornada.entrada_en:
            continue  # ya checó
        _, creado = RecordatorioEntrada.objects.get_or_create(usuario=u, fecha=hoy)
        if not creado:
            continue  # ya se le recordó hoy
        _push(u, "Recuerda checar tu entrada",
              "Aún no registras tu entrada de hoy. Ábrelo y checa cuando puedas.",
              url="/checador/")
        _emitir("checador.recordatorio_entrada", actor=u, payload={"fecha": hoy.isoformat()})
        enviados += 1
    return enviados


# ─────────────── horas trabajadas, proyecto-como-jornada y balance (V1.2) ───────────────

def _min_horario(horario) -> int:
    """Minutos esperados de un horario (salida − entrada)."""
    import datetime as _dt
    base = _dt.date(2000, 1, 1)
    ent = _dt.datetime.combine(base, horario.hora_entrada)
    sal = _dt.datetime.combine(base, horario.hora_salida)
    if sal <= ent:
        return 0
    return int((sal - ent).total_seconds() // 60)


def _proyecto_min_dia(usuario, dia) -> int:
    """Minutos de sesiones de proyecto CERRADAS de un día."""
    from django.db.models import Sum
    total = (
        SesionProyecto.objects.filter(usuario=usuario, estado="cerrada", inicio__date=dia)
        .aggregate(s=Sum("duracion_min"))["s"]
    )
    return int(total or 0)


def _trabajado_min_dia(usuario, dia, jornada=None) -> tuple[int, str]:
    """Minutos trabajados del día + tipo, según la regla:
    - jornada cerrada → sus minutos (tipo 'jornada').
    - jornada ABIERTA en curso → 0 (tipo 'abierta', no cuenta aún).
    - sin jornada pero con tiempo de proyecto → el proyecto cuenta como
      jornada (tipo 'proyecto').
    - nada → 0 (tipo 'vacio').
    """
    if jornada is None:
        jornada = Jornada.objects.filter(usuario=usuario, fecha=dia).first()
    if jornada and jornada.salida_en and jornada.entrada_en:
        return jornada.minutos_trabajados or 0, "jornada"
    if jornada and jornada.entrada_en and not jornada.salida_en:
        return 0, "abierta"
    pmin = _proyecto_min_dia(usuario, dia)
    if pmin > 0:
        return pmin, "proyecto"
    return 0, "vacio"


def filas_semana(usuario, desde, hasta) -> list[dict]:
    """Filas por día (con jornada o con tiempo de proyecto) para 'Mi semana'.
    Cada fila trae jornada, horas de proyecto y horas trabajadas efectivas."""
    import datetime as _dt
    fechas = set()
    for j in Jornada.objects.filter(usuario=usuario, fecha__gte=desde, fecha__lte=hasta):
        fechas.add(j.fecha)
    for d in (SesionProyecto.objects.filter(
            usuario=usuario, estado="cerrada", inicio__date__gte=desde, inicio__date__lte=hasta)
            .values_list("inicio", flat=True)):
        fechas.add(timezone.localtime(d).date() if timezone.is_aware(d) else d.date())

    jornadas = {j.fecha: j for j in Jornada.objects.filter(usuario=usuario, fecha__in=fechas)}
    filas = []
    for dia in sorted(fechas, reverse=True):
        jornada = jornadas.get(dia)
        pmin = _proyecto_min_dia(usuario, dia)
        trabajado, tipo = _trabajado_min_dia(usuario, dia, jornada)
        filas.append({
            "fecha": dia, "jornada": jornada,
            "proyecto_horas": round(pmin / 60, 2),
            "trabajado_horas": round(trabajado / 60, 2) if tipo != "abierta" else None,
            "tipo": tipo,
            "retardo_min": jornada.retardo_min if jornada else 0,
        })
        _ = _dt  # (import usado arriba)
    return filas


def balance_mensual(usuario, *, year: int = None, month: int = None, ahora=None) -> dict:
    """Horas esperadas (de los horarios configurados) vs trabajadas en el mes,
    hasta hoy. Devuelve {esperadas, trabajadas, balance} en horas. Positivo =
    a favor; negativo = deuda. Los días no laborados generan deuda que se
    compensa con horas extra (= balance)."""
    import calendar
    import datetime as _dt

    ahora = ahora or timezone.localtime()
    hoy = ahora.date()
    year = year or hoy.year
    month = month or hoy.month
    ultimo = calendar.monthrange(year, month)[1]
    fin = min(_dt.date(year, month, ultimo), hoy) if (year, month) == (hoy.year, hoy.month) else _dt.date(year, month, ultimo)

    esperadas = 0
    trabajadas = 0
    dia = _dt.date(year, month, 1)
    while dia <= fin:
        horario = horario_vigente(usuario, dia)
        if horario and horario.activo:
            esperadas += _min_horario(horario)
        trab, _tipo = _trabajado_min_dia(usuario, dia)
        trabajadas += trab
        dia += _dt.timedelta(days=1)

    balance = trabajadas - esperadas
    return {
        "esperadas_horas": round(esperadas / 60, 2),
        "trabajadas_horas": round(trabajadas / 60, 2),
        "balance_horas": round(balance / 60, 2),
        "a_favor": balance >= 0,
        "year": year, "month": month,
    }


# ─────────────── auto-cierre de jornadas abiertas (V1.2) ───────────────

def _salida_default_compania(dia):
    """Hora de salida global de la compañía para ese día (horario global,
    usuario NULL). None si no hay."""
    h = HorarioLaboral.objects.filter(
        usuario__isnull=True, dia_semana=dia.weekday(), activo=True,
    ).first()
    return h.hora_salida if h else None


def cerrar_jornadas_vencidas(*, ahora=None) -> int:
    """Cierra jornadas que quedaron abiertas: si no se checó salida antes de
    las 05:00 del día siguiente, se cierra al horario de salida default de la
    compañía de ese día (fallback 18:00). Devuelve cuántas cerró."""
    import datetime as _dt

    ahora = ahora or timezone.now()
    cerradas = 0
    abiertas = Jornada.objects.filter(entrada_en__isnull=False, salida_en__isnull=True)
    for j in abiertas:
        limite = timezone.make_aware(
            _dt.datetime.combine(j.fecha + _dt.timedelta(days=1), _dt.time(5, 0)),
        )
        if ahora < limite:
            continue  # aún tiene hasta las 05:00 del día siguiente
        salida_time = _salida_default_compania(j.fecha) or _dt.time(18, 0)
        salida_dt = timezone.make_aware(_dt.datetime.combine(j.fecha, salida_time))
        if j.entrada_en and salida_dt <= j.entrada_en:
            salida_dt = j.entrada_en  # evita duración negativa (turno nocturno)
        j.salida_en = salida_dt
        j.salida_automatica = True
        j.salida_sin_geo = True
        if j.estado != "cerrada":
            j.estado = "cerrada"
        j.save(update_fields=["salida_en", "salida_automatica", "salida_sin_geo",
                              "estado", "actualizado_en"])
        _emitir("checador.salida", actor=None, payload={
            "jornada_id": j.pk, "usuario_id": j.usuario_id, "automatica": True,
        })
        cerradas += 1
    return cerradas
