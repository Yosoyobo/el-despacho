"""El Runner — asignación de repartidor a tareas de entrega/recolección.

S-LC-Proyecto-V2 (Oscar 2026-06-16). Una tarea tipo `entrega`/`recoger` puede
delegarse a un **runner** (quien lleva o recoge). Se elige manual o
automáticamente ("que el sistema/El Chalán designe al menos cargado").

Auto-asignación (S-Chalan-Barrido): si la tarea tiene una ubicación de DESTINO
(fijada con pin o heredada de la última visita geolocalizada al cliente del
proyecto), elige al runner elegible MÁS CERCANO; si no hay destino o ninguna
posición de runner es conocida, cae a "el menos cargado". Sin geocodificación
de paga: las coordenadas vienen de las visitas/jornadas que ya registra El
Checador (regla "gratis o abortamos"). El Chalán también puede asignar/reasignar
por comando (ejecutor `asignar_runner`).
"""

from __future__ import annotations

import contextlib

from lib.permisos import usuarios_runner

TIPOS_RUNNER = ("entrega", "recoger")


def requiere_runner(tarea) -> bool:
    return tarea.tipo in TIPOS_RUNNER


# ── Ubicación (cero costo: reusa snapshots de El Checador) ────────────────────

def ubicacion_actual_de(usuario):
    """Última posición conocida del usuario: su visita geolocalizada más reciente
    o, en su defecto, la entrada de su jornada de hoy. (lat, lng) o None."""
    from datetime import date

    from apps.checador.models import Jornada, Visita
    v = (
        Visita.objects.filter(usuario=usuario, lat__isnull=False, lng__isnull=False)
        .order_by("-registrado_en").values_list("lat", "lng").first()
    )
    if v:
        return v
    j = (
        Jornada.objects.filter(usuario=usuario, fecha=date.today(),
                               entrada_lat__isnull=False, entrada_lng__isnull=False)
        .values_list("entrada_lat", "entrada_lng").first()
    )
    return j or None


def ubicacion_destino_de_tarea(tarea):
    """Destino de la tarea: el pin explícito, o la última visita geolocalizada al
    cliente del proyecto. (lat, lng) o None."""
    if tarea.destino_lat is not None and tarea.destino_lng is not None:
        return (tarea.destino_lat, tarea.destino_lng)
    cliente_id = getattr(getattr(tarea, "proyecto", None), "cliente_id", None)
    if not cliente_id:
        return None
    from apps.checador.models import Visita
    v = (
        Visita.objects.filter(cliente_id=cliente_id, lat__isnull=False, lng__isnull=False)
        .order_by("-registrado_en").values_list("lat", "lng").first()
    )
    return v or None


def pendientes_runner(usuario) -> int:
    """Entregas/recolecciones abiertas (no terminales) asignadas a `usuario`."""
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    from apps.el_pizarron.models.tarea import Tarea
    return (
        Tarea.objects.filter(runner=usuario, tipo__in=TIPOS_RUNNER)
        .exclude(estado__in=slugs_terminales_tarea())
        .count()
    )


def elegir_menos_cargado():
    """Runner elegible con menos pendientes abiertos (None si no hay candidatos)."""
    candidatos = usuarios_runner()
    if not candidatos:
        return None
    return min(candidatos, key=lambda u: (pendientes_runner(u), u.pk))


def elegir_mas_cercano(destino):
    """Runner elegible más cercano a `destino` (lat, lng), desempatando por
    menos cargado. Si NINGÚN candidato tiene posición conocida, devuelve None
    para que el caller caiga a `elegir_menos_cargado`."""
    from apps.checador.models.sede import distancia_m
    if not destino:
        return None
    dest_lat, dest_lng = destino
    candidatos = usuarios_runner()
    con_distancia = []
    for u in candidatos:
        pos = ubicacion_actual_de(u)
        if not pos:
            continue
        d = distancia_m(pos[0], pos[1], dest_lat, dest_lng)
        if d is not None:
            con_distancia.append((d, pendientes_runner(u), u.pk, u))
    if not con_distancia:
        return None
    con_distancia.sort(key=lambda t: (t[0], t[1], t[2]))
    return con_distancia[0][3]


# ── A quién le toca: carga, jornada, recorrido y agenda ──────────────────
#
# Oscar (2026-08-22): «los chalanes asignan las tareas a los runners basado en
# su carga, agenda, recorrido, jornada, etc.».
#
# Se resuelve con un puntaje y no con una llamada a la IA, por tres razones: es
# instantáneo, no cuesta, y sobre todo es EXPLICABLE — cuando alguien pregunte
# «¿por qué le tocó a él?», el sistema puede contestar con la cuenta exacta en
# vez de con una opinión. La IA aporta cuando hay que interpretar lenguaje; aquí
# lo que hay que hacer es comparar números.

# Cuánto pesa cada cosa. Los números salen de qué tan grave es cada situación:
# mandar a alguien que ya se fue a su casa es peor que mandarlo cinco kilómetros
# más lejos, y por eso la jornada pesa mucho más que la distancia.
PESO_FUERA_DE_JORNADA = -1000.0   # ya salió o no ha llegado: prácticamente lo descarta
PESO_POR_MANDADO_ABIERTO = -12.0  # cada pendiente que ya trae
PESO_POR_KM = -1.5                # qué tan lejos está del destino
PESO_DE_PASO = 25.0               # el destino le queda cerca de algo que ya va a hacer
PESO_CHOQUE_AGENDA = -60.0        # tiene un compromiso con hora encima
RADIO_DE_PASO_M = 3000            # "le queda de paso" si está a menos de 3 km de otra parada


def _en_jornada(usuario) -> bool:
    """¿Está trabajando ahora? Jornada de hoy abierta, o sin salida marcada."""
    from datetime import date

    from apps.checador.models import Jornada

    j = Jornada.objects.filter(usuario=usuario, fecha=date.today()).first()
    if j is None:
        return False
    return bool(j.entrada_en) and not j.salida_en


def _compromiso_proximo(usuario) -> bool:
    """¿Trae algo con hora en las próximas dos horas?

    Cargarle una entrega a alguien que tiene una junta en media hora es
    ponerlo a elegir cuál incumple.
    """
    from datetime import date, datetime, time, timedelta

    from apps.el_pizarron.models import Tarea
    from django.utils import timezone

    ahora = timezone.localtime()
    hoy = date.today()
    pendientes = Tarea.objects.filter(
        # `fecha_compromiso` de Tarea es DateField (el de Proyecto es datetime):
        # comparar con `__date` aquí lanza FieldError.
        asignada_a=usuario, archivada=False, fecha_compromiso=hoy,
        hora__isnull=False,
    ).exclude(estado__in=("completada", "cancelada")).values_list("hora", flat=True)
    for h in pendientes:
        cuando = timezone.make_aware(datetime.combine(hoy, h or time(0, 0)))
        if timedelta(0) <= (cuando - ahora) <= timedelta(hours=2):
            return True
    return False


def _le_queda_de_paso(usuario, destino) -> bool:
    """¿El destino está cerca de alguna parada que ya trae?"""
    if not destino:
        return False
    from apps.checador.models.sede import distancia_m
    from apps.el_pizarron.models import Tarea

    otras = Tarea.objects.filter(
        runner=usuario, archivada=False,
        destino_lat__isnull=False, destino_lng__isnull=False,
    ).exclude(estado__in=("completada", "cancelada")).values_list(
        "destino_lat", "destino_lng",
    )
    for lat, lng in otras:
        d = distancia_m(destino[0], destino[1], lat, lng)
        if d is not None and d <= RADIO_DE_PASO_M:
            return True
    return False


def evaluar_runners(tarea) -> list[dict]:
    """Puntúa a cada runner para esta tarea y explica el porqué.

    Devuelve `[{runner, puntaje, razones}]` de mejor a peor. Lo usan la
    asignación automática y El Chalán cuando le preguntan a quién conviene
    dársela.
    """
    from apps.checador.models.sede import distancia_m

    from lib.permisos import usuarios_runner

    destino = ubicacion_destino_de_tarea(tarea)
    filas = []
    for runner in usuarios_runner():
        puntaje = 0.0
        razones: list[str] = []

        trabajando = _en_jornada(runner)
        if not trabajando:
            puntaje += PESO_FUERA_DE_JORNADA
            razones.append("no ha checado entrada hoy")
        else:
            razones.append("en jornada")

        carga = pendientes_runner(runner)
        if carga:
            puntaje += PESO_POR_MANDADO_ABIERTO * carga
            razones.append(f"trae {carga} pendiente{'s' if carga != 1 else ''}")
        else:
            razones.append("sin pendientes")

        if destino:
            pos = ubicacion_actual_de(runner)
            if pos:
                metros = distancia_m(pos[0], pos[1], destino[0], destino[1])
                if metros is not None:
                    km = metros / 1000
                    puntaje += PESO_POR_KM * km
                    razones.append(f"a {km:.1f} km del destino")
            if _le_queda_de_paso(runner, destino):
                puntaje += PESO_DE_PASO
                razones.append("le queda de paso")

        if trabajando and _compromiso_proximo(runner):
            puntaje += PESO_CHOQUE_AGENDA
            razones.append("tiene un compromiso con hora encima")

        filas.append({"runner": runner, "puntaje": round(puntaje, 1), "razones": razones})

    filas.sort(key=lambda f: -f["puntaje"])
    return filas


def elegir_runner_auto(tarea):
    """A quién le toca: el mejor puntaje considerando jornada, carga, distancia,
    recorrido y agenda. Si nadie califica, cae a los criterios de siempre."""
    evaluados = evaluar_runners(tarea)
    if evaluados:
        return evaluados[0]["runner"]
    destino = ubicacion_destino_de_tarea(tarea)
    return elegir_mas_cercano(destino) or elegir_menos_cargado()


def asignar_runner_auto(tarea, *, actor=None):
    """Asigna automáticamente el runner a una tarea de entrega/recolección:
    el MÁS CERCANO al destino si se conoce, si no el MENOS CARGADO. Marca
    `runner_auto`. Devuelve el runner o None. No lanza: si no hay candidatos,
    deja la tarea sin runner."""
    if not requiere_runner(tarea):
        return None
    runner = elegir_runner_auto(tarea)
    if runner is None:
        return None
    from django.utils import timezone
    tarea.runner = runner
    tarea.runner_auto = True
    tarea.requiere_runner = True
    tarea.runner_asignado_en = timezone.now()
    tarea.save(update_fields=["runner", "runner_auto", "requiere_runner", "runner_asignado_en"])
    _notificar_runner(tarea, actor)
    return runner


def asignar_runner(tarea, runner, *, actor=None):
    """Asigna un runner explícito (manual). Marca `runner_auto=False`."""
    from django.utils import timezone
    tarea.runner = runner
    tarea.runner_auto = False
    tarea.requiere_runner = True
    tarea.runner_asignado_en = timezone.now()
    tarea.save(update_fields=["runner", "runner_auto", "requiere_runner", "runner_asignado_en"])
    _notificar_runner(tarea, actor)
    return runner


def aplicar_desde_form(tarea, cleaned, *, actor=None):
    """Aplica la elección de runner del form a una tarea ya guardada (alta o
    edición). Solo hace algo si el tipo es entrega/recoger.

    Idempotente: si la elección coincide con el estado actual NO reasigna ni
    re-notifica (evita un push en cada edición de la tarea). El runner elegido a
    mano puede ser CUALQUIER usuario activo; la auto-asignación elige solo entre
    los elegibles (permiso runner)."""
    if not requiere_runner(tarea):
        return
    elegido = cleaned.get("runner")
    if elegido:
        # Manual y explícito: respeta a quien el usuario eligió aunque no tenga
        # el permiso de runner. Solo reasigna si cambió (runner distinto o
        # venía en auto).
        ya_fijo = tarea.runner_id == elegido.pk and not tarea.runner_auto
        if not ya_fijo:
            asignar_runner(tarea, elegido, actor=actor)
    elif cleaned.get("runner_auto"):
        # Sin runner específico: el sistema designa entre los elegibles. No
        # re-pickea si ya hay una auto-asignación vigente.
        if tarea.runner_id is None or not tarea.runner_auto:
            asignar_runner_auto(tarea, actor=actor)
    elif not tarea.requiere_runner:
        tarea.requiere_runner = True
        tarea.save(update_fields=["requiere_runner"])


def _notificar_runner(tarea, actor):
    """Push al runner — best-effort, nunca tumba la asignación."""
    if not tarea.runner_id or tarea.runner_id == getattr(actor, "id", None):
        return
    with contextlib.suppress(Exception):
        from lib.interfono import enviar_a_usuario
        verbo = "Recoger" if tarea.tipo == "recoger" else "Entregar"
        enviar_a_usuario(
            tarea.runner,
            titulo=f"{verbo}: {tarea.titulo[:60]}",
            cuerpo=f"{tarea.proyecto.codigo} · {tarea.proyecto.cliente.razon_social}",
            url="/mandados/",
            categoria="mandados",
        )
