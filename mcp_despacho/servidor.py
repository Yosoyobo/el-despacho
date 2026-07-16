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


def main() -> None:
    """Sirve MCP sólo por stdio; no abre puertos ni omite autenticación HTTP."""
    mcp.run(transport="stdio")
