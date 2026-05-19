"""Reglas heurísticas de sugerencia de KPIs (Capa 2 — sin LLM, siempre activas).

Cuando el usuario abre la Sala de Juntas, se evalúan estas reglas. Cada regla
es un dict con:
- `slug`: KPI a sugerir
- `motivo`: texto humano para el banner
- `disparar(user)`: callable que retorna `True` si la sugerencia aplica

Se persiste una fila en `SugerenciaKPI(estado='pendiente')` la primera vez
que dispara. Si el usuario la descarta (`estado='descartada'`), no se vuelve
a sugerir el mismo slug (la unicidad `(usuario, kpi_slug)` lo garantiza).

La Capa 2 con LLM real del Chalán Claudio se cablea en S2b.2+ vía nuevo
campo `fuente='chalan_llm'` en `SugerenciaKPI` y un job periódico.
"""

from __future__ import annotations

from datetime import timedelta

from .kpis import kpi_por_slug


def _tareas_vencidas_equipo_count(user) -> int:
    from datetime import date

    from apps.el_pizarron.models import Tarea
    return Tarea.objects.filter(fecha_compromiso__lt=date.today()).exclude(estado="completada").count()


def _proyectos_inactivos_count(user) -> int:
    from apps.los_proyectos.models import Proyecto
    from django.utils import timezone
    limite = timezone.now() - timedelta(days=14)
    return Proyecto.objects.filter(
        estado__in=("en_diseno", "revision_cliente", "en_produccion"),
        actualizado_en__lt=limite,
    ).count()


def _buzon_pendiente_count(user) -> int:
    from buzon.models import MensajeBuzon
    return MensajeBuzon.objects.filter(estado="nuevo").count()


def _es_admin(user) -> bool:
    return getattr(user, "rol", None) in ("super_admin", "dueno")


REGLAS: list[dict] = [
    {
        "slug": "tareas-vencidas-equipo",
        "motivo": "Tu equipo tiene {n} tareas vencidas pero este KPI no está visible para ti.",
        "disparar": lambda u: _es_admin(u) and _tareas_vencidas_equipo_count(u) > 3,
        "contar": _tareas_vencidas_equipo_count,
    },
    {
        "slug": "proyectos-sin-actividad",
        "motivo": "{n} proyectos llevan >14 días sin movimiento — riesgo de cliente perdido.",
        "disparar": lambda u: _es_admin(u) and _proyectos_inactivos_count(u) > 0,
        "contar": _proyectos_inactivos_count,
    },
    {
        "slug": "buzon-sin-responder",
        "motivo": "Hay {n} mensajes del Buzón sin responder.",
        "disparar": lambda u: _es_admin(u) and _buzon_pendiente_count(u) > 2,
        "contar": _buzon_pendiente_count,
    },
    {
        "slug": "mis-tareas-vencidas",
        "motivo": "Tienes tareas vencidas. Actívalo para verlas siempre.",
        "disparar": lambda u: (
            # Solo si NO tiene este KPI ya visible y de hecho tiene tareas vencidas.
            kpi_por_slug("mis-tareas-vencidas").calcular(u)["valor"] > 0
        ),
        "contar": lambda u: kpi_por_slug("mis-tareas-vencidas").calcular(u)["valor"],
    },
]


def evaluar_y_persistir(user) -> int:
    """Evalúa todas las reglas y crea filas `SugerenciaKPI(estado='pendiente')`.

    Idempotente: si la sugerencia ya existe (en cualquier estado), no se duplica.
    Retorna número de sugerencias nuevas creadas.
    """
    from .models import PreferenciaKPI, SugerenciaKPI

    creadas = 0
    pref_ocultas = set(
        PreferenciaKPI.objects.filter(usuario=user, visible=False).values_list("kpi_slug", flat=True)
    )

    for regla in REGLAS:
        slug = regla["slug"]
        kpi = kpi_por_slug(slug)
        if not kpi:
            continue
        rol = getattr(user, "rol", None) or "disenador"
        if rol not in kpi.roles_visible:
            continue
        # Si el usuario ya lo tiene visible explícitamente o lo descartó como sugerencia, skip.
        if slug not in pref_ocultas and PreferenciaKPI.objects.filter(usuario=user, kpi_slug=slug, visible=True).exists():
            continue
        if SugerenciaKPI.objects.filter(usuario=user, kpi_slug=slug).exists():
            continue
        try:
            if not regla["disparar"](user):
                continue
        except Exception:  # noqa: BLE001 — una regla rota no debe romper el dashboard
            continue
        try:
            n = regla["contar"](user)
        except Exception:  # noqa: BLE001
            n = "varias"
        motivo = regla["motivo"].format(n=n)
        SugerenciaKPI.objects.create(usuario=user, kpi_slug=slug, motivo=motivo, fuente="heuristica")
        creadas += 1
    return creadas


def sugerencias_pendientes(user) -> list:
    from .models import SugerenciaKPI
    return list(SugerenciaKPI.objects.filter(usuario=user, estado="pendiente")[:3])
