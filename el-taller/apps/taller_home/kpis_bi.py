"""Los indicadores que faltaban: todo el negocio y la máquina.

Oscar, 2026-08-22: «incluye tickets, financieros, productos, proveedores,
clientes, hardware del NUC, IA, etc. TODO».

Estos KPIs no recalculan nada por su cuenta: se apoyan en los módulos que ya
hacen el trabajo —el embudo de ventas, la rentabilidad real, los hechos de
negocio, las estadísticas de IA y los medidores del NUC—, así que un número aquí
y el mismo número en El Análisis siempre coinciden.

El catálogo crece mucho a propósito, pero **el tablero no**: nadie va a ver
cuarenta indicadores. El Chalán elige cada día los pocos que importan (ver
`curaduria.py`); esto es el almacén del que escoge.

Todos son defensivos: si la fuente falla, el indicador devuelve 0 con una nota
en vez de tumbar el tablero.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def _seguro(fn, *, defecto=0, nota_error="sin datos"):
    """Corre el cálculo; si truena, devuelve el defecto con una nota honesta."""
    try:
        return fn()
    except Exception:  # noqa: BLE001
        logger.warning("KPI falló", exc_info=True)
        return {"valor": defecto, "nota": nota_error}


# ── Tickets (El Buzón) ───────────────────────────────────────────────────

def _kpi_buzon_urgentes(user) -> dict:
    def calc():
        from buzon.models import MensajeBuzon

        n = MensajeBuzon.objects.filter(prioridad__gte=8).exclude(
            estado__in=("respondido", "archivado", "cerrado"),
        ).count()
        return {"valor": n, "nota": "alerta" if n else "", "link": "/buzon/"}
    return _seguro(calc)


def _kpi_buzon_tiempo_respuesta(user) -> dict:
    """Cuántos días tarda en promedio una respuesta (últimos 30 días)."""
    def calc():
        from buzon.models import MensajeBuzon

        desde = date.today() - timedelta(days=30)
        atendidos = MensajeBuzon.objects.filter(
            creado_en__date__gte=desde, respondido_en__isnull=False,
        ).values_list("creado_en", "respondido_en")
        dias = [
            (r - c).total_seconds() / 86400 for c, r in atendidos if r and c
        ]
        if not dias:
            return {"valor": 0, "nota": "sin respuestas registradas", "link": "/buzon/"}
        prom = sum(dias) / len(dias)
        return {"valor": round(prom, 1), "nota": f"{len(dias)} atendidos", "link": "/buzon/"}
    return _seguro(calc)


# ── Ventas (el embudo real) ──────────────────────────────────────────────

def _embudo():
    from apps.cotizaciones.embudo import embudo
    return embudo()


def _kpi_conversion(user) -> dict:
    def calc():
        e = _embudo()
        return {"valor": e["conversion_pct"],
                "nota": f"{e['ganadas']} ganadas de {e['ganadas'] + e['perdidas']} resueltas",
                "link": "/cotizaciones/"}
    return _seguro(calc)


def _kpi_oportunidades_vivas(user) -> dict:
    def calc():
        e = _embudo()
        return {"valor": e["vivas"], "nota": f"${e['monto_vivo']:,.0f} en juego",
                "link": "/cotizaciones/"}
    return _seguro(calc)


def _kpi_cotizaciones_sin_enviar(user) -> dict:
    def calc():
        e = _embudo()
        n = len(e["sin_enviar"])
        return {"valor": n, "nota": "alerta" if n else "", "link": "/cotizaciones/"}
    return _seguro(calc)


def _kpi_cotizaciones_enfriadas(user) -> dict:
    def calc():
        e = _embudo()
        n = len(e["enfriadas"])
        return {"valor": n,
                "nota": f"más de {e['dias_silencio']} días sin respuesta" if n else "",
                "link": "/cotizaciones/"}
    return _seguro(calc)


# ── Rentabilidad real ────────────────────────────────────────────────────

def _resumen_rent():
    from apps.los_proyectos import rentabilidad as rent
    return rent.resumen()


def _kpi_margen_real(user) -> dict:
    def calc():
        r = _resumen_rent()
        return {"valor": r["margen_pct"],
                "nota": f"sano: {r['margen_sano_pct']:.0f}%", "link": "/analisis/#rentabilidad"}
    return _seguro(calc)


def _kpi_proyectos_en_perdida(user) -> dict:
    def calc():
        r = _resumen_rent()
        return {"valor": r["n_en_perdida"], "nota": "alerta" if r["n_en_perdida"] else "",
                "link": "/analisis/#rentabilidad"}
    return _seguro(calc)


def _kpi_proyectos_bajo_margen(user) -> dict:
    def calc():
        r = _resumen_rent()
        return {"valor": r["n_bajo_umbral"], "link": "/analisis/#rentabilidad"}
    return _seguro(calc)


def _kpi_dias_de_caja(user) -> dict:
    """Cuántos días aguanta el dinero disponible al ritmo de gasto actual."""
    def calc():
        from apps.contaduria import services as conta
        from apps.tesoreria.models import Egreso

        k = conta.kpis_landing()
        disponible = float(k.get("saldo_caja", 0)) + float(k.get("saldo_banco", 0))
        desde = date.today() - timedelta(days=90)
        egresos = Egreso.vigentes.filter(fecha__gte=desde)
        total = sum(float(e.monto or 0) for e in egresos)
        diario = total / 90 if total else 0
        if diario <= 0:
            return {"valor": 0, "nota": "sin gasto registrado", "link": "/tesoreria/"}
        return {"valor": round(disponible / diario, 1),
                "nota": f"gastas ~${diario:,.0f}/día", "link": "/tesoreria/"}
    return _seguro(calc)


def _kpi_cfdi_sin_emitir(user) -> dict:
    def calc():
        from apps.facturacion import services as fac

        n = fac.kpis_landing().get("cfdi_sin_emitir", 0)
        return {"valor": n,
                "nota": "sin cuenta por cobrar ni cobranza" if n else "",
                "link": "/facturacion/"}
    return _seguro(calc)


# ── Productos ────────────────────────────────────────────────────────────

def _kpi_productos_sin_costo(user) -> dict:
    def calc():
        from apps.el_catalogo.models import Servicio

        n = Servicio.objects.filter(activo=True).filter(costo__isnull=True).count()
        n += Servicio.objects.filter(activo=True, costo=0).count()
        return {"valor": n, "nota": "no se les puede medir margen" if n else "",
                "link": "/catalogo/"}
    return _seguro(calc)


def _kpi_margen_catalogo(user) -> dict:
    def calc():
        from apps.el_catalogo.models import Servicio

        margenes = [
            s.margen_porcentaje for s in Servicio.objects.filter(activo=True)
            if s.margen_porcentaje is not None
        ]
        if not margenes:
            return {"valor": 0, "nota": "sin costos capturados", "link": "/catalogo/"}
        prom = sum(float(m) for m in margenes) / len(margenes)
        return {"valor": round(prom, 1), "nota": f"{len(margenes)} productos",
                "link": "/catalogo/"}
    return _seguro(calc)


def _kpi_productos_usados_mes(user) -> dict:
    def calc():
        from apps.los_proyectos.models import ProyectoProducto

        desde = date.today().replace(day=1)
        n = ProyectoProducto.objects.filter(
            creado_en__date__gte=desde,
        ).values("servicio").distinct().count()
        return {"valor": n, "link": "/catalogo/"}
    return _seguro(calc)


# ── Proveedores ──────────────────────────────────────────────────────────

def _kpi_deuda_proveedores(user) -> dict:
    def calc():
        from apps.tesoreria.models import Egreso
        from django.db.models import Sum

        total = Egreso.vigentes.exclude(estado_pago="pagado").aggregate(
            t=Sum("monto"),
        )["t"] or 0
        return {"valor": round(float(total), 2), "link": "/tesoreria/por-pagar/"}
    return _seguro(calc)


def _kpi_egresos_sin_proveedor(user) -> dict:
    def calc():
        desde = date.today() - timedelta(days=90)
        from apps.tesoreria.models import Egreso

        n = Egreso.vigentes.filter(fecha__gte=desde, proveedor__isnull=True).count()
        return {"valor": n, "nota": "no se sabe a quién se le compró" if n else "",
                "link": "/tesoreria/egresos/"}
    return _seguro(calc)


def _kpi_proveedores_activos(user) -> dict:
    def calc():
        desde = date.today() - timedelta(days=90)
        from apps.tesoreria.models import Egreso

        n = Egreso.vigentes.filter(
            fecha__gte=desde, proveedor__isnull=False,
        ).values("proveedor").distinct().count()
        return {"valor": n, "nota": "últimos 90 días", "link": "/catalogo/proveedores/"}
    return _seguro(calc)


# ── Clientes ─────────────────────────────────────────────────────────────

def _kpi_ticket_promedio(user) -> dict:
    def calc():
        from apps.tesoreria.models import Ingreso
        from django.db.models import Avg

        desde = date.today() - timedelta(days=365)
        prom = Ingreso.vigentes.filter(fecha__gte=desde).aggregate(
            p=Avg("monto"),
        )["p"] or 0
        return {"valor": round(float(prom), 2), "nota": "por cobro, 12 meses",
                "link": "/tesoreria/ingresos/"}
    return _seguro(calc)


def _kpi_clientes_dormidos(user) -> dict:
    def calc():
        from apps.la_cartera.models import Cliente

        hace_un_ano = date.today() - timedelta(days=365)
        n = (
            Cliente.objects.filter(proyectos__isnull=False)
            .exclude(proyectos__creado_en__date__gte=hace_un_ano)
            .distinct().count()
        )
        return {"valor": n, "nota": "sin proyectos nuevos en un año" if n else "",
                "link": "/cartera/"}
    return _seguro(calc)


def _kpi_concentracion_cliente(user) -> dict:
    """Qué tanto del ingreso depende de un solo cliente. Arriba de 40% es riesgo."""
    def calc():
        from apps.tesoreria.models import Ingreso
        from django.db.models import Sum

        desde = date.today() - timedelta(days=365)
        por_cliente = (
            Ingreso.vigentes.filter(fecha__gte=desde, cliente__isnull=False)
            .values("cliente__razon_social")
            .annotate(t=Sum("monto")).order_by("-t")
        )
        filas = list(por_cliente)
        if not filas:
            return {"valor": 0, "nota": "sin ingresos con cliente", "link": "/cartera/"}
        total = sum(float(f["t"] or 0) for f in filas)
        mayor = float(filas[0]["t"] or 0)
        pct = (mayor / total * 100) if total else 0
        return {"valor": round(pct, 1),
                "nota": f"{filas[0]['cliente__razon_social']}", "link": "/cartera/"}
    return _seguro(calc)


# ── Runners y mandados ───────────────────────────────────────────────────

def _kpi_mandados_abiertos(user) -> dict:
    def calc():
        from apps.el_pizarron.models import Mandado

        n = Mandado.objects.exclude(estado__in=("entregado", "cancelado")).count()
        return {"valor": n, "link": "/mandados/"}
    return _seguro(calc)


def _kpi_mandados_sin_runner(user) -> dict:
    def calc():
        from apps.el_pizarron.models import Mandado

        n = Mandado.objects.filter(estado="por_asignar").count()
        return {"valor": n, "nota": "sin repartidor asignado" if n else "",
                "link": "/mandados/"}
    return _seguro(calc)


def _kpi_mandados_entregados_semana(user) -> dict:
    def calc():
        from apps.el_pizarron.models import Mandado

        desde = date.today() - timedelta(days=7)
        n = Mandado.objects.filter(
            estado="entregado", actualizado_en__date__gte=desde,
        ).count()
        return {"valor": n, "link": "/mandados/"}
    return _seguro(calc)


def _kpi_mandado_minutos(user) -> dict:
    """Cuánto tarda en promedio una misión, de la salida a la entrega."""
    def calc():
        from apps.el_pizarron.models import Mandado

        desde = date.today() - timedelta(days=30)
        cerrados = Mandado.objects.filter(
            estado="entregado", entregado_en__date__gte=desde,
            en_camino_en__isnull=False,
        )
        minutos = [m.minutos_en_ruta for m in cerrados if m.minutos_en_ruta is not None]
        if not minutos:
            return {"valor": 0, "nota": "aún sin misiones medidas", "link": "/mandados/"}
        return {"valor": round(sum(minutos) / len(minutos)),
                "nota": f"{len(minutos)} misiones, 30 días", "link": "/mandados/"}
    return _seguro(calc)


def _kpi_mandado_km(user) -> dict:
    """Kilómetros recorridos en repartos (línea recta entre salida y entrega)."""
    def calc():
        from apps.el_pizarron.models import Mandado
        from django.db.models import Sum

        desde = date.today() - timedelta(days=30)
        metros = Mandado.objects.filter(
            estado="entregado", entregado_en__date__gte=desde,
        ).aggregate(t=Sum("distancia_m"))["t"] or 0
        return {"valor": round(metros / 1000, 1), "nota": "últimos 30 días",
                "link": "/mandados/"}
    return _seguro(calc)


# ── La máquina (el NUC) ──────────────────────────────────────────────────

def _gauges():
    from lib.site.gauges import snapshot_gauges_minimo
    return snapshot_gauges_minimo() or {}


def _kpi_nuc_cpu(user) -> dict:
    def calc():
        g = _gauges()
        return {"valor": round(float(g.get("cpu") or 0), 1), "nota": "% de uso",
                "link": "/site/"}
    return _seguro(calc)


def _kpi_nuc_memoria(user) -> dict:
    def calc():
        g = _gauges()
        return {"valor": round(float(g.get("memoria") or 0), 1), "nota": "% ocupada",
                "link": "/site/"}
    return _seguro(calc)


def _kpi_nuc_disco(user) -> dict:
    def calc():
        g = _gauges()
        return {"valor": round(float(g.get("disco") or 0), 1), "nota": "% ocupado",
                "link": "/site/"}
    return _seguro(calc)


def _kpi_nuc_contenedores(user) -> dict:
    def calc():
        from lib.site import contenedores

        piezas = contenedores.estadisticas() or []
        corriendo = sum(1 for c in piezas if (c.get("estado") or "").startswith("run"))
        return {"valor": corriendo, "nota": f"de {len(piezas)}", "link": "/site/"}
    return _seguro(calc)


# ── Los Chalanes (IA) ────────────────────────────────────────────────────

def _kpi_ia_gasto(user) -> dict:
    def calc():
        from lib.analistas.stats import resumen_global

        r = resumen_global(dias=30)
        return {"valor": round(float(r.get("costo_total") or 0), 2),
                "nota": "USD, últimos 30 días", "link": "/perfil/chalanes/"}
    return _seguro(calc)


def _kpi_ia_llamadas(user) -> dict:
    def calc():
        from lib.analistas.stats import resumen_global

        r = resumen_global(dias=30)
        return {"valor": int(r.get("llamadas_total") or 0), "nota": "últimos 30 días",
                "link": "/perfil/chalanes/"}
    return _seguro(calc)


def _kpi_ia_fallos(user) -> dict:
    """Qué tan seguido el Chalán no entiende lo que se le dicta."""
    def calc():
        from apps.el_dictado.models import Dictado

        desde = date.today() - timedelta(days=30)
        total = Dictado.objects.filter(creado_en__date__gte=desde).count()
        if not total:
            return {"valor": 0, "nota": "sin dictados", "link": "/chalan/"}
        malos = Dictado.objects.filter(
            creado_en__date__gte=desde,
            estado__in=("fallo_ia", "aplicado_con_errores"),
        ).count()
        return {"valor": round(malos / total * 100, 1),
                "nota": f"{malos} de {total} dictados", "link": "/chalan/"}
    return _seguro(calc)


# ── La gente: accesos, jornadas y actividad ──────────────────────────────
#
# Oscar, 2026-08-22: «crúzalo con la actividad de cada usuario, tiempos de
# login, chequeos, jornadas trabajadas, horas — TODO».
#
# Ojo con la privacidad: estos indicadores son AGREGADOS (cuántos, cuántas
# horas en total, cuántos retardos). El detalle por persona vive en El Análisis
# y respeta la regla de siempre: las horas de alguien las ve esa persona, su
# jefe directo o el super admin.

def _kpi_accesos_hoy(user) -> dict:
    def calc():
        from cuentas.models.intento_acceso import IntentoAcceso

        hoy = date.today()
        ok = IntentoAcceso.objects.filter(creado_en__date=hoy, exito=True).count()
        return {"valor": ok, "nota": "entradas al sistema hoy", "link": "/directorio/"}
    return _seguro(calc)


def _kpi_accesos_fallidos(user) -> dict:
    """Intentos rechazados. Un salto aquí puede ser alguien probando contraseñas."""
    def calc():
        from cuentas.models.intento_acceso import IntentoAcceso

        desde = date.today() - timedelta(days=7)
        n = IntentoAcceso.objects.filter(creado_en__date__gte=desde, exito=False).count()
        return {"valor": n, "nota": "últimos 7 días", "link": "/directorio/"}
    return _seguro(calc)


def _kpi_usuarios_activos_semana(user) -> dict:
    """Cuánta gente de verdad usa el sistema."""
    def calc():
        from cuentas.models.usuario import Usuario

        desde = date.today() - timedelta(days=7)
        activos = Usuario.objects.filter(
            is_active=True, ultimo_acceso_en__date__gte=desde,
        ).count()
        total = Usuario.objects.filter(is_active=True).count()
        return {"valor": activos, "nota": f"de {total} cuentas", "link": "/directorio/"}
    return _seguro(calc)


def _kpi_cuentas_sin_entrar(user) -> dict:
    """Cuentas activas que llevan un mes sin entrar."""
    def calc():
        from django.db.models import Q

        from cuentas.models.usuario import Usuario

        corte = date.today() - timedelta(days=30)
        n = Usuario.objects.filter(is_active=True).filter(
            Q(ultimo_acceso_en__isnull=True) | Q(ultimo_acceso_en__date__lt=corte),
        ).count()
        return {"valor": n, "nota": "sin entrar en 30 días" if n else "",
                "link": "/directorio/"}
    return _seguro(calc)


def _kpi_horas_equipo_semana(user) -> dict:
    """Horas trabajadas por todo el equipo en los últimos 7 días."""
    def calc():
        from apps.checador.models import Jornada

        desde = date.today() - timedelta(days=7)
        total = 0.0
        dias = 0
        for j in Jornada.objects.filter(fecha__gte=desde):
            h = j.horas_trabajadas
            if h:
                total += h
                dias += 1
        return {"valor": round(total, 1), "nota": f"{dias} jornadas", "link": "/checador/equipo/"}
    return _seguro(calc)


def _kpi_retardos_mes(user) -> dict:
    def calc():
        from apps.checador.models import Jornada

        desde = date.today().replace(day=1)
        n = Jornada.objects.filter(fecha__gte=desde, retardo_min__gt=0).count()
        return {"valor": n, "nota": "llegadas tarde este mes", "link": "/checador/equipo/"}
    return _seguro(calc)


def _kpi_jornadas_sin_cerrar(user) -> dict:
    """Entradas sin salida de días pasados: alguien olvidó checar."""
    def calc():
        from apps.checador.models import Jornada

        n = Jornada.objects.filter(
            estado="abierta", fecha__lt=date.today(),
        ).count()
        return {"valor": n, "nota": "sin checar salida" if n else "",
                "link": "/checador/equipo/"}
    return _seguro(calc)


def _kpi_visitas_semana(user) -> dict:
    def calc():
        from apps.checador.models import Visita

        desde = date.today() - timedelta(days=7)
        n = Visita.objects.filter(registrado_en__date__gte=desde).count()
        return {"valor": n, "nota": "visitas a clientes y proveedores",
                "link": "/checador/"}
    return _seguro(calc)


def _kpi_horas_imputadas_pct(user) -> dict:
    """De las horas trabajadas, cuántas se pueden atribuir a un proyecto.

    Es la medida de qué tan confiable es el costo de mano de obra: si nadie usa
    el cronómetro ni registra actividad, el margen con mano de obra es una
    estimación gruesa y conviene saberlo.
    """
    def calc():
        from apps.checador.models import Jornada
        from apps.los_proyectos.mano_obra import horas_por_proyecto

        hoy = date.today()
        desde = hoy - timedelta(days=30)
        trabajadas = sum(
            (j.horas_trabajadas or 0) for j in Jornada.objects.filter(fecha__gte=desde)
        )
        if not trabajadas:
            return {"valor": 0, "nota": "sin jornadas registradas", "link": "/analisis/"}
        imputadas = sum(d["horas"] for d in horas_por_proyecto(desde, hoy).values())
        pct = min(100.0, imputadas / trabajadas * 100)
        return {"valor": round(pct, 1),
                "nota": f"{imputadas:.0f} h de {trabajadas:.0f} h", "link": "/analisis/"}
    return _seguro(calc)


def _kpi_actividad_registrada_semana(user) -> dict:
    """Movimientos registrados en proyectos: el pulso del trabajo."""
    def calc():
        from apps.los_proyectos.models import ActividadProyecto

        desde = date.today() - timedelta(days=7)
        n = ActividadProyecto.objects.filter(creado_en__date__gte=desde).count()
        return {"valor": n, "nota": "movimientos en proyectos", "link": "/proyectos/kanban/"}
    return _seguro(calc)


# ── Registro ─────────────────────────────────────────────────────────────
# (slug, título, descripción, categoría, roles, función)

def catalogo_bi(ROLES_TODOS, ROLES_ADMIN, ROLES_ADMIN_CONTADOR) -> list[tuple]:
    """Las tuplas para construir los KPI del catálogo principal.

    Se pasan los roles como argumento para no importar `kpis.py` desde aquí y
    evitar el import circular (es `kpis.py` quien llama a esta función).
    """
    return [
        # Tickets — El Buzón
        ("buzon-urgentes", "Tickets urgentes abiertos",
         "Mensajes con prioridad alta que nadie ha respondido.",
         "buzon", ROLES_TODOS, _kpi_buzon_urgentes),
        ("buzon-tiempo-respuesta", "Días en responder un ticket",
         "Cuánto tarda en promedio una respuesta del equipo (30 días).",
         "buzon", ROLES_ADMIN, _kpi_buzon_tiempo_respuesta),

        # Ventas
        ("conversion-oportunidades", "Conversión de cotizaciones",
         "De lo que ya se resolvió, cuánto se ganó. Cuenta oportunidades, no documentos.",
         "operacion", ROLES_ADMIN_CONTADOR, _kpi_conversion),
        ("oportunidades-vivas", "Oportunidades vivas",
         "Cotizaciones que todavía pueden convertirse en venta.",
         "operacion", ROLES_ADMIN_CONTADOR, _kpi_oportunidades_vivas),
        ("cotizaciones-sin-enviar", "Cotizaciones sin mandar",
         "Trabajo hecho que nunca salió al cliente.",
         "operacion", ROLES_ADMIN_CONTADOR, _kpi_cotizaciones_sin_enviar),
        ("cotizaciones-enfriadas", "Cotizaciones enfriadas",
         "Enviadas que llevan demasiado sin respuesta.",
         "operacion", ROLES_ADMIN_CONTADOR, _kpi_cotizaciones_enfriadas),

        # Dinero de verdad
        ("margen-real", "Margen real del despacho",
         "Lo vendido contra lo que de verdad costó producirlo.",
         "dinero", ROLES_ADMIN_CONTADOR, _kpi_margen_real),
        ("proyectos-en-perdida", "Proyectos en pérdida",
         "Trabajos que cuestan más de lo que dejan.",
         "dinero", ROLES_ADMIN_CONTADOR, _kpi_proyectos_en_perdida),
        ("proyectos-bajo-margen", "Proyectos bajo el margen sano",
         "Debajo del porcentaje que configuraste como aceptable.",
         "dinero", ROLES_ADMIN_CONTADOR, _kpi_proyectos_bajo_margen),
        ("dias-de-caja", "Días de caja",
         "Cuánto aguanta el dinero disponible al ritmo de gasto de los últimos meses.",
         "dinero", ROLES_ADMIN_CONTADOR, _kpi_dias_de_caja),
        ("facturas-cfdi-sin-emitir", "CFDI subidos sin emitir",
         "Facturas con su CFDI que siguen en borrador: no generan cuenta por cobrar.",
         "dinero", ROLES_ADMIN_CONTADOR, _kpi_cfdi_sin_emitir),

        # Productos
        ("productos-sin-costo", "Productos sin costo capturado",
         "Sin costo no se puede saber cuánto dejan.",
         "catalogo", ROLES_ADMIN_CONTADOR, _kpi_productos_sin_costo),
        ("margen-catalogo", "Margen promedio del catálogo",
         "Margen de lista de los productos activos.",
         "catalogo", ROLES_ADMIN_CONTADOR, _kpi_margen_catalogo),
        ("productos-usados-mes", "Productos distintos usados (mes)",
         "Qué tanto del catálogo se está moviendo.",
         "catalogo", ROLES_ADMIN, _kpi_productos_usados_mes),

        # Proveedores
        ("deuda-proveedores", "Deuda con proveedores",
         "Todo lo que se debe y aún no se paga.",
         "proveedores", ROLES_ADMIN_CONTADOR, _kpi_deuda_proveedores),
        ("egresos-sin-proveedor", "Gastos sin proveedor",
         "Egresos de los últimos 90 días que no dicen a quién se le compró.",
         "proveedores", ROLES_ADMIN_CONTADOR, _kpi_egresos_sin_proveedor),
        ("proveedores-activos", "Proveedores con movimiento",
         "A cuántos se les ha comprado en los últimos 90 días.",
         "proveedores", ROLES_ADMIN, _kpi_proveedores_activos),

        # Clientes
        ("ticket-promedio", "Ticket promedio",
         "Cuánto deja en promedio cada cobro (12 meses).",
         "cartera", ROLES_ADMIN_CONTADOR, _kpi_ticket_promedio),
        ("clientes-dormidos", "Clientes dormidos",
         "Compraron antes y no han vuelto en un año.",
         "cartera", ROLES_ADMIN, _kpi_clientes_dormidos),
        ("concentracion-cliente", "Dependencia del mayor cliente",
         "Qué porcentaje del ingreso viene de un solo cliente. Arriba de 40% es riesgo.",
         "cartera", ROLES_ADMIN, _kpi_concentracion_cliente),

        # Runners y mandados
        ("mandados-abiertos", "Mandados abiertos",
         "Entregas y recolecciones que siguen en la calle.",
         "runner", ROLES_TODOS, _kpi_mandados_abiertos),
        ("mandados-sin-runner", "Mandados sin repartidor",
         "Nadie los ha tomado todavía.",
         "runner", ROLES_ADMIN, _kpi_mandados_sin_runner),
        ("mandados-entregados-semana", "Mandados entregados (semana)",
         "Ritmo de entregas de los últimos 7 días.",
         "runner", ROLES_TODOS, _kpi_mandados_entregados_semana),
        ("mandado-minutos-promedio", "Minutos por misión",
         "De que el runner sale a que entrega. Se mide desde que checa salida.",
         "runner", ROLES_ADMIN, _kpi_mandado_minutos),
        ("mandado-km-mes", "Kilómetros recorridos",
         "Distancia de los repartos del mes, en línea recta entre salida y entrega.",
         "runner", ROLES_ADMIN, _kpi_mandado_km),

        # La máquina
        ("nuc-cpu", "CPU del servidor",
         "Qué tan cargado está el NUC ahora mismo.",
         "maquina", ROLES_ADMIN, _kpi_nuc_cpu),
        ("nuc-memoria", "Memoria ocupada",
         "Porcentaje de RAM en uso en el servidor.",
         "maquina", ROLES_ADMIN, _kpi_nuc_memoria),
        ("nuc-disco", "Disco ocupado",
         "Porcentaje del disco usado. Vigílalo antes de que llene.",
         "maquina", ROLES_ADMIN, _kpi_nuc_disco),
        ("nuc-contenedores", "Piezas corriendo",
         "Cuántos servicios del sistema están arriba.",
         "maquina", ROLES_ADMIN, _kpi_nuc_contenedores),

        # Los Chalanes
        ("ia-gasto-30d", "Gasto en IA (30 días)",
         "Lo que cuestan Los Chalanes al mes.",
         "ia", ROLES_ADMIN, _kpi_ia_gasto),
        ("ia-llamadas-30d", "Llamadas a los Chalanes (30 días)",
         "Cuánto se usa la IA.",
         "ia", ROLES_ADMIN, _kpi_ia_llamadas),
        ("ia-fallos-pct", "Dictados que fallan",
         "Porcentaje de instrucciones que el Chalán no logró aplicar.",
         "ia", ROLES_ADMIN, _kpi_ia_fallos),

        # La gente: accesos, jornadas y actividad
        ("accesos-hoy", "Entradas al sistema hoy",
         "Cuántas veces entró el equipo hoy.",
         "gente", ROLES_ADMIN, _kpi_accesos_hoy),
        ("accesos-fallidos", "Intentos de entrada rechazados",
         "Contraseñas equivocadas o cuentas sin permiso, últimos 7 días.",
         "gente", ROLES_ADMIN, _kpi_accesos_fallidos),
        ("usuarios-activos-semana", "Personas usando el sistema",
         "Cuántas cuentas entraron en los últimos 7 días.",
         "gente", ROLES_ADMIN, _kpi_usuarios_activos_semana),
        ("cuentas-sin-entrar", "Cuentas dormidas",
         "Activas pero sin entrar en un mes.",
         "gente", ROLES_ADMIN, _kpi_cuentas_sin_entrar),
        ("horas-equipo-semana", "Horas trabajadas del equipo",
         "Suma de las jornadas de los últimos 7 días.",
         "gente", ROLES_ADMIN, _kpi_horas_equipo_semana),
        ("retardos-mes", "Retardos del mes",
         "Llegadas tarde según el horario de cada quien.",
         "gente", ROLES_ADMIN, _kpi_retardos_mes),
        ("jornadas-sin-cerrar", "Jornadas sin checar salida",
         "Días pasados con entrada pero sin salida.",
         "gente", ROLES_ADMIN, _kpi_jornadas_sin_cerrar),
        ("visitas-semana", "Visitas registradas",
         "Salidas a clientes y proveedores de la semana.",
         "gente", ROLES_TODOS, _kpi_visitas_semana),
        ("horas-imputadas-pct", "Horas que se pueden costear",
         "De lo trabajado, cuánto se puede atribuir a un proyecto. Mide qué tan "
         "confiable es el costo de mano de obra.",
         "gente", ROLES_ADMIN, _kpi_horas_imputadas_pct),
        ("actividad-semana", "Movimientos en proyectos",
         "El pulso del trabajo: cuántas cosas se movieron esta semana.",
         "gente", ROLES_ADMIN, _kpi_actividad_registrada_semana),
    ]
