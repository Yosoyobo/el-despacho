"""Lógica de las herramientas MCP, separada del transporte.

Todas las consultas son de sólo lectura y fallan cerradas si falta identidad,
si el usuario está inactivo o si no tiene los dos permisos requeridos:
`mcp.usar` y el permiso propio del módulo consultado.
"""

from __future__ import annotations

import os
from typing import Any

from django.db.models import Q, QuerySet

from lib.permisos import puede, roles_efectivos, tiene_rol

ENV_USUARIO = "DESPACHO_MCP_USUARIO_EMAIL"
LIMITE_MAXIMO = 100


class ErrorAccesoMCP(PermissionError):
    """Error seguro y legible para clientes MCP."""


def _limite(valor: int) -> int:
    return max(1, min(int(valor), LIMITE_MAXIMO))


def _texto(valor: str, maximo: int = 200) -> str:
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


def _proyectos_visibles(usuario) -> QuerySet:
    from apps.los_proyectos.models import Proyecto

    qs = Proyecto.objects.select_related("cliente")
    if roles_efectivos(usuario) & {"super_admin", "dueno", "contador"}:
        return qs
    return qs.filter(asignaciones__usuario=usuario).distinct()


def _tareas_visibles(usuario) -> QuerySet:
    from apps.el_pizarron.models import Tarea

    qs = Tarea.objects.select_related(
        "proyecto", "proyecto__cliente", "asignada_a", "runner"
    )
    if roles_efectivos(usuario) & {"super_admin", "dueno", "contador"}:
        return qs
    return qs.filter(
        Q(asignada_a=usuario)
        | Q(responsables=usuario)
        | Q(runner=usuario)
        | Q(proyecto__asignaciones__usuario=usuario)
    ).distinct()


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
    from apps.la_cartera.models import Cliente

    usuario = _usuario_actual()
    _exigir_permiso(usuario, "cartera", "ver")
    q = _texto(consulta)
    qs = Cliente.objects.all() if incluir_archivados else Cliente.activos.all()
    if q:
        qs = qs.filter(
            Q(razon_social__icontains=q)
            | Q(rfc__icontains=q)
            | Q(nombre_contacto__icontains=q)
            | Q(email_contacto__icontains=q)
        )
    filas = list(qs.order_by("razon_social")[: _limite(limite)])
    return {
        "resultados": [
            {
                "id": cliente.pk,
                "referencia": f"${cliente.slug}",
                "razon_social": cliente.razon_social,
                "estado": cliente.estado,
                "activo": cliente.activo,
                "contacto": cliente.nombre_contacto,
            }
            for cliente in filas
        ],
        "cantidad": len(filas),
    }


def buscar_proyectos(
    consulta: str = "",
    estado: str = "",
    incluir_archivados: bool = False,
    limite: int = 20,
) -> dict[str, Any]:
    """Lista proyectos visibles, filtrables por texto y estado."""
    usuario = _usuario_actual()
    _exigir_permiso(usuario, "proyectos", "ver")
    q = _texto(consulta)
    estado = _texto(estado, 32)
    qs = _proyectos_visibles(usuario)
    qs = qs if incluir_archivados else qs.filter(archivado=False)
    if q:
        qs = qs.filter(
            Q(codigo__icontains=q)
            | Q(nombre__icontains=q)
            | Q(cliente__razon_social__icontains=q)
        )
    if estado:
        qs = qs.filter(estado=estado)
    filas = list(qs.order_by("-actualizado_en")[: _limite(limite)])
    return {
        "resultados": [
            {
                "id": proyecto.pk,
                "codigo": proyecto.codigo,
                "referencia": f"#{proyecto.slug}",
                "nombre": proyecto.nombre,
                "cliente": proyecto.cliente.razon_social,
                "estado": proyecto.estado,
                "fecha_compromiso": (
                    proyecto.fecha_compromiso.isoformat()
                    if proyecto.fecha_compromiso
                    else None
                ),
                "archivado": proyecto.archivado,
            }
            for proyecto in filas
        ],
        "cantidad": len(filas),
    }


def obtener_proyecto(referencia: str) -> dict[str, Any]:
    """Obtiene el detalle de un proyecto por ID, código, slug o #referencia."""
    usuario = _usuario_actual()
    _exigir_permiso(usuario, "proyectos", "ver")
    valor = _texto(referencia).lstrip("#")
    filtro = Q(codigo__iexact=valor) | Q(slug__iexact=valor) | Q(slug_legacy__iexact=valor)
    if valor.isdigit():
        filtro |= Q(pk=int(valor))
    proyecto = (
        _proyectos_visibles(usuario)
        .filter(filtro)
        .prefetch_related("asignaciones__usuario")
        .first()
    )
    if proyecto is None:
        raise ErrorAccesoMCP("Proyecto inexistente o no visible para este usuario.")

    datos: dict[str, Any] = {
        "id": proyecto.pk,
        "codigo": proyecto.codigo,
        "referencia": f"#{proyecto.slug}",
        "nombre": proyecto.nombre,
        "cliente": proyecto.cliente.razon_social,
        "descripcion": proyecto.descripcion,
        "estado": proyecto.estado,
        "regimen_fiscal": proyecto.regimen_fiscal,
        "fecha_inicio": proyecto.fecha_inicio.isoformat() if proyecto.fecha_inicio else None,
        "fecha_compromiso": (
            proyecto.fecha_compromiso.isoformat() if proyecto.fecha_compromiso else None
        ),
        "archivado": proyecto.archivado,
        "equipo": [
            {
                "nombre": asignacion.usuario.nombre_completo,
                "rol": asignacion.rol_en_proyecto,
            }
            for asignacion in proyecto.asignaciones.all()
        ],
        "tareas": {
            "total": proyecto.tareas.count(),
            "abiertas": proyecto.tareas.exclude(estado="completada").count(),
        },
    }
    if tiene_rol(usuario, "super_admin") or puede(usuario, "tesoreria", "ver"):
        datos["finanzas"] = {
            "monto_estimado": str(proyecto.monto_estimado) if proyecto.monto_estimado else None,
            "monto_cotizado": str(proyecto.monto_cotizado) if proyecto.monto_cotizado else None,
            "monto_facturado": str(proyecto.monto_facturado),
            "monto_cobrado": str(proyecto.monto_cobrado),
        }
    return datos


def listar_tareas(
    consulta: str = "",
    estado: str = "",
    proyecto: str = "",
    incluir_archivadas: bool = False,
    limite: int = 30,
) -> dict[str, Any]:
    """Lista tareas visibles por texto, estado y proyecto."""
    usuario = _usuario_actual()
    _exigir_permiso(usuario, "pizarron", "ver")
    q = _texto(consulta)
    estado = _texto(estado, 32)
    proyecto = _texto(proyecto).lstrip("#")
    qs = _tareas_visibles(usuario)
    qs = qs if incluir_archivadas else qs.filter(archivada=False)
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(descripcion__icontains=q))
    if estado:
        qs = qs.filter(estado=estado)
    if proyecto:
        filtro_proyecto = (
            Q(proyecto__codigo__iexact=proyecto)
            | Q(proyecto__slug__iexact=proyecto)
            | Q(proyecto__slug_legacy__iexact=proyecto)
        )
        if proyecto.isdigit():
            filtro_proyecto |= Q(proyecto_id=int(proyecto))
        qs = qs.filter(filtro_proyecto)
    filas = list(qs.order_by("fecha_compromiso", "-creado_en")[: _limite(limite)])
    return {
        "resultados": [
            {
                "id": tarea.pk,
                "titulo": tarea.titulo,
                "estado": tarea.estado,
                "prioridad": tarea.prioridad,
                "tipo": tarea.tipo,
                "proyecto": tarea.proyecto.codigo,
                "referencia_proyecto": f"#{tarea.proyecto.slug}",
                "cliente": tarea.proyecto.cliente.razon_social,
                "asignada_a": tarea.asignada_a.nombre_completo if tarea.asignada_a else None,
                "fecha_compromiso": (
                    tarea.fecha_compromiso.isoformat() if tarea.fecha_compromiso else None
                ),
                "hora": tarea.hora.isoformat() if tarea.hora else None,
                "atrasada": tarea.esta_atrasada,
            }
            for tarea in filas
        ],
        "cantidad": len(filas),
    }
