"""De una ruta a lo que una persona está haciendo.

El flujo de El Vigía mostraba rutas: `/proyectos/kanban/`, `/medios/ab/cd/x/w400.png`.
Eso es correcto y es ilegible desde tres metros. Lo que la pared debe decir es
«Tablero de proyectos» y «Foto de producto» — el **qué**, no el **dónde**.

El mapa es a propósito una lista de pares (patrón, nombre) recorrida en orden, no
un diccionario: el orden importa porque las reglas van de lo específico a lo
general (`/proyectos/kanban/` antes que `/proyectos/`), y así una ruta nueva cae
en la regla general de su módulo en vez de quedar sin nombre.

Cuando nada casa se devuelve la ruta tal cual. Es lo correcto: inventar un nombre
para algo que no se reconoce sería peor que enseñar la verdad cruda.
"""

from __future__ import annotations

import re

# (patrón, qué está haciendo la persona). Se recorre en orden: lo específico primero.
_MAPA: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p), n) for p, n in (
        # ── Lo que más se ve: medios ─────────────────────────────────────────
        (r"^/medios/",                          "Foto de producto"),
        (r"^/catalogo/imagen-producto/",        "Foto de producto"),
        (r"^/perfil/avatar-img/",               "Foto de perfil"),

        # ── Proyectos ────────────────────────────────────────────────────────
        (r"^/proyectos/kanban",                 "Tablero de proyectos"),
        (r"^/proyectos/cancelaciones",          "Estadísticas de cancelación"),
        (r"^/proyectos/nuevo",                  "Alta de proyecto"),
        (r"^/proyectos/\d+/pago-proveedor",     "Pago a proveedor"),
        (r"^/proyectos/\d+/editar",             "Edición de proyecto"),
        (r"^/proyectos/\d+/",                   "Ficha de proyecto"),
        (r"^/proyectos/",                       "Proyectos"),

        # ── Tareas y mandados ────────────────────────────────────────────────
        (r"^/tareas/lista",                     "Lista de tareas"),
        (r"^/tareas/nueva",                     "Alta de tarea"),
        (r"^/tareas/",                          "Tablero de tareas"),
        (r"^/mandados/",                        "Mandados"),
        (r"^/pizarron/",                        "Tareas"),

        # ── Dinero ───────────────────────────────────────────────────────────
        (r"^/cotizaciones/\d+/documento",       "Documento de cotización"),
        (r"^/cotizaciones/\d+/pdf",             "PDF de cotización"),
        (r"^/cotizaciones/\d+/",                "Ficha de cotización"),
        (r"^/cotizaciones/",                    "Cotizaciones"),
        (r"^/facturacion/\d+/",                 "Ficha de factura"),
        (r"^/facturacion/",                     "Facturación"),
        (r"^/tesoreria/gastos-no-registrados",  "Gastos por registrar"),
        (r"^/tesoreria/(ingresos|egresos)",     "Movimientos de dinero"),
        (r"^/tesoreria/por-(cobrar|pagar)",     "Cuentas por cobrar y pagar"),
        (r"^/tesoreria/",                       "Tesorería"),
        (r"^/contaduria/",                      "Contaduría"),

        # ── Gente y catálogo ─────────────────────────────────────────────────
        (r"^/clientes/|^/cartera/",             "Clientes"),
        (r"^/catalogo/proveedores",             "Proveedores"),
        (r"^/catalogo/",                        "Productos"),
        (r"^/equipo/",                          "Equipo"),
        (r"^/directorio/",                      "Directorio"),

        # ── Comunicación ─────────────────────────────────────────────────────
        (r"^/recados/buzon",                    "Mi buzón"),
        (r"^/recados/",                         "Mensajes"),
        (r"^/buzon/",                           "Buzón de soporte"),
        (r"^/campanas/",                        "Campañas de correo"),

        # ── El Chalán y la IA ────────────────────────────────────────────────
        (r"^/chalan/",                          "El Chalán"),
        (r"^/dictado/",                         "El Dictado"),
        (r"^/chalanes/",                        "Los Chalanes"),

        # ── El Checador ──────────────────────────────────────────────────────
        (r"^/checador/api/sync",                "Checadas guardadas sin señal"),
        (r"^/checador/equipo",                  "Reporte de asistencia"),
        (r"^/checador/",                        "El Checador"),

        # ── Calendario, ayuda, tablero ───────────────────────────────────────
        (r"^/calendario/",                      "Calendario"),
        (r"^/ayuda/novedades",                  "Novedades"),
        (r"^/ayuda/",                           "Manual de uso"),
        (r"^/resumen/actividad",                "Resumen de pendientes"),
        (r"^/kpis/",                            "KPIs del tablero"),
        (r"^/perfil/",                          "Preferencias"),
        (r"^/site/",                            "El Site"),
        (r"^/ajustes/",                         "Ajustes"),
        (r"^/legal/|^/acerca",                  "Aviso legal"),

        # ── Entrar y salir ───────────────────────────────────────────────────
        (r"^/(sign-in|login|entrar)",           "Iniciar sesión"),
        (r"^/(sign-out|logout|salir)",          "Cerrar sesión"),
        (r"^/auth/google",                      "Entrar con Google"),

        # ── Lo del navegador, que no es una persona ──────────────────────────
        (r"^/(static|sw\.js|manifest|favicon)", "Recursos del navegador"),

        # ── Y al final, la raíz: cualquier ruta corta cae aquí ───────────────
        (r"^/$",                                "Tablero"),
    )
)

# Navegadores y aparatos, para decir DESDE QUÉ se está usando el sistema. El
# orden importa: Edge y Chrome se anuncian los dos como "Chrome", y iPad se
# anuncia como Macintosh en modo escritorio.
_AGENTES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p, re.I), n) for p, n in (
        (r"iphone",                    "iPhone"),
        (r"ipad",                      "iPad"),
        (r"android",                   "Android"),
        (r"edg/",                      "Edge"),
        (r"opr/|opera",                "Opera"),
        (r"chrome|crios",              "Chrome"),
        (r"firefox|fxios",             "Firefox"),
        (r"safari",                    "Safari"),
        (r"curl|wget|httpx|python",    "Un guion"),
        (r"bot|crawler|spider",        "Un robot"),
    )
)


def nombrar(ruta: str) -> str:
    """Lo que una persona está haciendo, según la ruta que pidió."""
    if not ruta:
        return "?"
    limpia = ruta.split("?")[0]
    for patron, nombre in _MAPA:
        if patron.search(limpia):
            return nombre
    return limpia


def aparato(user_agent: str | None) -> str:
    """Desde qué se está usando el sistema. Cadena vacía si no se sabe."""
    if not user_agent or user_agent == "-":
        return ""
    for patron, nombre in _AGENTES:
        if patron.search(user_agent):
            return nombre
    return ""


def quien(xff: str | None, ip_directa: str | None = None) -> str:
    """La dirección del visitante de verdad.

    Detrás de El Portero, la IP que ve gunicorn es la del proxy —siempre la
    misma— así que por sí sola no distingue a nadie. La real viene en
    `X-Forwarded-For`, y **el primer salto de esa lista** es el cliente: los
    demás son proxies que se fueron agregando.
    """
    for candidata in ((xff or "").split(",")[0].strip(), (ip_directa or "").strip()):
        if candidata and candidata != "-":
            return candidata
    return ""


__all__ = ["aparato", "nombrar", "quien"]
