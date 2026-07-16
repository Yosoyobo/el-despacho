"""Lecturas del servidor MCP por stdio (S-Chalan-MCP-V1 commit 2).

Estas impls vivían duplicadas en `mcp_despacho/herramientas.py`. Ahora tienen un
único hogar aquí, dentro del paquete `capacidades`, con la firma estándar de una
capacidad `(args: dict, usuario) -> dict`. `mcp_despacho` queda como una fachada
delgada que resuelve la identidad (env `DESPACHO_MCP_USUARIO_EMAIL`), exige los
permisos del módulo (con semántica de excepción) y delega en estas funciones.

Diferencias con las lecturas del chat (`lecturas.py`): estas devuelven listas más
amplias (hasta `limite`, sin el recorte top-N del chat) y con la forma pensada
para un cliente MCP externo. Por eso son capacidades de superficie sólo-MCP y no
se listan al Chalán conversacional. El gating por módulo y la visibilidad por
objeto (asignaciones) se conservan intactos.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from lib.permisos import puede, roles_efectivos, tiene_rol

LIMITE_MAXIMO = 100

# Roles con visibilidad amplia (ven todos los proyectos/tareas, no sólo los suyos).
_ROLES_AMPLIOS = {"super_admin", "dueno", "contador"}


def _limite(valor) -> int:
    try:
        return max(1, min(int(valor), LIMITE_MAXIMO))
    except (TypeError, ValueError):
        return 20


def _texto(valor, maximo: int = 200) -> str:
    return (valor or "").strip()[:maximo]


def _proyectos_visibles(usuario) -> QuerySet:
    from apps.los_proyectos.models import Proyecto

    qs = Proyecto.objects.select_related("cliente")
    if roles_efectivos(usuario) & _ROLES_AMPLIOS:
        return qs
    return qs.filter(asignaciones__usuario=usuario).distinct()


def _tareas_visibles(usuario) -> QuerySet:
    from apps.el_pizarron.models import Tarea

    qs = Tarea.objects.select_related("proyecto", "proyecto__cliente", "asignada_a", "runner")
    if roles_efectivos(usuario) & _ROLES_AMPLIOS:
        return qs
    return qs.filter(
        Q(asignada_a=usuario)
        | Q(responsables=usuario)
        | Q(runner=usuario)
        | Q(proyecto__asignaciones__usuario=usuario)
    ).distinct()


def buscar_clientes_impl(args: dict, usuario) -> dict:
    from apps.la_cartera.models import Cliente

    q = _texto(args.get("consulta", ""))
    incluir = bool(args.get("incluir_archivados", False))
    limite = _limite(args.get("limite", 20))
    qs = Cliente.objects.all() if incluir else Cliente.activos.all()
    if q:
        qs = qs.filter(
            Q(razon_social__icontains=q)
            | Q(rfc__icontains=q)
            | Q(nombre_contacto__icontains=q)
            | Q(email_contacto__icontains=q)
        )
    filas = list(qs.order_by("razon_social")[:limite])
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


def buscar_proyectos_impl(args: dict, usuario) -> dict:
    q = _texto(args.get("consulta", ""))
    estado = _texto(args.get("estado", ""), 32)
    incluir = bool(args.get("incluir_archivados", False))
    limite = _limite(args.get("limite", 20))
    qs = _proyectos_visibles(usuario)
    qs = qs if incluir else qs.filter(archivado=False)
    if q:
        qs = qs.filter(
            Q(codigo__icontains=q) | Q(nombre__icontains=q) | Q(cliente__razon_social__icontains=q)
        )
    if estado:
        qs = qs.filter(estado=estado)
    filas = list(qs.order_by("-actualizado_en")[:limite])
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
                    proyecto.fecha_compromiso.isoformat() if proyecto.fecha_compromiso else None
                ),
                "archivado": proyecto.archivado,
            }
            for proyecto in filas
        ],
        "cantidad": len(filas),
    }


def obtener_proyecto_impl(args: dict, usuario) -> dict[str, Any]:
    """Devuelve el detalle o `{"error": "no_visible"}` si no existe/no es visible
    (la fachada MCP traduce ese error a `ErrorAccesoMCP`)."""
    valor = _texto(args.get("referencia", "")).lstrip("#")
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
        return {"error": "no_visible"}

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


def listar_tareas_impl(args: dict, usuario) -> dict:
    q = _texto(args.get("consulta", ""))
    estado = _texto(args.get("estado", ""), 32)
    proyecto = _texto(args.get("proyecto", "")).lstrip("#")
    incluir = bool(args.get("incluir_archivadas", False))
    limite = _limite(args.get("limite", 30))
    qs = _tareas_visibles(usuario)
    qs = qs if incluir else qs.filter(archivada=False)
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
    filas = list(qs.order_by("fecha_compromiso", "-creado_en")[:limite])
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
