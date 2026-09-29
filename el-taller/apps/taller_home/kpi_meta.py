"""Lo que cada KPI del catálogo es, además de su cálculo.

Para juzgar un indicador no basta su número: hay que saber hacia dónde es
mejor, si se reinicia cada periodo, si depende de quién lo mira y cómo se lee.
Los KPIs nuevos lo declaran al construirse (`KPI(..., direccion="baja")`);
los del catálogo original lo toman de aquí para no reescribir sus 92 renglones.

- `direccion`: `sube` (más es mejor) · `baja` (menos es mejor: vencidos,
  deudas, errores) · `neutro` (informa, no se persigue).
- `acumula`: `dia` · `semana` · `mes` · `ano` si el número vuelve a cero al
  empezar ese periodo («ingresos del mes»). Una meta sobre él se mide
  proporcional al avance del periodo; uno que no acumula es un saldo al corte.
- `personal`: depende de quién pregunta («mis tareas»). No es un número del
  despacho: no entra a la foto diaria ni lleva meta del despacho.
- `acotado`: el despacho ve el total, pero quien sólo ve sus proyectos ve lo
  suyo. Su historia es la del despacho: no se compara contra la de esa persona.
- `formato`: `numero` · `dinero` · `pct` · `dias` · `horas` · `minutos` · `km`.
"""

from __future__ import annotations

DIRECCIONES = (("sube", "Más es mejor"), ("baja", "Menos es mejor"), ("neutro", "Sólo informa"))
PERIODOS_ACUMULA = (("", "Saldo al corte"), ("dia", "Del día"), ("semana", "De la semana"),
                    ("mes", "Del mes"), ("ano", "Del año"))
FORMATOS = ("numero", "dinero", "pct", "dias", "horas", "minutos", "km")

_BAJA = {
    "cotizados-sin-avance", "proyectos-en-pausa", "proyectos-vencidos",
    "proyectos-sin-actividad", "proyectos-cancelados-mes", "mis-tareas-vencidas",
    "tareas-vencidas-equipo", "tareas-bloqueadas", "tareas-sin-asignar",
    "buzon-sin-responder", "buzon-bugs-abiertos", "buzon-mios-sin-responder",
    "mis-recados-no-leidos", "clientes-sin-proyectos", "site-integraciones-rojo",
    "egresos-mes", "cxc-total", "cxp-total", "reembolsos-pendientes",
    "cotizaciones-vencidas", "anticipos-pendientes", "facturas-pendientes-cobro",
    "facturas-vencidas", "monto-por-cobrar", "contaduria-balance-descuadrado",
    "checador-retardos-mes", "buzon-urgentes", "buzon-tiempo-respuesta",
    "cotizaciones-sin-enviar", "cotizaciones-enfriadas", "proyectos-en-perdida",
    "proyectos-bajo-margen", "facturas-cfdi-sin-emitir", "productos-sin-costo",
    "deuda-proveedores", "egresos-sin-proveedor", "clientes-dormidos",
    "concentracion-cliente", "mandados-sin-runner", "mandado-minutos-promedio",
    "nuc-cpu", "nuc-memoria", "nuc-disco", "ia-gasto-30d", "ia-fallos-pct",
    "accesos-fallidos", "cuentas-sin-entrar", "retardos-mes", "jornadas-sin-cerrar",
}
_NEUTRO = {
    "mis-tareas-proximas-3d", "por-entregar-esta-semana", "buzon-sugerencias",
    "recados-enviados-semana", "interfon-pushes-semana", "contaduria-asientos-mes",
    "checador-horas-por-proyecto-top", "nuc-contenedores", "ia-llamadas-30d",
    "accesos-hoy", "mandados-abiertos", "mandado-km-mes", "cotizaciones-pendientes",
}
_ACUMULA = {
    "dia": {"accesos-hoy"},
    "semana": {
        "tareas-completadas-semana", "recados-enviados-semana", "interfon-pushes-semana",
        "checador-horas-semana", "checador-visitas-semana", "mandados-entregados-semana",
        "horas-equipo-semana", "visitas-semana", "actividad-semana", "usuarios-activos-semana",
    },
    "mes": {
        "proyectos-cancelados-mes", "clientes-nuevos-mes", "ingresos-mes", "egresos-mes",
        "utilidad-mes", "cotizaciones-aprobadas-mes", "facturado-mes",
        "contaduria-asientos-mes", "contaduria-utilidad-neta-mes", "checador-retardos-mes",
        "productos-usados-mes", "mandado-km-mes", "retardos-mes",
    },
}
_PERSONAL = {
    "mis-tareas-vencidas", "mis-tareas-proximas-3d", "buzon-mios-sin-responder",
    "mis-recados-no-leidos", "recados-enviados-semana", "checador-horas-semana",
    "checador-retardos-mes", "checador-visitas-semana", "checador-horas-por-proyecto-top",
}
_ACOTADO = {"proyectos-activos", "valor-proyectos", "por-entregar-esta-semana", "proyectos-vencidos"}
_FORMATO = {
    "dinero": {
        "valor-proyectos", "ingresos-mes", "egresos-mes", "utilidad-mes", "cxc-total",
        "cxp-total", "reembolsos-pendientes", "monto-por-cobrar", "facturado-mes",
        "contaduria-saldo-banco", "contaduria-utilidad-neta-mes", "deuda-proveedores",
        "ticket-promedio", "ia-gasto-30d",
    },
    "pct": {
        "conversion-oportunidades", "margen-real", "margen-catalogo", "concentracion-cliente",
        "ia-fallos-pct", "horas-imputadas-pct", "nuc-cpu", "nuc-memoria", "nuc-disco",
    },
    "dias": {"buzon-tiempo-respuesta", "dias-de-caja"},
    "horas": {"checador-horas-semana", "horas-equipo-semana", "checador-horas-por-proyecto-top"},
    "minutos": {"mandado-minutos-promedio"},
    "km": {"mandado-km-mes"},
}


def metadatos_de(slug: str) -> dict:
    """Los metadatos de un KPI del catálogo original (los defaults si no está)."""
    direccion = "baja" if slug in _BAJA else ("neutro" if slug in _NEUTRO else "sube")
    acumula = next((p for p, slugs in _ACUMULA.items() if slug in slugs), "")
    formato = next((f for f, slugs in _FORMATO.items() if slug in slugs), "numero")
    return {
        "direccion": direccion,
        "acumula": acumula,
        "personal": slug in _PERSONAL or slug.startswith("mis-"),
        "acotado": slug in _ACOTADO,
        "formato": formato,
    }
