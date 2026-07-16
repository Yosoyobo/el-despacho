"""Fachada del servidor MCP: identidad + gating; las lecturas viven en
`capacidades.mcp_lecturas` (S-Chalan-MCP-V1 commit 2).

Falla cerrada si falta identidad, si el usuario está inactivo o si no tiene los
dos permisos requeridos: `mcp.usar` y el permiso del módulo consultado. Las
consultas son de sólo lectura; ninguna herramienta muta la DB.
"""

from __future__ import annotations

import os
from typing import Any

from lib.permisos import puede, roles_efectivos, tiene_rol

ENV_USUARIO = "DESPACHO_MCP_USUARIO_EMAIL"


class ErrorAccesoMCP(PermissionError):
    """Error seguro y legible para clientes MCP."""


def _texto(valor: str, maximo: int = 254) -> str:
    return (valor or "").strip()[:maximo]


def _usuario_actual():
    from cuentas.models import Usuario

    email = _texto(os.environ.get(ENV_USUARIO, ""), 254).lower()
    if not email:
        raise ErrorAccesoMCP(
            f"Falta {ENV_USUARIO}; configura el correo del usuario que operará MCP."
        )
    usuario = (
        Usuario.objects.filter(email__iexact=email, is_active=True)
        .prefetch_related("roles_extra")
        .first()
    )
    if usuario is None:
        raise ErrorAccesoMCP("El usuario MCP no existe o está inactivo.")
    _exigir_permiso(usuario, "mcp", "usar")
    return usuario


def _exigir_permiso(usuario, modulo: str, accion: str) -> None:
    if tiene_rol(usuario, "super_admin") or puede(usuario, modulo, accion):
        return
    raise ErrorAccesoMCP(f"Sin permiso {modulo}.{accion}.")


def identidad_actual() -> dict[str, Any]:
    """Devuelve la identidad y capacidades efectivas de esta conexión MCP."""
    usuario = _usuario_actual()
    modulos_lectura = [
        modulo
        for modulo, accion in (
            ("cartera", "ver"),
            ("proyectos", "ver"),
            ("pizarron", "ver"),
        )
        if tiene_rol(usuario, "super_admin") or puede(usuario, modulo, accion)
    ]
    return {
        "id": usuario.pk,
        "email": usuario.email,
        "nombre": usuario.nombre_completo,
        "roles": sorted(roles_efectivos(usuario)),
        "modulos_lectura": modulos_lectura,
        "modo": "solo_lectura",
    }


def buscar_clientes(
    consulta: str = "", incluir_archivados: bool = False, limite: int = 20
) -> dict[str, Any]:
    """Busca clientes por razón social, RFC, contacto o correo."""
    from capacidades.mcp_lecturas import buscar_clientes_impl

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "cartera", "ver")
    return buscar_clientes_impl(
        {"consulta": consulta, "incluir_archivados": incluir_archivados, "limite": limite},
        usuario,
    )


def buscar_proyectos(
    consulta: str = "",
    estado: str = "",
    incluir_archivados: bool = False,
    limite: int = 20,
) -> dict[str, Any]:
    """Lista proyectos visibles, filtrables por texto y estado."""
    from capacidades.mcp_lecturas import buscar_proyectos_impl

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "proyectos", "ver")
    return buscar_proyectos_impl(
        {
            "consulta": consulta,
            "estado": estado,
            "incluir_archivados": incluir_archivados,
            "limite": limite,
        },
        usuario,
    )


def obtener_proyecto(referencia: str) -> dict[str, Any]:
    """Obtiene el detalle de un proyecto por ID, código, slug o #referencia."""
    from capacidades.mcp_lecturas import obtener_proyecto_impl

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "proyectos", "ver")
    datos = obtener_proyecto_impl({"referencia": referencia}, usuario)
    if isinstance(datos, dict) and datos.get("error") == "no_visible":
        raise ErrorAccesoMCP("Proyecto inexistente o no visible para este usuario.")
    return datos


def listar_tareas(
    consulta: str = "",
    estado: str = "",
    proyecto: str = "",
    incluir_archivadas: bool = False,
    limite: int = 30,
) -> dict[str, Any]:
    """Lista tareas visibles por texto, estado y proyecto."""
    from capacidades.mcp_lecturas import listar_tareas_impl

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "pizarron", "ver")
    return listar_tareas_impl(
        {
            "consulta": consulta,
            "estado": estado,
            "proyecto": proyecto,
            "incluir_archivadas": incluir_archivadas,
            "limite": limite,
        },
        usuario,
    )
