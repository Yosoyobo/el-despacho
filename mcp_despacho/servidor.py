"""Entrypoint MCP por stdio para El Despacho."""

from __future__ import annotations

from typing import Any

from mcp_despacho.django_setup import configurar_django

configurar_django()

from mcp.server.fastmcp import FastMCP  # noqa: E402

from mcp_despacho import herramientas  # noqa: E402

mcp = FastMCP(
    "El Despacho",
    instructions=(
        "Consulta de sólo lectura del CRM/ERP Learning Center. "
        "Respeta la identidad configurada y los permisos granulares de El Despacho."
    ),
)


@mcp.tool()
def identidad_actual() -> dict[str, Any]:
    """Muestra qué usuario opera esta conexión y qué módulos puede consultar."""
    return herramientas.identidad_actual()


@mcp.tool()
def buscar_clientes(
    consulta: str = "", incluir_archivados: bool = False, limite: int = 20
) -> dict[str, Any]:
    """Busca clientes por razón social, RFC, contacto o correo."""
    return herramientas.buscar_clientes(consulta, incluir_archivados, limite)


@mcp.tool()
def buscar_proyectos(
    consulta: str = "",
    estado: str = "",
    incluir_archivados: bool = False,
    limite: int = 20,
) -> dict[str, Any]:
    """Busca proyectos visibles por nombre, código, cliente y estado."""
    return herramientas.buscar_proyectos(consulta, estado, incluir_archivados, limite)


@mcp.tool()
def obtener_proyecto(referencia: str) -> dict[str, Any]:
    """Obtiene un proyecto por ID, código LC-0001, slug o #referencia."""
    return herramientas.obtener_proyecto(referencia)


@mcp.tool()
def listar_tareas(
    consulta: str = "",
    estado: str = "",
    proyecto: str = "",
    incluir_archivadas: bool = False,
    limite: int = 30,
) -> dict[str, Any]:
    """Lista tareas visibles y permite filtrar por proyecto o estado."""
    return herramientas.listar_tareas(
        consulta, estado, proyecto, incluir_archivadas, limite
    )


@mcp.tool()
def resumen_negocio(tema: str = "") -> dict[str, Any]:
    """Lee un tema del negocio: finanzas, cobranza, ventas, rentabilidad,
    perdidos, clientes, proveedores, equipo o ia. Sin tema, lista los que este
    usuario puede ver."""
    return herramientas.resumen_negocio(tema)


@mcp.tool()
def rentabilidad_proyectos(
    incluir_terminados: bool = True, limite: int = 30
) -> dict[str, Any]:
    """Rentabilidad real de cada proyecto: vendido, costo, utilidad y margen,
    del peor al mejor."""
    return herramientas.rentabilidad_proyectos(incluir_terminados, limite)


@mcp.tool()
def indicadores(categoria: str = "", limite: int = 40) -> dict[str, Any]:
    """Lista los indicadores del despacho con su valor de hoy, su tendencia y si
    alguno se salió de lo normal. Filtra por categoría: dinero, operacion,
    cartera, catalogo, proveedores, runner, maquina, ia, gente, buzon."""
    return herramientas.indicadores(categoria, limite)


@mcp.tool()
def serie_indicador(slug: str, dias: int = 90) -> dict[str, Any]:
    """La historia diaria de un indicador y su comparación contra el periodo
    anterior — para graficar o analizar fuera del sistema."""
    return herramientas.serie_indicador(slug, dias)


@mcp.tool()
def accesos_portal(cliente: str) -> dict[str, Any]:
    """Quién de un cliente puede entrar al portal de clientes (La Recepción),
    cuándo entró por última vez, y qué contactos con correo todavía no."""
    return herramientas.accesos_portal(cliente)


@mcp.tool()
def documentos_del_cliente(cliente: str = "") -> dict[str, Any]:
    """La papelería que entregan los clientes por el portal (comprobantes de pago,
    constancia fiscal, acta…): qué falta, qué subieron, su estado y lo que El
    Chalán leyó de la constancia. Sin cliente, lo que está por revisar en todos."""
    return herramientas.documentos_del_cliente(cliente)


@mcp.tool()
def pagos_en_linea(estado: str = "", limite: int = 20) -> dict[str, Any]:
    """La Caja: pagos que llegaron por Stripe o MercadoPago —registrados solos,
    por revisar (con el motivo) o por acreditar— y lo cobrado en línea este mes.
    Filtra por estado: registrado, por_revisar, pendiente, rechazado, descartado."""
    return herramientas.pagos_en_linea(estado, limite)


@mcp.tool()
def links_de_pago(estado: str = "", limite: int = 20) -> dict[str, Any]:
    """La Caja: links de pago en línea de facturas, anticipos y montos libres.
    Filtra por estado: vigente, pagado, anulado, vencido."""
    return herramientas.links_de_pago(estado, limite)


@mcp.tool()
def nomina_quincena(fecha: str = "") -> dict[str, Any]:
    """La Nómina de una quincena (1–15 o 16–fin de mes): estado, total a pagar,
    sueldos, percepciones, deducciones y neto de cada persona. Requiere permiso
    de nómina. `fecha` es cualquier día de la quincena (AAAA-MM-DD); vacío = hoy.
    Calcular, cerrar o pagar no se hace por aquí: son botones de Nómina."""
    return herramientas.nomina_quincena(fecha)


@mcp.tool()
def mi_recibo(fecha: str = "") -> dict[str, Any]:
    """Tu recibo de nómina de una quincena ya cerrada: sueldo, conceptos, neto
    y si ya se depositó. Sólo el de quien opera esta conexión."""
    return herramientas.mi_recibo(fecha)


@mcp.tool()
def historial_de_actividad(persona: str = "", fecha: str = "") -> dict[str, Any]:
    """Qué hizo una persona en un día: a qué hora entró y salió, qué pantallas abrió,
    qué guardó y su tiempo activo. Sin persona, el tuyo. Fecha: hoy, ayer, anteayer
    o AAAA-MM-DD (se guarda un año). El de otro pide permiso de ver el historial."""
    return herramientas.historial_de_actividad(persona, fecha)


def main() -> None:
    """Sirve MCP sólo por stdio; no abre puertos ni omite autenticación HTTP."""
    mcp.run(transport="stdio")
