"""Resumen de pendientes del taller — herramienta del Dashboard (2026-07).

Pedido de Oscar: un reporte de **texto simple** (sin emojis, secciones
separadas por `<br>`, negritas SOLO en los títulos) con todo lo que está
pendiente a futuro, listo para leer de un vistazo o copiar y pegar.

**Es determinista** — se arma con queries, NO con IA. Un reporte operativo
debe ser exacto y gratis; el resumen narrativo con IA vive por proyecto en
`apps.los_proyectos.resumen_ia`.

Secciones (orden fijo, decisión Oscar):
  0. Encabezado .......... día de la semana, fecha y hora en que se generó
  1. URGENTES ............ tareas de prioridad alta + las que NO tienen fecha
  2..N. <PERSONA> ........ una sección por persona con pendientes asignados
  N+1. MISIONES .......... mandados (entregas/recolecciones) sin cerrar
  N+2. TIZAYUCA .......... un renglón POR PRODUCTO del proveedor de Tizayuca
  N+3. FACTURAS X EMITIR . proyectos confirmados sin factura ligada
  N+4. COTIZACIONES ...... proyectos en «por cotizar»
  N+5. FACTURAS X COBRAR . facturas emitidas con saldo pendiente

**Regla de fechas (Oscar, 2026-07-25): el reporte mira HACIA ADELANTE.** Solo
entra lo de hoy y lo que viene; lo que ya pasó de fecha NO se lista (aplica a
tareas, mandados y proyectos). Lo que no tiene fecha sí entra — y en el caso de
las tareas, se va a URGENTES para que no se pierda.

**Única excepción: FACTURAS X COBRAR.** Ahí salen todas las que tengan saldo,
vencidas incluidas, hasta que se marquen cobradas o se les ligue el cobro.

Cada sección respeta la visibilidad del usuario (mismos helpers que el
Kanban de Tareas y el de Proyectos) y los permisos granulares (§4 #20): si
no puedes ver Facturación, esas secciones simplemente no salen.
"""

from __future__ import annotations

from datetime import date, datetime

# Estados de proyecto que cuentan como "confirmado" para facturar: el cliente
# ya dijo que sí y el trabajo va en curso o terminó. `por_cotizar`/
# `esperando_respuesta` aún no son venta; `en_pausa`/`cancelado` no se facturan.
ESTADOS_CONFIRMADOS = ("en_proceso_diseno", "en_proceso_produccion", "entregado", "cerrado")

# Facturas que siguen "por cobrar" (emitidas, no canceladas, con saldo).
ESTADOS_FACTURA_POR_COBRAR = ("emitida", "cobrada_parcial")

# Nombres completos (Oscar 2026-07-25): «sábado 26 de julio», no «26 jul».
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

# Tope por sección para que el reporte siga siendo legible (y el modal, corto).
LIMITE_SECCION = 40


def _a_date(d):
    """Normaliza a `date`. Los `datetime` aware se pasan a hora local ANTES de
    leer el día: leerlos en UTC corre la fecha (el bug +6h de S-Chalan-Barrido)."""
    if isinstance(d, datetime):
        from django.utils import timezone
        return timezone.localtime(d).date() if timezone.is_aware(d) else d.date()
    return d


def _fecha(d) -> str:
    """`date`/`datetime` → «sábado 26 de julio» (+ « de 2027» si es otro año)."""
    if not d:
        return "sin fecha"
    d = _a_date(d)
    txt = f"{_DIAS[d.weekday()]} {d.day} de {_MESES[d.month - 1]}"
    return txt if d.year == date.today().year else f"{txt} de {d.year}"


def _vigente(d) -> bool:
    """Regla Oscar: solo hoy y lo que viene. Sin fecha también entra (no se
    pierde); lo que ya pasó, no."""
    if not d:
        return True
    return _a_date(d) >= date.today()


def encabezado_fecha() -> str:
    """Primera línea del reporte: día, fecha y hora en que se generó.

    La hora respeta la preferencia 24h/AM-PM del usuario (thread-local que fija
    el context processor `formato_hora`; fuera de un request cae a 24h).
    """
    from django.template.defaultfilters import date as _fmt
    from django.utils import timezone

    from lib.formato_hora import aplicar
    ahora = timezone.localtime()
    return (
        f"{_DIAS[ahora.weekday()]} {ahora.day} de {_MESES[ahora.month - 1]} "
        f"de {ahora.year} · {_fmt(ahora, aplicar('H:i'))}"
    )


def _cliente_de(proyecto) -> str:
    cli = getattr(proyecto, "cliente", None)
    return (getattr(cli, "razon_social", "") or "").strip() or "sin cliente"


def _nombre_proyecto(proyecto) -> str:
    """Decisión Oscar: SIEMPRE el nombre por delante; el código es respaldo."""
    if not proyecto:
        return "sin proyecto"
    return (getattr(proyecto, "nombre", "") or "").strip() or proyecto.codigo


def _linea_tarea(t) -> str:
    return f"{t.titulo} · {_cliente_de(t.proyecto)} · {_fecha(t.fecha_compromiso)}"


def _orden_tareas(tareas: list) -> list:
    """Fechas más cercanas hasta arriba; sin fecha al final; empata por orden
    de captura (como fueron agregadas al sistema)."""
    lejos = date(9999, 12, 31)
    return sorted(tareas, key=lambda t: (t.fecha_compromiso or lejos, t.pk))


# ── Secciones ────────────────────────────────────────────────────────────────

def _tareas_pendientes(user):
    """Tareas visibles que siguen abiertas: ni terminales ni archivadas, y con
    fecha de hoy en adelante (o sin fecha)."""
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    from apps.el_pizarron.views import _tareas_visibles
    from django.db.models import Q
    return (
        _tareas_visibles(user)
        .filter(archivada=False)
        .exclude(estado__in=slugs_terminales_tarea())
        .filter(Q(fecha_compromiso__isnull=True) | Q(fecha_compromiso__gte=date.today()))
    )


def _seccion_urgentes(tareas: list) -> dict:
    """Prioridad alta + TODO lo que no tiene fecha (Oscar: sin fecha = urgente,
    para que no se quede olvidado en el fondo de la lista)."""
    urgentes = [t for t in tareas if t.prioridad == "alta" or not t.fecha_compromiso]
    return {
        "titulo": "URGENTES",
        "lineas": [_linea_tarea(t) for t in _orden_tareas(urgentes)[:LIMITE_SECCION]],
    }


def _secciones_por_persona(tareas: list) -> list[dict]:
    """Una sección por persona con pendientes, encabezada con su nombre en
    mayúsculas (ALEX, JORGE…). Si dos personas comparten nombre de pila, se
    usa el nombre completo para no confundirlas."""
    por_usuario: dict[int, dict] = {}
    for t in tareas:
        for u in ([t.asignada_a] if t.asignada_a_id else []):
            por_usuario.setdefault(u.pk, {"usuario": u, "tareas": []})["tareas"].append(t)

    pilas: dict[str, int] = {}
    for datos in por_usuario.values():
        pila = datos["usuario"].get_short_name().strip().upper()
        pilas[pila] = pilas.get(pila, 0) + 1

    secciones = []
    for datos in sorted(por_usuario.values(), key=lambda d: d["usuario"].nombre_completo):
        u = datos["usuario"]
        pila = u.get_short_name().strip().upper()
        titulo = pila if pilas.get(pila, 0) == 1 else (u.nombre_completo or pila).upper()
        secciones.append({
            "titulo": titulo,
            "lineas": [_linea_tarea(t) for t in _orden_tareas(datos["tareas"])[:LIMITE_SECCION]],
        })
    return secciones


def _seccion_misiones(user) -> dict:
    from apps.el_pizarron.mandados import mandados_visibles
    from django.db.models import Q
    mandados = list(
        mandados_visibles(user)
        .exclude(estado__in=("entregado", "cancelado"))
        .filter(Q(tarea__fecha_compromiso__isnull=True)
                | Q(tarea__fecha_compromiso__gte=date.today()))[:LIMITE_SECCION * 2]
    )
    lejos = date(9999, 12, 31)
    mandados.sort(key=lambda m: (m.tarea.fecha_compromiso or lejos, m.pk))
    lineas = []
    for m in mandados[:LIMITE_SECCION]:
        runner = getattr(m.runner, "nombre_completo", "") or "sin runner"
        lineas.append(
            f"{m.titulo} · {_cliente_de(m.proyecto)} · {runner} · {_fecha(m.fecha_compromiso)}"
        )
    return {"titulo": "MISIONES", "lineas": lineas}


def _seccion_tizayuca(proyectos_qs) -> dict:
    """Un renglón POR PRODUCTO del proveedor de Tizayuca (Oscar 2026-07-25):
    «proyecto · cliente · fecha · producto x N pz».

    N son las piezas que hay que producir: cantidad **+ merma**. Si un proyecto
    lleva varios productos de ese proveedor, cada uno va en su propio renglón.
    Solo cuentan las líneas incluidas en el cálculo (las apagadas no se
    producen — mismo criterio que los chips del Kanban).
    """
    from apps.el_catalogo.calculadora import PROVEEDOR_CALCULADORA
    from apps.los_proyectos.models import ProyectoProducto
    from django.db.models import Q

    lineas_qs = (
        ProyectoProducto.objects.filter(
            proyecto__in=proyectos_qs, incluir_en_calculo=True,
        )
        .filter(
            Q(proveedor__razon_social__icontains=PROVEEDOR_CALCULADORA)
            | Q(servicio__proveedores__razon_social__icontains=PROVEEDOR_CALCULADORA)
        )
        .select_related("proyecto", "proyecto__cliente", "servicio", "variacion")
        .distinct()
    )
    lejos = date(9999, 12, 31)
    filas = sorted(
        lineas_qs[: LIMITE_SECCION * 3],
        key=lambda pp: (pp.proyecto.fecha_compromiso or lejos, pp.proyecto_id, pp.orden, pp.pk),
    )
    lineas = []
    for pp in filas[:LIMITE_SECCION]:
        piezas = (pp.cantidad or 0) + (pp.merma or 0)
        lineas.append(
            f"{_nombre_proyecto(pp.proyecto)} · {_cliente_de(pp.proyecto)} · "
            f"{_fecha(pp.proyecto.fecha_compromiso)} · {pp.nombre_visible} x {piezas} pz"
        )
    return {"titulo": "TIZAYUCA", "lineas": lineas}


def _seccion_facturas_por_emitir(proyectos_qs) -> dict:
    from apps.facturacion.models import Factura
    con_factura = set(
        Factura.objects.exclude(estado="cancelada")
        .exclude(proyecto__isnull=True)
        .values_list("proyecto_id", flat=True)
    )
    qs = (
        proyectos_qs.filter(estado__in=ESTADOS_CONFIRMADOS)
        .exclude(pk__in=con_factura)
        .order_by("fecha_compromiso", "pk")
    )
    lineas = [f"{_nombre_proyecto(p)} · {_cliente_de(p)}" for p in qs[:LIMITE_SECCION]]
    return {"titulo": "FACTURAS X EMITIR", "lineas": lineas}


def _seccion_cotizaciones(proyectos_qs) -> dict:
    qs = proyectos_qs.filter(estado="por_cotizar").order_by("fecha_compromiso", "pk")
    lineas = [f"{_nombre_proyecto(p)} · {_cliente_de(p)}" for p in qs[:LIMITE_SECCION]]
    return {"titulo": "COTIZACIONES", "lineas": lineas}


def _seccion_facturas_por_cobrar() -> dict:
    """**Excepción a la regla de fechas** (Oscar 2026-07-25): aquí salen TODAS
    las facturas con saldo —vencidas incluidas— hasta que se marquen cobradas o
    se les ligue el cobro. Una factura por cobrar no deja de importar por haber
    pasado su fecha; al contrario."""
    from apps.facturacion.models import Factura
    qs = (
        Factura.objects.filter(estado__in=ESTADOS_FACTURA_POR_COBRAR)
        .select_related("cliente", "proyecto")
        .order_by("fecha_vencimiento", "pk")
    )
    lineas = []
    for f in qs[: LIMITE_SECCION * 2]:
        if f.saldo_pendiente <= 0:
            continue
        cliente = (getattr(f.cliente, "razon_social", "") or "").strip() or "sin cliente"
        lineas.append(f"{f.folio_display} · {cliente} · saldo {f.saldo_pendiente:,.2f}")
        if len(lineas) >= LIMITE_SECCION:
            break
    return {"titulo": "FACTURAS X COBRAR", "lineas": lineas}


# ── Entrada pública ──────────────────────────────────────────────────────────

def secciones_pendientes(usuario) -> list[dict]:
    """Arma el reporte completo: lista de `{titulo, lineas}` en orden fijo.

    Nunca lanza por permisos: las secciones que el usuario no puede ver se
    omiten (no se muestran vacías).
    """
    from apps.los_proyectos.views import _proyectos_visibles
    from django.db.models import Q

    from lib.permisos import puede_ver_cotizaciones, puede_ver_facturacion

    tareas = list(_tareas_pendientes(usuario))
    secciones: list[dict] = [_seccion_urgentes(tareas)]
    secciones += _secciones_por_persona(tareas)
    secciones.append(_seccion_misiones(usuario))

    proyectos = (
        _proyectos_visibles(usuario)
        .exclude(estado__in=("cancelado",))
        .filter(Q(fecha_compromiso__isnull=True) | Q(fecha_compromiso__gte=date.today()))
    )
    secciones.append(_seccion_tizayuca(proyectos))
    if puede_ver_facturacion(usuario):
        secciones.append(_seccion_facturas_por_emitir(proyectos))
    if puede_ver_cotizaciones(usuario):
        secciones.append(_seccion_cotizaciones(proyectos))
    if puede_ver_facturacion(usuario):
        secciones.append(_seccion_facturas_por_cobrar())
    return secciones


def texto_pendientes(usuario) -> str:
    """El reporte en texto plano (para copiar/pegar). Sin HTML."""
    bloques = [encabezado_fecha()]
    for sec in secciones_pendientes(usuario):
        cuerpo = "\n".join(sec["lineas"]) if sec["lineas"] else "(ninguno)"
        bloques.append(f"{sec['titulo']}\n{cuerpo}")
    return "\n\n".join(bloques)


__all__ = [
    "secciones_pendientes",
    "texto_pendientes",
    "encabezado_fecha",
    "ESTADOS_CONFIRMADOS",
]
