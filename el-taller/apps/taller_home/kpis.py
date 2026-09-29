"""Catálogo declarativo de KPIs para La Sala de Juntas (S2b.4).

Cada KPI es un dataclass `KPI` con:
- `slug`: identificador estable (también clave de `PreferenciaKPI.kpi_slug`)
- `titulo`, `descripcion`
- `categoria`: agrupa visualmente la lista de preferencias
- `permisos`: los permisos granulares que hacen falta para verlo —todos—
  (`permisos_kpi.py`: el permiso del DATO que enseña, nunca un nombre de rol)
- `origen`: 'manual' (catálogo) | 'sugerido_chalan' (S2b.2+) | 'custom_chalan' (S2b.5)
- `estado_kpi`: 'activo' (calcula) | 'pendiente_tesoreria' (placeholder S2b.3)
- `calcular(user) -> dict`: retorna `{valor, nota, link}`

Agregar un KPI = agregar una entrada a `KPIS`. Las preferencias del usuario
se persisten en `taller_home.PreferenciaKPI`; default opt-in (visible si no
hay fila explícita), opuesto al opt-out de `PreferenciaCategoriaPush` porque
para KPIs el comportamiento natural es "mostrar todo lo que puedo ver".

NOTA: Las consultas se ejecutan en cada render. Para 5 usuarios y ~30 KPIs
visibles el costo es bajo (~30 COUNT con índices). Si crece, agregar caché
con TTL=60s en `taller_home/cache.py` (sprint futuro).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .permisos_kpi import (
    ATIENDE_SOPORTE,
    CHECA,
    CONFIGURA_INTERFONO,
    EDITA_CARTERA,
    GESTIONA_PROYECTOS,
    VE_BUZON_PROPIO,
    VE_CARTERA,
    VE_CONTADURIA,
    VE_COTIZACIONES,
    VE_DINERO,
    VE_FACTURACION,
    VE_PROYECTOS,
    VE_RECADOS,
    VE_SITE,
    VE_TAREAS,
    VE_TODOS_PROYECTOS,
    VIGILA_CONTADURIA,
    puede_ver,
    puede_ver_con,
)

# ── Constantes auxiliares ──────────────────────────────────────────────────

ESTADOS_PROYECTO_ACTIVOS = ("en_proceso_diseno", "en_proceso_produccion")


@dataclass(frozen=True)
class KPI:
    slug: str
    titulo: str
    descripcion: str
    categoria: str
    permisos: tuple[str, ...]
    calcular: Callable[[Any], dict[str, Any]]
    origen: str = "manual"
    estado_kpi: str = "activo"
    # Cómo se juzga (ver `kpi_meta.py`). Los del catálogo original los toman de
    # `kpi_meta.metadatos_de()` al registrarse; los nuevos los declaran aquí.
    direccion: str = "sube"
    acumula: str = ""
    personal: bool = False
    acotado: bool = False
    formato: str = "numero"
    # El mismo número repartido: `desglose("persona")` → `{usuario_pk: n}`,
    # `desglose("cliente")` → `{cliente_pk: n}`. Es lo que permite ponerle
    # meta a una persona o a un cliente. `desgloses` dice cuáles sabe dar.
    desglose: Callable[[str], dict[int, float]] | None = None
    desgloses: tuple[str, ...] = ()

    def visible_para(self, user) -> bool:
        """¿`user` puede ver este KPI? (sus permisos; super_admin siempre)."""
        return puede_ver(user, self.permisos)

    def admite_meta(self, ambito: str) -> bool:
        """¿Se le puede poner meta de este ámbito (`despacho|persona|cliente`)?

        Una meta del despacho necesita un número del despacho (no «mis
        tareas»); una por persona, un KPI personal o que se reparta por
        persona; una por cliente, que se reparta por cliente."""
        if self.direccion == "neutro":
            return False
        if ambito == "despacho":
            return not self.personal
        if ambito == "persona":
            return self.personal or "persona" in self.desgloses
        if ambito == "cliente":
            return "cliente" in self.desgloses
        return False


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


def _es_solo_disenador(user) -> bool:
    """Restringe el queryset a "sus" proyectos a quien ve proyectos pero no
    todos (`proyectos.ver` sin `ver_todos`; antes, «diseñador sin rol amplio»)."""
    from lib.permisos import solo_proyectos_asignados
    return solo_proyectos_asignados(user)


# ── Cálculos por categoría ──────────────────────────────────────────────────


def _kpi_proyectos_activos(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    qs = Proyecto.objects.filter(estado__in=ESTADOS_PROYECTO_ACTIVOS)
    if _es_solo_disenador(user):  # V6 Bloque 10
        qs = qs.filter(asignaciones__usuario=user).distinct()
    return _resultado(qs.count(), link="/proyectos/?kpi=activos")


def _kpi_prospectos_pipeline(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    return _resultado(
        Proyecto.objects.filter(estado="por_cotizar").count(),
        link="/proyectos/?estado=por_cotizar",
    )


def _kpi_valor_proyectos(user) -> dict:
    """C4 S-LC-Feedback-V6: suma del valor estimado (derivado de productos)
    de los proyectos no terminales — refleja el pipeline en pesos."""
    from apps.los_proyectos.models import Proyecto
    from django.db.models import Sum
    qs = Proyecto.objects.exclude(estado__in=("entregado", "cancelado"))
    if _es_solo_disenador(user):  # V6 Bloque 10
        qs = qs.filter(asignaciones__usuario=user).distinct()
    total = qs.aggregate(s=Sum("monto_estimado"))["s"] or 0
    return _resultado(f"${total:,.0f}", link="/proyectos/")


def _kpi_cotizados_sin_avance(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    from django.utils import timezone
    limite = timezone.now() - timedelta(days=7)
    n = Proyecto.objects.filter(estado="esperando_respuesta", actualizado_en__lt=limite).count()
    return _resultado(n, nota=("alerta" if n > 0 else ""), link="/proyectos/?estado=esperando_respuesta")


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
        fecha_compromiso__date__gte=hoy,
        fecha_compromiso__date__lte=fin,
    )
    if _es_solo_disenador(user):  # V6 Bloque 10
        qs = qs.filter(asignaciones__usuario=user).distinct()
    return _resultado(qs.count())


def _kpi_proyectos_vencidos(user) -> dict:
    from apps.los_proyectos.models import Proyecto
    hoy = _hoy()
    qs = Proyecto.objects.filter(
        estado__in=ESTADOS_PROYECTO_ACTIVOS,
        fecha_compromiso__date__lt=hoy,
    )
    if _es_solo_disenador(user):  # V6 Bloque 10
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
    """Tareas atrasadas (derivado V6: compromiso vencido sin estado terminal).
    El estado `bloqueada` se eliminó — esto reemplaza su semántica."""
    from apps.el_pizarron.models import Tarea
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    n = Tarea.objects.filter(fecha_compromiso__lt=_hoy()).exclude(
        estado__in=slugs_terminales_tarea()
    ).count()
    return _resultado(n, nota=("alerta" if n > 0 else ""))


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
    # El campo de fecha de SiteChequeo es `probado_en`, NO `creado_en`: con el
    # nombre equivocado este KPI lanzaba FieldError cada vez que se calculaba.
    # Lo cazó el test que recorre todo el catálogo (2026-08-22).
    desde = _hoy() - timedelta(days=2)
    qs = SiteChequeo.objects.filter(
        estado="error", probado_en__date__gte=desde,
    ).values("plataforma").distinct()
    n = qs.count()
    return _resultado(n, nota=("alerta" if n > 0 else ""), link="/site/")


# ── Dinero (S2b.3 — leen de La Tesorería) ──


def _kpi_ingresos_mes(user) -> dict:
    from apps.tesoreria.models import Ingreso
    from django.db.models import Sum
    total = Ingreso.vigentes.filter(fecha__gte=_inicio_mes()).aggregate(
        s=Sum("monto"))["s"] or 0
    return _resultado(f"${total:,.0f}", link="/tesoreria/ingresos/")


def _kpi_egresos_mes(user) -> dict:
    from apps.tesoreria.models import Egreso
    from django.db.models import Sum
    total = Egreso.vigentes.filter(fecha__gte=_inicio_mes()).aggregate(
        s=Sum("monto"))["s"] or 0
    return _resultado(f"${total:,.0f}", link="/tesoreria/egresos/")


def _kpi_utilidad_mes(user) -> dict:
    from apps.tesoreria.models import Egreso, Ingreso
    from django.db.models import Sum
    desde = _inicio_mes()
    ingresos = Ingreso.vigentes.filter(fecha__gte=desde).aggregate(s=Sum("monto"))["s"] or 0
    egresos = Egreso.vigentes.filter(fecha__gte=desde).aggregate(s=Sum("monto"))["s"] or 0
    diff = ingresos - egresos
    return _resultado(f"${diff:,.0f}", nota=("alerta" if diff < 0 else ""), link="/tesoreria/reportes/")


def _kpi_cxc_total(user) -> dict:
    """CxC unificado: facturas + anticipos + proyectos legacy."""
    from apps.tesoreria.services import cxc_total_unificado
    total = cxc_total_unificado()
    return _resultado(f"${total:,.0f}", link="/tesoreria/por-cobrar/")


def _kpi_anticipos_pendientes(user) -> dict:
    """Cotizaciones aprobadas con anticipo > 0 sin factura del anticipo
    generada todavía."""
    from apps.cotizaciones.services import cotizaciones_con_anticipo_pendiente
    cots = cotizaciones_con_anticipo_pendiente()
    n = len(cots)
    return _resultado(n, nota=("alerta" if n > 0 else ""), link="/cotizaciones/?estado=aprobada")


def _kpi_cxp_total(user) -> dict:
    from apps.tesoreria.services import cuentas_por_pagar_qs
    from django.db.models import Sum
    total = cuentas_por_pagar_qs().aggregate(s=Sum("monto"))["s"] or 0
    return _resultado(f"${total:,.0f}", link="/tesoreria/por-pagar/")


def _kpi_reembolsos_pendientes(user) -> dict:
    from apps.tesoreria.models import Egreso
    from django.db.models import Sum
    qs = Egreso.vigentes.filter(estado_pago="por_reembolsar")
    n = qs.count()
    total = qs.aggregate(s=Sum("monto"))["s"] or 0
    return _resultado(
        f"${total:,.0f}",
        nota=f"{n} pendiente{'s' if n != 1 else ''}" if n else "",
        link="/tesoreria/por-pagar/",
    )


# ── Cotizaciones (S2b.cotizaciones-v1) ──

def _kpi_cotizaciones_pendientes(user) -> dict:
    from apps.cotizaciones.models import Cotizacion
    n = Cotizacion.objects.filter(estado="enviada").count()
    return _resultado(n, link="/cotizaciones/?estado=enviada")


def _kpi_cotizaciones_vencidas(user) -> dict:
    from datetime import date

    from apps.cotizaciones.models import Cotizacion
    n = Cotizacion.objects.filter(estado="enviada", fecha_validez__lt=date.today()).count()
    return _resultado(n, nota=("alerta" if n > 0 else ""), link="/cotizaciones/?estado=enviada")


def _kpi_cotizaciones_aprobadas_mes(user) -> dict:
    from datetime import date

    from apps.cotizaciones.models import Cotizacion
    hoy = date.today()
    n = Cotizacion.objects.filter(
        estado="aprobada",
        aprobada_en__year=hoy.year,
        aprobada_en__month=hoy.month,
    ).count()
    return _resultado(n, link="/cotizaciones/?estado=aprobada")


# ── Facturación (S2b.facturacion-v1) ──

def _kpi_facturas_pendientes_cobro(user) -> dict:
    from apps.facturacion.models import Factura
    n = Factura.objects.filter(estado__in=["emitida", "cobrada_parcial"]).count()
    return _resultado(n, link="/facturacion/?estado=emitida")


def _kpi_facturas_vencidas(user) -> dict:
    from datetime import date

    from apps.facturacion.models import Factura
    hoy = date.today()
    qs = Factura.objects.filter(
        estado__in=["emitida", "cobrada_parcial"], fecha_vencimiento__lt=hoy,
    )
    n = sum(1 for f in qs if f.saldo_pendiente > 0)
    return _resultado(n, nota=("alerta" if n > 0 else ""), link="/facturacion/?estado=emitida")


def _kpi_monto_por_cobrar(user) -> dict:
    from apps.facturacion.models import Factura
    qs = Factura.objects.filter(estado__in=["emitida", "cobrada_parcial"])
    total = sum((f.saldo_pendiente for f in qs), 0)
    return _resultado(f"${total:,.0f}", link="/facturacion/?estado=emitida")


def _kpi_facturado_mes(user) -> dict:
    from datetime import date

    from apps.facturacion.models import Factura
    hoy = date.today()
    qs = Factura.objects.exclude(estado="cancelada").filter(
        emitida_en__year=hoy.year, emitida_en__month=hoy.month,
    )
    total = sum((f.calcular_totales()["total"] for f in qs), 0)
    return _resultado(f"${total:,.0f}", link="/facturacion/")


# ── Contaduría (S3.contaduria-v1) ──

def _kpi_asientos_mes_contaduria(user) -> dict:
    from datetime import date

    from apps.contaduria.models import Asiento
    hoy = date.today()
    n = Asiento.vigentes.filter(fecha__year=hoy.year, fecha__month=hoy.month).count()
    return _resultado(n, link="/contaduria/asientos/")


def _kpi_saldo_banco(user) -> dict:
    from apps.contaduria.services import cuenta_por_slot, saldo_cuenta
    banco = cuenta_por_slot("banco")
    if not banco:
        return _resultado("—")
    s = saldo_cuenta(banco)
    return _resultado(f"${s:,.0f}", link=f"/contaduria/libro-mayor/{banco.pk}/")


def _kpi_utilidad_neta_mes_contaduria(user) -> dict:
    """Utilidad operativa del mes vía estado de resultados de Contaduría."""
    from datetime import date

    from apps.contaduria.reportes import estado_resultados
    hoy = date.today()
    pl = estado_resultados(desde=hoy.replace(day=1), hasta=hoy)
    nota = "alerta" if pl["utilidad_neta"] < 0 else ""
    return _resultado(f"${pl['utilidad_neta']:,.0f}", nota=nota, link="/contaduria/estado-resultados/")


def _kpi_balance_descuadrado(user) -> dict:
    """Cuenta de asientos del mes donde sum(cargos) != sum(abonos). Debe ser 0
    siempre (services valida partida doble). Si >0 algo inconsistente pasó."""
    from datetime import date

    from apps.contaduria.models import Asiento
    from django.db.models import Sum
    hoy = date.today()
    desc = 0
    qs = Asiento.vigentes.filter(fecha__year=hoy.year, fecha__month=hoy.month)
    for a in qs.only("id"):
        t = a.partidas.aggregate(c=Sum("cargo"), b=Sum("abono"))
        if (t["c"] or 0) != (t["b"] or 0):
            desc += 1
    return _resultado(desc, nota=("alerta" if desc > 0 else ""), link="/contaduria/asientos/")


# ── Checador (S-Checador E6) ──

def _kpi_checador_horas_semana(user) -> dict:
    from apps.checador import services
    agg = services.horas_de(user, _inicio_semana(), _hoy())
    return _resultado(agg["jornada_horas"], nota="horas esta semana", link="/checador/historial/")


def _kpi_checador_retardos_mes(user) -> dict:
    from apps.checador.models import Jornada
    n = Jornada.objects.filter(usuario=user, fecha__gte=_inicio_mes(), retardo_min__gt=0).count()
    return _resultado(n, nota=("retardos este mes" if n else "sin retardos"), link="/checador/historial/")


def _kpi_checador_visitas_semana(user) -> dict:
    from apps.checador.models import Visita
    n = Visita.objects.filter(usuario=user, registrado_en__date__gte=_inicio_semana()).count()
    return _resultado(n, nota="visitas esta semana", link="/checador/historial/")


def _kpi_checador_horas_proyecto_top(user) -> dict:
    from apps.checador.models import SesionProyecto
    from django.db.models import Sum
    row = (
        SesionProyecto.objects.filter(usuario=user, estado="cerrada", inicio__date__gte=_inicio_semana())
        .values("proyecto__codigo").annotate(t=Sum("duracion_min")).order_by("-t").first()
    )
    if not row or not row["t"]:
        return _resultado(0, nota="sin tiempo registrado", link="/checador/historial/")
    return _resultado(round(row["t"] / 60, 1), nota=f"{row['proyecto__codigo']} (top)", link="/checador/historial/")


# ── Catálogo ──

KPIS: list[KPI] = [
    # Operación
    KPI("proyectos-activos", "Proyectos activos", "Proyectos en diseño, revisión o producción.",
        "operacion", VE_PROYECTOS, _kpi_proyectos_activos),
    KPI("prospectos-pipeline", "Prospectos en pipeline", "Clientes potenciales con conversación abierta.",
        "operacion", VE_TODOS_PROYECTOS, _kpi_prospectos_pipeline),
    KPI("valor-proyectos", "Valor en proyectos", "Suma estimada (derivada de productos) de los proyectos no terminados.",
        "operacion", VE_DINERO, _kpi_valor_proyectos),
    KPI("cotizados-sin-avance", "Cotizados >7d sin avance", "Cotización enviada y sin movimiento. Velocidad comercial.",
        "operacion", VE_TODOS_PROYECTOS, _kpi_cotizados_sin_avance),
    KPI("proyectos-en-pausa", "Proyectos en pausa", "Pausados — insumos atrasados, cliente desaparecido.",
        "operacion", VE_TODOS_PROYECTOS, _kpi_proyectos_en_pausa),
    KPI("por-entregar-esta-semana", "Por entregar esta semana", "Proyectos con fecha de entrega en los próximos 7 días.",
        "operacion", VE_PROYECTOS, _kpi_por_entregar_esta_semana),
    KPI("proyectos-vencidos", "Proyectos vencidos", "Activos con fecha de entrega pasada.",
        "operacion", VE_PROYECTOS, _kpi_proyectos_vencidos),
    KPI("proyectos-sin-actividad", "Proyectos sin actividad (>14d)", "Activos sin actualizar en 2 semanas — riesgo de cliente perdido.",
        "operacion", VE_TODOS_PROYECTOS, _kpi_proyectos_sin_actividad),
    KPI("proyectos-cancelados-mes", "Cancelados este mes", "Señal de churn comercial.",
        "operacion", GESTIONA_PROYECTOS, _kpi_proyectos_cancelados_mes),

    # Tareas
    KPI("mis-tareas-vencidas", "Mis tareas vencidas", "Tareas tuyas con fecha de compromiso pasada.",
        "tareas", VE_TAREAS, _kpi_mis_tareas_vencidas),
    KPI("mis-tareas-proximas-3d", "Mis tareas (próximos 3 días)", "Tareas tuyas que vencen pronto.",
        "tareas", VE_TAREAS, _kpi_mis_tareas_proximas),
    KPI("tareas-vencidas-equipo", "Tareas vencidas del equipo", "Vista cross-equipo para admins.",
        "tareas", GESTIONA_PROYECTOS, _kpi_tareas_vencidas_equipo),
    # Slug preservado por compatibilidad con PreferenciaKPI; semántica V6 =
    # atrasadas (el estado `bloqueada` ya no existe).
    KPI("tareas-bloqueadas", "Tareas atrasadas", "Compromiso vencido sin cerrar.",
        "tareas", VE_TAREAS, _kpi_tareas_bloqueadas),
    KPI("tareas-sin-asignar", "Tareas sin asignar", "Tareas activas sin owner.",
        "tareas", GESTIONA_PROYECTOS, _kpi_tareas_sin_asignar),
    KPI("tareas-completadas-semana", "Completadas esta semana", "Throughput del equipo.",
        "tareas", GESTIONA_PROYECTOS, _kpi_tareas_completadas_semana),

    # Buzón
    KPI("buzon-sin-responder", "Buzón sin responder", "Mensajes de empleados en estado 'nuevo'.",
        "buzon", ATIENDE_SOPORTE, _kpi_buzon_sin_responder),
    KPI("buzon-bugs-abiertos", "Bugs abiertos", "Mensajes tipo 'problema' no archivados.",
        "buzon", ATIENDE_SOPORTE, _kpi_buzon_bugs_abiertos),
    KPI("buzon-sugerencias", "Sugerencias acumuladas", "Mensajes tipo 'sugerencia' en estado 'nuevo'.",
        "buzon", ATIENDE_SOPORTE, _kpi_buzon_sugerencias),
    KPI("buzon-mios-sin-responder", "Mis mensajes sin responder", "Mensajes que envié al Buzón y siguen abiertos.",
        "buzon", VE_BUZON_PROPIO, _kpi_buzon_mios_sin_responder),

    # Recados
    KPI("mis-recados-no-leidos", "Mis recados no leídos", "Mensajería interna sin leer.",
        "recados", VE_RECADOS, _kpi_mis_recados_no_leidos),
    KPI("recados-enviados-semana", "Recados que envié (semana)", "Mi nivel de actividad en mensajería.",
        "recados", VE_RECADOS, _kpi_recados_enviados_semana),

    # Cartera
    KPI("clientes-activos", "Clientes activos", "Cartera total sin soft-delete.",
        "cartera", VE_CARTERA, _kpi_clientes_activos),
    KPI("clientes-nuevos-mes", "Clientes nuevos del mes", "Crecimiento de cartera.",
        "cartera", VE_CARTERA, _kpi_clientes_nuevos_mes),
    KPI("clientes-sin-proyectos", "Clientes sin proyectos activos", "Oportunidad de cross-sell.",
        "cartera", EDITA_CARTERA, _kpi_clientes_sin_proyectos),
    KPI("clientes-con-pry-activos", "Clientes con proyectos vivos", "Cuántos clientes están comprándote ahora.",
        "cartera", VE_CARTERA, _kpi_clientes_con_pry_activos),

    # Infraestructura
    KPI("interfon-suscripciones", "Suscripciones del Interfón", "Dispositivos del equipo recibiendo push.",
        "infraestructura", CONFIGURA_INTERFONO, _kpi_interfon_suscripciones),
    KPI("interfon-pushes-semana", "Pushes enviados (semana)", "Volumen de notificaciones de la semana.",
        "infraestructura", CONFIGURA_INTERFONO, _kpi_interfon_pushes_semana),
    KPI("site-integraciones-rojo", "Integraciones en rojo", "Plataformas externas fallando en El Site.",
        "infraestructura", VE_SITE, _kpi_site_integraciones_rojo),

    # Dinero (S2b.3)
    KPI("ingresos-mes", "Ingresos del mes", "Cobros vigentes (no anulados) del mes en curso.",
        "dinero", VE_DINERO, _kpi_ingresos_mes),
    KPI("egresos-mes", "Egresos del mes", "Gastos vigentes del mes en curso.",
        "dinero", VE_DINERO, _kpi_egresos_mes),
    KPI("utilidad-mes", "Utilidad bruta del mes", "Ingresos menos egresos del mes.",
        "dinero", VE_DINERO, _kpi_utilidad_mes),
    KPI("cxc-total", "Cuentas por cobrar", "Saldos pendientes por cobrar (mientras Facturación llega, se calcula sobre proyectos).",
        "dinero", VE_DINERO, _kpi_cxc_total),
    KPI("cxp-total", "Cuentas por pagar", "Egresos pendientes o por reembolsar.",
        "dinero", VE_DINERO, _kpi_cxp_total),
    KPI("reembolsos-pendientes", "Reembolsos pendientes", "Dinero adelantado por empleados que el despacho debe.",
        "dinero", VE_DINERO, _kpi_reembolsos_pendientes),

    # Cotizaciones (S2b.cotizaciones-v1)
    KPI("cotizaciones-pendientes", "Cotizaciones pendientes", "Enviadas y esperando respuesta del cliente.",
        "operacion", VE_COTIZACIONES, _kpi_cotizaciones_pendientes),
    KPI("cotizaciones-vencidas", "Cotizaciones vencidas", "Enviadas con fecha de validez ya pasada.",
        "operacion", VE_COTIZACIONES, _kpi_cotizaciones_vencidas),
    KPI("cotizaciones-aprobadas-mes", "Cotizaciones aprobadas (mes)", "Conversiones del mes en curso.",
        "operacion", VE_COTIZACIONES, _kpi_cotizaciones_aprobadas_mes),
    KPI("anticipos-pendientes", "Anticipos pendientes de facturar",
        "Cotizaciones aprobadas con anticipo > 0 sin factura del anticipo generada.",
        "dinero", VE_FACTURACION, _kpi_anticipos_pendientes),

    # Facturación (S2b.facturacion-v1)
    KPI("facturas-pendientes-cobro", "Facturas pendientes de cobro",
        "Facturas emitidas (totalmente o parcialmente cobradas con saldo pendiente).",
        "dinero", VE_FACTURACION, _kpi_facturas_pendientes_cobro),
    KPI("facturas-vencidas", "Facturas vencidas",
        "Facturas con fecha de vencimiento pasada y saldo > 0.",
        "dinero", VE_FACTURACION, _kpi_facturas_vencidas),
    KPI("monto-por-cobrar", "Monto por cobrar",
        "Suma del saldo pendiente de todas las facturas emitidas o parciales.",
        "dinero", VE_FACTURACION, _kpi_monto_por_cobrar),
    KPI("facturado-mes", "Facturado del mes",
        "Suma del total de facturas emitidas en el mes en curso (no canceladas).",
        "dinero", VE_FACTURACION, _kpi_facturado_mes),

    # Contaduría (S3.contaduria-v1)
    KPI("contaduria-asientos-mes", "Asientos del mes", "Movimientos contables (vigentes) del mes en curso.",
        "dinero", VE_CONTADURIA, _kpi_asientos_mes_contaduria),
    KPI("contaduria-saldo-banco", "Saldo en bancos", "Saldo deudor actual de la cuenta de Bancos.",
        "dinero", VE_CONTADURIA, _kpi_saldo_banco),
    KPI("contaduria-balance-descuadrado", "Asientos descuadrados", "Asientos del mes con cargos ≠ abonos. Debe ser 0.",
        "dinero", VIGILA_CONTADURIA, _kpi_balance_descuadrado),

    # Contaduría (S3.contaduria-v2)
    KPI("contaduria-utilidad-neta-mes", "Utilidad neta del mes", "Resultado del periodo según el estado de resultados (sin ISR estimado).",
        "dinero", VE_CONTADURIA, _kpi_utilidad_neta_mes_contaduria),

    # Checador (S-Checador E6) — personales, todo el staff.
    KPI("checador-horas-semana", "Mis horas esta semana", "Horas de jornada (entrada→salida) acumuladas esta semana.",
        "checador", CHECA, _kpi_checador_horas_semana),
    KPI("checador-retardos-mes", "Mis retardos del mes", "Días con retardo este mes según tu horario.",
        "checador", CHECA, _kpi_checador_retardos_mes),
    KPI("checador-visitas-semana", "Mis visitas esta semana", "Visitas a clientes/proveedores registradas esta semana.",
        "checador", CHECA, _kpi_checador_visitas_semana),
    KPI("checador-horas-por-proyecto-top", "Proyecto con más horas", "Proyecto donde más tiempo registraste esta semana.",
        "checador", CHECA, _kpi_checador_horas_proyecto_top),
]


# Los indicadores del resto del negocio y de la máquina (2026-08-22, Oscar:
# «tickets, financieros, productos, proveedores, clientes, hardware del NUC, IA
# — TODO»). Viven en `kpis_bi.py` para no engordar este archivo, y se agregan
# aquí para que todo el sistema los vea igual que a los demás.
#
# Que el catálogo sea grande NO significa un tablero grande: El Chalán elige
# cada día los pocos que importan (`curaduria.py`). Antes de esto, la gente
# apagaba a mano los que le sobraban — 72 ocultamientos en la base.
from .kpis_bi import catalogo_bi  # noqa: E402

KPIS += [
    KPI(slug, titulo, descripcion, categoria, permisos, fn)
    for slug, titulo, descripcion, categoria, permisos, fn in catalogo_bi()
]

# Cómo se juzga cada KPI del catálogo original (dirección, periodo, formato).
from dataclasses import replace as _replace  # noqa: E402

from .kpi_meta import metadatos_de  # noqa: E402

KPIS = [_replace(k, **metadatos_de(k.slug)) for k in KPIS]

# Los de desempeño declaran sus propios metadatos: van después del `replace`.
from .kpis_desempeno import catalogo_desempeno  # noqa: E402

KPIS += catalogo_desempeno()


CATEGORIAS = (
    ("operacion", "🏗 Operación"),
    ("tareas", "✅ Tareas"),
    ("buzon", "📨 Buzón / Tickets"),
    ("recados", "💬 Recados"),
    ("cartera", "👥 Clientes"),
    ("catalogo", "📦 Productos"),
    ("proveedores", "🚚 Proveedores"),
    ("runner", "🛵 Mandados"),
    ("infraestructura", "📡 Infraestructura"),
    ("maquina", "🖥 El servidor"),
    ("ia", "🤖 Los Chalanes"),
    ("dinero", "💰 Dinero"),
    ("checador", "🕐 Checador"),
    ("gente", "🧑‍🔧 La gente"),
)


def _kpis_custom_para(user) -> list[KPI]:
    """KPIs generados por el Chalán (S2b.5) que aplican a `user`:
    - personales del autor (alcance='personal', estado='activo')
    - de equipo aprobados (alcance='equipo', estado='activo')
    """
    from lib.kpi_dsl import ejecutar

    from .models import KPICustom

    qs = KPICustom.objects.filter(estado="activo").filter(
        models_Q_personal_o_equipo(user)
    )
    salida: list[KPI] = []
    for kpi_db in qs.only(
        "slug", "titulo", "descripcion", "categoria", "definicion_json", "alcance", "autor_id",
    ):
        definicion = dict(kpi_db.definicion_json)  # copia local para no mutar

        def _calc(usuario, _def=definicion):
            return ejecutar(_def, usuario=usuario)

        salida.append(KPI(
            slug=f"custom-{kpi_db.slug}",
            titulo=kpi_db.titulo,
            descripcion=kpi_db.descripcion or "KPI personalizado.",
            categoria=kpi_db.categoria or "custom",
            # Los hizo El Chalán para su autor o se aprobaron para el equipo: no
            # llevan permiso propio (antes, «los cuatro roles», pero el catálogo
            # los agregaba a todos sin mirar la tupla).
            permisos=(),
            calcular=_calc,
            origen="custom_chalan",
            estado_kpi="activo",
        ))
    return salida


def _kpis_custom_equipo() -> list[KPI]:
    """Los KPIs del Chalán aprobados para el equipo: esos sí son números del
    despacho y entran a la foto diaria (los personales no)."""
    from lib.kpi_dsl import ejecutar

    from .models import KPICustom

    salida: list[KPI] = []
    for kpi_db in KPICustom.objects.filter(estado="activo", alcance="equipo").only(
        "slug", "titulo", "descripcion", "categoria", "definicion_json",
    ):
        definicion = dict(kpi_db.definicion_json)

        def _calc(usuario, _def=definicion):
            return ejecutar(_def, usuario=usuario)

        salida.append(KPI(
            slug=f"custom-{kpi_db.slug}", titulo=kpi_db.titulo,
            descripcion=kpi_db.descripcion or "KPI personalizado.",
            categoria=kpi_db.categoria or "custom", permisos=(), calcular=_calc,
            origen="custom_chalan",
        ))
    return salida


def models_Q_personal_o_equipo(user):
    """Q: (alcance='personal' AND autor=user) OR alcance='equipo'."""
    from django.db.models import Q
    return Q(alcance="equipo") | Q(alcance="personal", autor=user)


def kpis_aplicables(user) -> list[KPI]:
    """El catálogo que `user` puede ver —por sus permisos (§4 #20)— más sus
    KPIs del Chalán (S2b.5), sin los que La Gerencia apagó (S-KPIs-V2) y con
    la dirección que La Gerencia haya elegido."""
    from .tablero import apagados, configs, efectivo

    cfgs = configs()
    fuera = apagados(cfgs)
    return [
        efectivo(k, cfgs)
        for k in [*[k for k in KPIS if k.visible_para(user)], *_kpis_custom_para(user)]
        if k.slug not in fuera
    ]


def kpis_aplicables_a_rol(rol: str, *, user=None) -> list[KPI]:
    """Compatibilidad: con `user`, lo mismo que `kpis_aplicables(user)` (el
    rol ya no decide nada). Sólo con el nombre de un rol, lo que verían los
    DEFAULTS de ese rol (`lib.permisos_defaults`), sin KPIs del Chalán."""
    if user is not None:
        return kpis_aplicables(user)
    from lib.permisos_defaults import defaults_de

    mapa = defaults_de(rol or "")
    return [k for k in KPIS if puede_ver_con(mapa, k.permisos)]


def kpis_visibles_para(user, *, incluir_ocultos: bool = False) -> list[tuple[KPI, dict]]:
    """Retorna lista de (KPI, resultado_dict) respetando preferencias del usuario.

    Si `incluir_ocultos=True` (página de edición), devuelve TODOS los aplicables
    al usuario, sin calcular los ocultos. Si False (dashboard), devuelve sólo los
    visibles y ya calculados.
    """
    from .models.preferencia_kpi import PreferenciaKPI
    aplicables = kpis_aplicables(user)
    ocultos: set[str] = set(
        PreferenciaKPI.objects.filter(usuario=user, visible=False).values_list("kpi_slug", flat=True)
    )
    # S-LC-Feedback-V3: orden personalizado por usuario (campo `orden` en
    # PreferenciaKPI, persistido por drag&drop). Slugs sin preferencia
    # quedan al final en el orden del catálogo.
    ordenes = dict(
        PreferenciaKPI.objects.filter(usuario=user).values_list("kpi_slug", "orden")
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
    # Ordenar respetando preferencia (sin preferencia = orden default catálogo).
    # S-LC-Feedback-V4 hotfix: PreferenciaKPI puede tener orden=NULL en prod
    # (filas legacy creadas antes de que el campo tuviera default). `dict.get`
    # devuelve None en ese caso y rompe el sort con `'<' not supported between
    # NoneType`. Coalescemos a 9999 (mismo bucket que "sin preferencia").
    salida.sort(key=lambda pair: ordenes.get(pair[0].slug) if ordenes.get(pair[0].slug) is not None else 9999)
    return salida


def kpi_por_slug(slug: str) -> KPI | None:
    return next((k for k in KPIS if k.slug == slug), None)
