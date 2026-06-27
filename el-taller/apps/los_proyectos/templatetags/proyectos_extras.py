from datetime import date, datetime

from django import template

register = template.Library()


@register.filter(name="nombre_cliente")
def nombre_cliente(proyecto):
    """Decisión Oscar: en widgets/listas el protagonista es el NOMBRE del
    proyecto + el NOMBRE del cliente (en esa prioridad), no el código LC-NNNN.

    Devuelve "Nombre · Cliente" tolerando nulos (proyecto, cliente, campos
    vacíos). Si no hay proyecto, devuelve "". Si falta el cliente, devuelve
    solo el nombre del proyecto (con fallback al código si tampoco hay nombre).
    """
    if not proyecto:
        return ""
    nombre = (getattr(proyecto, "nombre", "") or "").strip()
    cliente = getattr(proyecto, "cliente", None)
    razon = (getattr(cliente, "razon_social", "") or "").strip() if cliente else ""
    if not nombre:
        nombre = (getattr(proyecto, "codigo", "") or "").strip()
    if nombre and razon:
        return f"{nombre} · {razon}"
    return nombre or razon


@register.filter(name="dentro_de")
def dentro_de(fecha):
    """Devuelve 'dentro de N días' / 'hoy' / 'vencido hace N días' para una fecha."""
    if not fecha:
        return "—"
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    hoy = date.today()
    delta = (fecha - hoy).days
    if delta == 0:
        return "hoy"
    if delta == 1:
        return "mañana"
    if delta == -1:
        return "ayer"
    if delta > 0:
        return f"en {delta} días"
    return f"vencido hace {-delta} días"


@register.filter(name="dentro_de_clase")
def dentro_de_clase(fecha):
    """Color del texto según urgencia: rojo si vencido, naranja ≤3d, gris."""
    if not fecha:
        return "text-gray-400"
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    delta = (fecha - date.today()).days
    if delta < 0:
        return "text-error-600 dark:text-error-400 font-medium"
    if delta <= 3:
        return "text-warning-600 dark:text-warning-400 font-medium"
    return "text-gray-600 dark:text-gray-300"

# S-Estados-Color-HEX: el color del estado es un HEX libre. El fallback
# (estados legacy sin fila en DB) usa la paleta TailAdmin canónica.
_COLORES_FALLBACK = {
    "por_cotizar": "#0ba5ec",
    "esperando_respuesta": "#fb6514",
    "en_proceso_diseno": "#f79009",
    "en_proceso_produccion": "#f79009",
    "entregado": "#12b76a",
    "cerrado": "#465fff",
    "en_pausa": "#667085",
    "cancelado": "#f04438",
}


def _mapa_estados():
    """Cache de proceso (60s) del mapa slug → {label, color}.

    Evita N+1 queries en listas/Kanban con muchos badges. Cambios desde
    Gerencia se ven a los ≤60s sin restart. Tolerante a DB no migrada
    (tests aislados, primer boot).
    """
    from django.core.cache import cache
    clave = "proyectos:mapa_estados:v1"
    cacheado = cache.get(clave)
    if cacheado is not None:
        return cacheado
    from apps.los_proyectos.models import EstadoProyecto
    try:
        mapa = {
            e.slug: {"label": e.label, "color": e.color}
            for e in EstadoProyecto.objects.all()
        }
        cache.set(clave, mapa, 60)
        return mapa
    except Exception:
        return {}


def invalidar_mapa_estados():
    """Llamado desde signals al guardar/borrar EstadoProyecto."""
    from django.core.cache import cache
    cache.delete("proyectos:mapa_estados:v1")


@register.filter(name="color_estado")
def color_estado(estado: str) -> str:
    """Color HEX del estado (#RRGGBB). Se inyecta en la custom property --ec."""
    mapa = _mapa_estados()
    if estado in mapa:
        return mapa[estado]["color"]
    return _COLORES_FALLBACK.get(estado, "#667085")


@register.filter(name="estado_label")
def estado_label(estado: str) -> str:
    """Label visible del estado (configurable desde Gerencia)."""
    mapa = _mapa_estados()
    if estado in mapa:
        return mapa[estado]["label"]
    for slug, label in (
        ("por_cotizar", "Por cotizar"),
        ("esperando_respuesta", "Esperando respuesta"),
        ("en_proceso_diseno", "En proceso de diseño"),
        ("en_proceso_produccion", "En proceso de producción"),
        ("entregado", "Entregado"),
        ("cerrado", "Cerrado"),
        ("en_pausa", "En pausa"),
        ("cancelado", "Cancelado"),
    ):
        if slug == estado:
            return label
    return estado
