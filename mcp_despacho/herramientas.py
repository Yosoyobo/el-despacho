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


def resumen_negocio(tema: str = "") -> dict[str, Any]:
    """Un tema del negocio (finanzas, cobranza, ventas, rentabilidad, perdidos,
    clientes, proveedores, equipo, ia). Sin tema, lista los disponibles."""
    from capacidades.mcp_lecturas import resumen_negocio_impl

    usuario = _usuario_actual()
    datos = resumen_negocio_impl({"tema": tema}, usuario)
    if isinstance(datos, dict) and datos.get("error") == "no_visible":
        raise ErrorAccesoMCP(f"Sin permiso para ver el tema «{tema}».")
    return datos


def rentabilidad_proyectos(
    incluir_terminados: bool = True, limite: int = 30
) -> dict[str, Any]:
    """Rentabilidad real por proyecto: ingreso, costo, utilidad y margen."""
    from capacidades.mcp_lecturas import rentabilidad_impl

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "tesoreria", "ver")
    return rentabilidad_impl(
        {"incluir_terminados": incluir_terminados, "limite": limite}, usuario
    )


def indicadores(categoria: str = "", limite: int = 40) -> dict[str, Any]:
    """Los indicadores del despacho con su valor, tendencia y anomalías."""
    from capacidades.mcp_lecturas import indicadores_impl

    usuario = _usuario_actual()
    return indicadores_impl({"categoria": categoria, "limite": limite}, usuario)


def serie_indicador(slug: str, dias: int = 90) -> dict[str, Any]:
    """La historia de un indicador: su serie diaria y cómo viene."""
    from capacidades.mcp_lecturas import serie_indicador_impl

    usuario = _usuario_actual()
    datos = serie_indicador_impl({"slug": slug, "dias": dias}, usuario)
    if isinstance(datos, dict) and datos.get("error") == "no_visible":
        raise ErrorAccesoMCP(f"No existe el indicador «{slug}».")
    return datos


def accesos_portal(cliente: str) -> dict[str, Any]:
    """Quién de un cliente puede entrar al portal de clientes (La Recepción)."""
    from capacidades.lecturas import _h_accesos_portal

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "recepcion", "ver")
    return _h_accesos_portal({"cliente": cliente}, usuario)


def documentos_del_cliente(cliente: str = "") -> dict[str, Any]:
    """La papelería que entregan los clientes por el portal."""
    from capacidades.lecturas import _h_documentos_del_cliente

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "recepcion", "documentos")
    return _h_documentos_del_cliente({"cliente": cliente}, usuario)


def pagos_en_linea(estado: str = "", limite: int = 20) -> dict[str, Any]:
    """La Caja: pagos que llegaron por Stripe/MercadoPago (registrados, por
    revisar, pendientes) y lo cobrado en línea este mes."""
    from capacidades.lecturas_caja import _h_pagos_recientes

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "caja", "ver")
    return _h_pagos_recientes({"estado": _texto(estado, 20), "limite": limite}, usuario)


def links_de_pago(estado: str = "", limite: int = 20) -> dict[str, Any]:
    """La Caja: links de pago en línea (vigentes, pagados, anulados, vencidos)."""
    from capacidades.lecturas_caja import _h_links_de_pago

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "caja", "ver")
    return _h_links_de_pago({"estado": _texto(estado, 20), "limite": limite}, usuario)


def nomina_quincena(fecha: str = "") -> dict[str, Any]:
    """La Nómina de una quincena: estado, totales y neto por persona (nomina.ver)."""
    from capacidades.lecturas_nomina import _h_nomina_quincena

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "nomina", "ver")
    return _h_nomina_quincena({"fecha": _texto(fecha, 10)}, usuario)


def formato_documentos() -> dict[str, Any]:
    """La Imprenta: cómo están configurados los PDF (documentos.ver)."""
    from capacidades.lecturas_imprenta import _h_formato_documentos

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "documentos", "ver")
    return _h_formato_documentos({}, usuario)


def enlace_documento(tipo: str, codigo: str) -> dict[str, Any]:
    """El enlace al PDF de un documento (cotización o factura comercial)."""
    from capacidades.lecturas_imprenta import _h_enlace_documento

    usuario = _usuario_actual()
    return _h_enlace_documento({"tipo": _texto(tipo, 20), "codigo": _texto(codigo, 30)}, usuario)


def ordenes_de_compra(estado: str = "", proveedor: str = "", limite: int = 20) -> dict[str, Any]:
    """Las órdenes de compra a proveedores (compras.ver)."""
    from capacidades.lecturas_imprenta import _h_ordenes_de_compra

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "compras", "ver")
    return _h_ordenes_de_compra({"estado": _texto(estado, 20), "proveedor": _texto(proveedor, 80),
                                 "limite": limite}, usuario)


def mi_recibo(fecha: str = "") -> dict[str, Any]:
    """El recibo de nómina de quien opera la conexión (sólo quincenas cerradas)."""
    from capacidades.lecturas_nomina import _h_mi_recibo

    usuario = _usuario_actual()
    return _h_mi_recibo({"fecha": _texto(fecha, 10)}, usuario)


def historial_de_actividad(persona: str = "", fecha: str = "") -> dict[str, Any]:
    """Qué hizo alguien en un día (pantallas, cambios guardados, entradas y salidas,
    tiempo activo). Sin persona es el de quien opera la conexión; el de otro pide
    `equipo.ver_historial`, que se re-chequea dentro."""
    from capacidades.lecturas import _h_historial_de_actividad

    usuario = _usuario_actual()
    return _h_historial_de_actividad(
        {"persona": _texto(persona, 120), "fecha": _texto(fecha, 10)}, usuario,
    )
