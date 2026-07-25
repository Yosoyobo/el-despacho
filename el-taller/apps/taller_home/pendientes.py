"""Resumen de pendientes del taller — herramienta del Dashboard (2026-07).

Pedido de Oscar: un reporte de **texto simple** (sin emojis, secciones
separadas por `<br>`, negritas SOLO en los títulos) con todo lo que está
pendiente a futuro, listo para leer de un vistazo o copiar y pegar.

**Es determinista** — se arma con queries, NO con IA. Un reporte operativo
debe ser exacto y gratis; el resumen narrativo con IA vive por proyecto en
`apps.los_proyectos.resumen_ia`.

Secciones (orden fijo, decisión Oscar):
  1. URGENTES ............ tareas de TODO el equipo marcadas alta o ya vencidas
  2..N. <PERSONA> ........ una sección por persona con pendientes asignados
  N+1. MISIONES .......... mandados (entregas/recolecciones) sin cerrar
  N+2. TIZAYUCA .......... proyectos vigentes con el proveedor de Tizayuca
  N+3. FACTURAS X EMITIR . proyectos confirmados sin factura ligada
  N+4. COTIZACIONES ...... proyectos en «por cotizar»
  N+5. FACTURAS X COBRAR . facturas emitidas con saldo pendiente

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

_MESES = ("ene", "feb", "mar", "abr", "may", "jun",
          "jul", "ago", "sep", "oct", "nov", "dic")

# Tope por sección para que el reporte siga siendo legible (y el modal, corto).
LIMITE_SECCION = 40


def _fecha(d) -> str:
    """`date`/`datetime` → «26 jul» (o «26 jul 2027» si no es el año en curso).

    Los `datetime` aware se pasan a hora local ANTES de leer el día: leerlos en
    UTC corre la fecha (el bug +6h de S-Chalan-Barrido).
    """
    if not d:
        return "sin fecha"
    if isinstance(d, datetime):
        from django.utils import timezone
        d = timezone.localtime(d).date() if timezone.is_aware(d) else d.date()
    txt = f"{d.day} {_MESES[d.month - 1]}"
    return txt if d.year == date.today().year else f"{txt} {d.year}"


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
    """Tareas vigentes visibles: ni terminales ni archivadas."""
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    from apps.el_pizarron.views import _tareas_visibles
    return (
        _tareas_visibles(user)
        .filter(archivada=False)
        .exclude(estado__in=slugs_terminales_tarea())
    )


def _seccion_urgentes(tareas: list) -> dict:
    hoy = date.today()
    urgentes = [
        t for t in tareas
        if t.prioridad == "alta" or (t.fecha_compromiso and t.fecha_compromiso < hoy)
    ]
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
    mandados = list(
        mandados_visibles(user)
        .exclude(estado__in=("entregado", "cancelado"))[:LIMITE_SECCION * 2]
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
    """Proyectos vigentes que llevan producto del proveedor de Tizayuca —
    ligado a la línea del proyecto o al producto del catálogo."""
    from apps.el_catalogo.calculadora import PROVEEDOR_CALCULADORA
    from django.db.models import Q
    qs = (
        proyectos_qs.filter(
            Q(productos__proveedor__razon_social__icontains=PROVEEDOR_CALCULADORA)
            | Q(productos__servicio__proveedores__razon_social__icontains=PROVEEDOR_CALCULADORA)
        )
        .distinct()
        .order_by("fecha_compromiso", "pk")
    )
    lineas = [
        f"{_nombre_proyecto(p)} · {_cliente_de(p)} · {_fecha(p.fecha_compromiso)}"
        for p in qs[:LIMITE_SECCION]
    ]
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

    from lib.permisos import puede_ver_cotizaciones, puede_ver_facturacion

    tareas = list(_tareas_pendientes(usuario))
    secciones: list[dict] = [_seccion_urgentes(tareas)]
    secciones += _secciones_por_persona(tareas)
    secciones.append(_seccion_misiones(usuario))

    proyectos = _proyectos_visibles(usuario).exclude(estado__in=("cancelado",))
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
    bloques = []
    for sec in secciones_pendientes(usuario):
        cuerpo = "\n".join(sec["lineas"]) if sec["lineas"] else "(ninguno)"
        bloques.append(f"{sec['titulo']}\n{cuerpo}")
    return "\n\n".join(bloques)


__all__ = ["secciones_pendientes", "texto_pendientes", "ESTADOS_CONFIRMADOS"]
