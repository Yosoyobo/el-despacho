"""Catálogo declarativo de KPIs para La Sala de Juntas (S2b.4).

Cada KPI es un dataclass `KPI` con:
- `slug`: identificador estable (también clave de `PreferenciaKPI.kpi_slug`)
- `titulo`, `descripcion`
- `categoria`: agrupa visualmente la lista de preferencias
- `roles_visible`: tupla de roles que pueden activarlo
- `origen`: 'manual' (catálogo) | 'sugerido_chalan' (S2b.2+) | 'custom_chalan' (S2b.5)
- `estado_kpi`: 'activo' (calcula) | 'pendiente_tesoreria' (placeholder S2b.3)
- `calcular(user) -> dict`: retorna `{valor, nota, link}`

Agregar un KPI = agregar una entrada a `KPIS`. Las preferencias del usuario
se persisten en `taller_home.PreferenciaKPI`; default opt-in (visible si no
hay fila explícita), opuesto al opt-out de `PreferenciaCategoriaPush` porque
para KPIs el comportamiento natural es "mostrar todo lo que aplica a mi rol".

NOTA: Las consultas se ejecutan en cada render. Para 5 usuarios y ~30 KPIs
visibles el costo es bajo (~30 COUNT con índices). Si crece, agregar caché
con TTL=60s en `taller_home/cache.py` (sprint futuro).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

# ── Constantes auxiliares ──────────────────────────────────────────────────

ESTADOS_PROYECTO_ACTIVOS = ("en_diseno", "revision_cliente", "en_produccion")
ROLES_TODOS = ("super_admin", "dueno", "contador", "disenador")
ROLES_ADMIN = ("super_admin", "dueno")
ROLES_ADMIN_CONTADOR = ("super_admin", "dueno", "contador")


@dataclass(frozen=True)
class KPI:
    slug: str
    titulo: str
    descripcion: str
    categoria: str
    roles_visible: tuple[str, ...]
    calcular: Callable[[Any], dict[str, Any]]
    origen: str = "manual"
    estado_kpi: str = "activo"


# ── Helpers de cálculo (mantienen las queries simples y legibles) ───────────

def _hoy() -> date:
    return date.today()


def _inicio_mes(hoy: date | None = None) -> date:
    hoy = hoy or _hoy()
    return hoy.replace(day=1)


def _inicio_semana(hoy: date | None = None) -> date:
    hoy = hoy or _hoy()
    return hoy - timedelta(days=hoy.weekday())


def _resultado(valor: Any, *, nota: str = "", link: str = "") -> dict[str, Any]:
    return {"valor": valor, "nota": nota, "link": link}


# ── Cálculos por categoría ──────────────────────────────────────────────────


def _kpi_proyectos_activos(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    qs = Proyecto.objects.filter(estado__in=ESTADOS_PROYECTO_ACTIVOS)
    if getattr(user, "rol", None) == "disenador":
        qs = qs.filter(asignaciones__usuario=user).distinct()
    return _resultado(qs.count(), link="/proyectos/?estado=activos")


def _kpi_prospectos_pipeline(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    return _resultado(
        Proyecto.objects.filter(estado="prospecto").count(),
        link="/proyectos/?estado=prospecto",
    )


def _kpi_cotizados_sin_avance(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    from django.utils import timezone
    limite = timezone.now() - timedelta(days=7)
    n = Proyecto.objects.filter(estado="cotizado", actualizado_en__lt=limite).count()
    return _resultado(n, nota=("alerta" if n > 0 else ""), link="/proyectos/?estado=cotizado")


def _kpi_proyectos_en_pausa(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    return _resultado(
        Proyecto.objects.filter(estado="en_pausa").count(),
        link="/proyectos/?estado=en_pausa",
    )


def _kpi_por_entregar_esta_semana(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    hoy = _hoy()
    fin = hoy + timedelta(days=7)
    qs = Proyecto.objects.filter(
        estado__in=ESTADOS_PROYECTO_ACTIVOS,
        fecha_compromiso__gte=hoy,
        fecha_compromiso__lte=fin,
    )
    if getattr(user, "rol", None) == "disenador":
        qs = qs.filter(asignaciones__usuario=user).distinct()
    return _resultado(qs.count())


def _kpi_proyectos_vencidos(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    hoy = _hoy()
    qs = Proyecto.objects.filter(
        estado__in=ESTADOS_PROYECTO_ACTIVOS,
        fecha_compromiso__lt=hoy,
    )
    if getattr(user, "rol", None) == "disenador":
        qs = qs.filter(asignaciones__usuario=user).distinct()
    n = qs.count()
    return _resultado(n, nota=("alerta" if n > 0 else ""))


def _kpi_proyectos_sin_actividad(user) -> dict:
    """Activos sin comentarios ni cambios en 14 días — riesgo de cliente perdido."""
    from apps.los_proyectos.models import Proyecto
    from django.utils import timezone
    limite = timezone.now() - timedelta(days=14)
    qs = Proyecto.objects.filter(
        estado__in=ESTADOS_PROYECTO_ACTIVOS,
        actualizado_en__lt=limite,
    )
    return _resultado(qs.count(), nota=("alerta" if qs.exists() else ""))


def _kpi_proyectos_cancelados_mes(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    return _resultado(
        Proyecto.objects.filter(
            estado="cancelado", actualizado_en__date__gte=_inicio_mes()
        ).count()
    )


# ── Tareas ──


def _kpi_mis_tareas_vencidas(user) -> dict:
    from apps.el_pizarron.models import Tarea
    hoy = _hoy()
    n = Tarea.objects.filter(
        asignada_a=user, fecha_compromiso__lt=hoy,
    ).exclude(estado="completada").count()
    return _resultado(n, nota=("alerta" if n > 0 else ""))


def _kpi_mis_tareas_proximas(user) -> dict:
    """Tareas mías con entrega en los próximos 3 días."""
    from apps.el_pizarron.models import Tarea
    hoy = _hoy()
    fin = hoy + timedelta(days=3)
    n = Tarea.objects.filter(
        asignada_a=user,
        fecha_compromiso__gte=hoy,
        fecha_compromiso__lte=fin,
    ).exclude(estado="completada").count()
    return _resultado(n)


def _kpi_tareas_vencidas_equipo(user) -> dict:
    from apps.el_pizarron.models import Tarea
    hoy = _hoy()
    n = Tarea.objects.filter(fecha_compromiso__lt=hoy).exclude(estado="completada").count()
    return _resultado(n, nota=("alerta" if n > 0 else ""))


def _kpi_tareas_bloqueadas(user) -> dict:
    """Tareas en `bloqueada` — cuellos de botella visibles."""
    from apps.el_pizarron.models import Tarea
    return _resultado(Tarea.objects.filter(estado="bloqueada").count())


def _kpi_tareas_sin_asignar(user) -> dict:
    from apps.el_pizarron.models import Tarea
    return _resultado(
        Tarea.objects.filter(asignada_a__isnull=True).exclude(estado="completada").count()
    )


def _kpi_tareas_completadas_semana(user) -> dict:
    from apps.el_pizarron.models import Tarea
    inicio = _inicio_semana()
    return _resultado(
        Tarea.objects.filter(estado="completada", completada_en__date__gte=inicio).count()
    )


# ── Buzón ──


def _kpi_buzon_sin_responder(user) -> dict:
    from buzon.models import MensajeBuzon
    n = MensajeBuzon.objects.filter(estado="nuevo").count()
    return _resultado(n, nota=("alerta" if n > 0 else ""), link="/buzon/")


def _kpi_buzon_bugs_abiertos(user) -> dict:
    from buzon.models import MensajeBuzon
    return _resultado(
        MensajeBuzon.objects.filter(tipo="problema").exclude(estado="archivado").count(),
        link="/buzon/?tipo=problema",
    )


def _kpi_buzon_sugerencias(user) -> dict:
    from buzon.models import MensajeBuzon
    return _resultado(
        MensajeBuzon.objects.filter(tipo="sugerencia", estado="nuevo").count(),
        link="/buzon/?tipo=sugerencia",
    )


def _kpi_buzon_mios_sin_responder(user) -> dict:
    """Mensajes que yo (autor) envié y no han sido respondidos."""
    from buzon.models import MensajeBuzon
    return _resultado(
        MensajeBuzon.objects.filter(autor=user).exclude(estado="respondido").exclude(estado="archivado").count(),
    )


# ── Recados ──


def _kpi_mis_recados_no_leidos(user) -> dict:
    from apps.recados.models import RecadoDestinatario
    n = RecadoDestinatario.objects.filter(usuario=user, leido_en__isnull=True).count()
    return _resultado(n, link="/recados/?tab=no_leidos")


def _kpi_recados_enviados_semana(user) -> dict:
    from apps.recados.models import Recado
    return _resultado(
        Recado.objects.filter(autor=user, creado_en__date__gte=_inicio_semana()).count()
    )


# ── Cartera ──


def _kpi_clientes_activos(user) -> dict:
    from apps.la_cartera.models import Cliente
    return _resultado(Cliente.objects.filter(activo=True).count(), link="/cartera/")


def _kpi_clientes_nuevos_mes(user) -> dict:
    from apps.la_cartera.models import Cliente
    return _resultado(
        Cliente.objects.filter(activo=True, creado_en__date__gte=_inicio_mes()).count()
    )


def _kpi_clientes_sin_proyectos(user) -> dict:
    """Oportunidades de cross-sell — clientes activos sin proyecto vivo."""
    from apps.la_cartera.models import Cliente
    qs = Cliente.objects.filter(activo=True).exclude(
        proyectos__estado__in=ESTADOS_PROYECTO_ACTIVOS,
    ).distinct()
    return _resultado(qs.count())


def _kpi_clientes_con_pry_activos(user) -> dict:
    from apps.la_cartera.models import Cliente
    qs = Cliente.objects.filter(
        activo=True, proyectos__estado__in=ESTADOS_PROYECTO_ACTIVOS,
    ).distinct()
    return _resultado(qs.count())


# ── Infraestructura ──


def _kpi_interfon_suscripciones(user) -> dict:
    from interfono.models import InterfonoSuscripcion
    return _resultado(InterfonoSuscripcion.objects.filter(activa=True).count())


def _kpi_interfon_pushes_semana(user) -> dict:
    from interfono.models import InterfonoEntrega
    return _resultado(
        InterfonoEntrega.objects.filter(enviado_en__date__gte=_inicio_semana()).count()
    )


def _kpi_site_integraciones_rojo(user) -> dict:
    """Conteo de integraciones del Site con último chequeo en estado 'error'."""
    try:
        from apps.el_site.models import SiteChequeo
    except ImportError:
        return _resultado("—", nota="(SiteChequeo no disponible)")
    # Última fila por plataforma con estado='error'.
    desde = _hoy() - timedelta(days=2)
    qs = SiteChequeo.objects.filter(estado="error", creado_en__date__gte=desde).values("plataforma").distinct()
    n = qs.count()
    return _resultado(n, nota=("alerta" if n > 0 else ""), link="/site/")


# ── Dinero (placeholders — calculados con campos del modelo de proyecto) ──


def _kpi_ingresos_mes(user) -> dict:
    """Suma de `monto_cobrado` de proyectos cobrados este mes."""
    from apps.los_proyectos.models import Proyecto
    from django.db.models import Sum
    inicio = _inicio_mes()
    total = Proyecto.objects.filter(
        actualizado_en__date__gte=inicio,
    ).aggregate(s=Sum("monto_cobrado"))["s"] or 0
    return _resultado(f"${total:,.0f}", nota="(estimado parcial — completar con S2b.3 La Tesorería)")


def _kpi_cxc_total(user) -> dict:
    """`monto_facturado - monto_cobrado` agregado de proyectos no-terminales."""
    from apps.los_proyectos.models import ESTADOS_TERMINALES, Proyecto
    from django.db.models import F, Sum
    qs = Proyecto.objects.exclude(estado__in=ESTADOS_TERMINALES)
    total = qs.aggregate(s=Sum(F("monto_facturado") - F("monto_cobrado")))["s"] or 0
    return _resultado(f"${total:,.0f}", nota="(estimado parcial — S2b.3)")


# ── Catálogo ──

KPIS: list[KPI] = [
    # Operación
    KPI("proyectos-activos", "Proyectos activos", "Proyectos en diseño, revisión o producción.",
        "operacion", ROLES_TODOS, _kpi_proyectos_activos),
    KPI("prospectos-pipeline", "Prospectos en pipeline", "Clientes potenciales con conversación abierta.",
        "operacion", ROLES_ADMIN_CONTADOR, _kpi_prospectos_pipeline),
    KPI("cotizados-sin-avance", "Cotizados >7d sin avance", "Cotización enviada y sin movimiento. Velocidad comercial.",
        "operacion", ROLES_ADMIN_CONTADOR, _kpi_cotizados_sin_avance),
    KPI("proyectos-en-pausa", "Proyectos en pausa", "Pausados — insumos atrasados, cliente desaparecido.",
        "operacion", ROLES_ADMIN_CONTADOR, _kpi_proyectos_en_pausa),
    KPI("por-entregar-esta-semana", "Por entregar esta semana", "Proyectos con fecha de entrega en los próximos 7 días.",
        "operacion", ROLES_TODOS, _kpi_por_entregar_esta_semana),
    KPI("proyectos-vencidos", "Proyectos vencidos", "Activos con fecha de entrega pasada.",
        "operacion", ROLES_TODOS, _kpi_proyectos_vencidos),
    KPI("proyectos-sin-actividad", "Proyectos sin actividad (>14d)", "Activos sin actualizar en 2 semanas — riesgo de cliente perdido.",
        "operacion", ROLES_ADMIN_CONTADOR, _kpi_proyectos_sin_actividad),
    KPI("proyectos-cancelados-mes", "Cancelados este mes", "Señal de churn comercial.",
        "operacion", ROLES_ADMIN, _kpi_proyectos_cancelados_mes),

    # Tareas
    KPI("mis-tareas-vencidas", "Mis tareas vencidas", "Tareas tuyas con fecha de compromiso pasada.",
        "tareas", ROLES_TODOS, _kpi_mis_tareas_vencidas),
    KPI("mis-tareas-proximas-3d", "Mis tareas (próximos 3 días)", "Tareas tuyas que vencen pronto.",
        "tareas", ROLES_TODOS, _kpi_mis_tareas_proximas),
    KPI("tareas-vencidas-equipo", "Tareas vencidas del equipo", "Vista cross-equipo para admins.",
        "tareas", ROLES_ADMIN, _kpi_tareas_vencidas_equipo),
    KPI("tareas-bloqueadas", "Tareas bloqueadas", "Cuellos de botella visibles.",
        "tareas", ROLES_TODOS, _kpi_tareas_bloqueadas),
    KPI("tareas-sin-asignar", "Tareas sin asignar", "Tareas activas sin owner.",
        "tareas", ROLES_ADMIN, _kpi_tareas_sin_asignar),
    KPI("tareas-completadas-semana", "Completadas esta semana", "Throughput del equipo.",
        "tareas", ROLES_ADMIN, _kpi_tareas_completadas_semana),

    # Buzón
    KPI("buzon-sin-responder", "Buzón sin responder", "Mensajes de empleados en estado 'nuevo'.",
        "buzon", ROLES_ADMIN, _kpi_buzon_sin_responder),
    KPI("buzon-bugs-abiertos", "Bugs abiertos", "Mensajes tipo 'problema' no archivados.",
        "buzon", ROLES_ADMIN, _kpi_buzon_bugs_abiertos),
    KPI("buzon-sugerencias", "Sugerencias acumuladas", "Mensajes tipo 'sugerencia' en estado 'nuevo'.",
        "buzon", ROLES_ADMIN, _kpi_buzon_sugerencias),
    KPI("buzon-mios-sin-responder", "Mis mensajes sin responder", "Mensajes que envié al Buzón y siguen abiertos.",
        "buzon", ROLES_TODOS, _kpi_buzon_mios_sin_responder),

    # Recados
    KPI("mis-recados-no-leidos", "Mis recados no leídos", "Mensajería interna sin leer.",
        "recados", ROLES_TODOS, _kpi_mis_recados_no_leidos),
    KPI("recados-enviados-semana", "Recados que envié (semana)", "Mi nivel de actividad en mensajería.",
        "recados", ROLES_TODOS, _kpi_recados_enviados_semana),

    # Cartera
    KPI("clientes-activos", "Clientes activos", "Cartera total sin soft-delete.",
        "cartera", ROLES_ADMIN_CONTADOR, _kpi_clientes_activos),
    KPI("clientes-nuevos-mes", "Clientes nuevos del mes", "Crecimiento de cartera.",
        "cartera", ROLES_ADMIN_CONTADOR, _kpi_clientes_nuevos_mes),
    KPI("clientes-sin-proyectos", "Clientes sin proyectos activos", "Oportunidad de cross-sell.",
        "cartera", ROLES_ADMIN, _kpi_clientes_sin_proyectos),
    KPI("clientes-con-pry-activos", "Clientes con proyectos vivos", "Cuántos clientes están comprándote ahora.",
        "cartera", ROLES_ADMIN_CONTADOR, _kpi_clientes_con_pry_activos),

    # Infraestructura
    KPI("interfon-suscripciones", "Suscripciones del Interfón", "Dispositivos del equipo recibiendo push.",
        "infraestructura", ROLES_ADMIN, _kpi_interfon_suscripciones),
    KPI("interfon-pushes-semana", "Pushes enviados (semana)", "Volumen de notificaciones de la semana.",
        "infraestructura", ROLES_ADMIN, _kpi_interfon_pushes_semana),
    KPI("site-integraciones-rojo", "Integraciones en rojo", "Plataformas externas fallando en El Site.",
        "infraestructura", ("super_admin", "dueno"), _kpi_site_integraciones_rojo),

    # Dinero (parcial — completo en S2b.3)
    KPI("ingresos-mes", "Ingresos del mes (estimado)", "Suma de cobros del mes. Completo en La Tesorería.",
        "dinero", ROLES_ADMIN_CONTADOR, _kpi_ingresos_mes, estado_kpi="pendiente_tesoreria"),
    KPI("cxc-total", "Cuentas por cobrar (estimado)", "Facturado - cobrado en proyectos no-terminales. Completo en La Tesorería.",
        "dinero", ROLES_ADMIN_CONTADOR, _kpi_cxc_total, estado_kpi="pendiente_tesoreria"),
]


CATEGORIAS = (
    ("operacion", "🏗 Operación"),
    ("tareas", "✅ Tareas"),
    ("buzon", "📨 Buzón"),
    ("recados", "💬 Recados"),
    ("cartera", "👥 Cartera"),
    ("infraestructura", "📡 Infraestructura"),
    ("dinero", "💰 Dinero (S2b.3)"),
)


def kpis_aplicables_a_rol(rol: str) -> list[KPI]:
    """Filtra el catálogo por rol del usuario."""
    return [k for k in KPIS if rol in k.roles_visible]


def kpis_visibles_para(user, *, incluir_ocultos: bool = False) -> list[tuple[KPI, dict]]:
    """Retorna lista de (KPI, resultado_dict) respetando preferencias del usuario.

    Si `incluir_ocultos=True` (página de edición), devuelve TODOS los aplicables
    al rol, sin calcular los ocultos. Si False (dashboard), devuelve sólo los
    visibles y ya calculados.
    """
    from .models.preferencia_kpi import PreferenciaKPI
    rol = getattr(user, "rol", None) or "disenador"
    aplicables = kpis_aplicables_a_rol(rol)
    ocultos: set[str] = set(
        PreferenciaKPI.objects.filter(usuario=user, visible=False).values_list("kpi_slug", flat=True)
    )

    salida: list[tuple[KPI, dict]] = []
    for kpi in aplicables:
        if kpi.slug in ocultos:
            if incluir_ocultos:
                salida.append((kpi, {"valor": "—", "nota": "oculto", "link": ""}))
            continue
        try:
            resultado = kpi.calcular(user)
        except Exception:  # noqa: BLE001 — un KPI roto no debe tumbar el dashboard
            resultado = {"valor": "?", "nota": "error", "link": ""}
        salida.append((kpi, resultado))
    return salida


def kpi_por_slug(slug: str) -> KPI | None:
    return next((k for k in KPIS if k.slug == slug), None)
