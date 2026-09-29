"""Endpoints JSON del Sistema de Referencias.

- `/api/autocomplete/{usuarios,proyectos,clientes}?q=<prefijo>` — sugerencias
   para el dropdown del cliente (debounce, 8 resultados máx).
- `/api/referencias/{usuarios,proyectos,clientes}/<id>` — búsqueda inversa
   paginada de contenedores que mencionan a la entidad.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse

LIMITE_AUTOCOMPLETE = 8


def _aplicar_filtro_y_top(qs, q: str, campos: list[str]):
    """Aplica filtro `istartswith` sobre `campos` si `q` no es vacío, sino
    deja `qs` tal cual. Siempre ordena por `slug` y limita a `LIMITE_AUTOCOMPLETE`.

    UX Slack/Notion: `@` sin prefijo muestra el equipo completo (top 8);
    `@osc` filtra a quienes empiezan con "osc".
    """
    if q:
        cond = Q()
        for campo in campos:
            valor = q.upper() if campo == "codigo" else q
            cond |= Q(**{f"{campo}__istartswith": valor})
        qs = qs.filter(cond)
    return qs.order_by("slug")[:LIMITE_AUTOCOMPLETE]


@login_required
def autocomplete_usuarios(request):
    """`@usuario`: cualquiera con sesión ve al equipo activo. Excluye inactivos.

    No hay permiso de «ver personas» que gatear: mencionar a un compañero es
    para lo que existen los recados, las tareas y los comentarios, y ningún
    permiso del catálogo esconde quién está en el equipo (la bandeja de recados
    ya los lista a todos). Por eso esta puerta se quedó igual cuando las de
    clientes y proyectos pasaron a permisos (2026-09-28).

    Sin prefijo retorna top 8 alfabético (UX Slack-style).
    """
    q = (request.GET.get("q") or "").strip().lower()
    from cuentas.models.usuario import Usuario
    qs = _aplicar_filtro_y_top(
        Usuario.objects.filter(is_active=True),
        q,
        ["slug", "email", "nombre_completo"],
    )
    return JsonResponse({"resultados": [
        {
            "slug": u.slug,
            "etiqueta": u.nombre_completo,
            "secundario": u.email,
            "tipo": "usuario",
            "sigil": "@",
        }
        for u in qs
    ]})


@login_required
def autocomplete_proyectos(request):
    """`#proyecto`: sugiere sólo los proyectos que el usuario puede ver —todos con
    `proyectos.ver_todos`, sus asignados con `proyectos.ver`, ninguno sin los
    dos— igual que la lista de Proyectos (`puede_ver_proyecto`).

    Hasta 2026.09.05 leía el rol PRIMARIO: sólo el diseñador se acotaba a sus
    asignados y cualquier otro veía todos. Decisión de Oscar (2026-09-28): las
    sugerencias siguen a los permisos de ver.

    Sin prefijo retorna top 8 alfabético (UX Slack-style).
    """
    from lib.permisos import puede, puede_ver_todos_proyectos

    q = (request.GET.get("q") or "").strip().lower()
    user = request.user
    from apps.los_proyectos.models.proyecto import Proyecto
    # No referenciar proyectos cancelados ni cerrados (ya no son accionables).
    base = Proyecto.objects.exclude(estado__in=["cancelado", "cerrado"])
    if not puede_ver_todos_proyectos(user):
        if puede(user, "proyectos", "ver"):
            base = base.filter(asignaciones__usuario_id=user.pk).distinct()
        else:
            base = base.none()
    qs = _aplicar_filtro_y_top(base, q, ["slug", "codigo", "nombre"])
    return JsonResponse({"resultados": [
        {
            "slug": p.slug,
            "etiqueta": p.nombre,
            "secundario": p.codigo,
            "tipo": "proyecto",
            "sigil": "#",
        }
        for p in qs
    ]})


@login_required
def autocomplete_clientes(request):
    """`$cliente`: sólo para quien puede ver La Cartera (`cartera.ver`); a los
    demás, lista vacía silenciosa (DOC_01 §4.4).

    Hasta 2026.09.05 sólo se le negaba al rol PRIMARIO diseñador. Decisión de
    Oscar (2026-09-28): que decida el mismo permiso que abre Clientes — quien
    ahí recibe 403 tampoco ve clientes al autocompletar.

    Sin prefijo retorna top 8 alfabético (UX Slack-style).
    """
    from lib.permisos import puede_ver_cartera

    q = (request.GET.get("q") or "").strip().lower()
    if not puede_ver_cartera(request.user):
        return JsonResponse({"resultados": []})
    from apps.la_cartera.models.cliente import Cliente
    qs = _aplicar_filtro_y_top(
        Cliente.objects.filter(activo=True),
        q,
        ["slug", "razon_social"],
    )
    return JsonResponse({"resultados": [
        {
            "slug": c.slug,
            "etiqueta": c.razon_social,
            "secundario": c.rfc or "",
            "tipo": "cliente",
            "sigil": "$",
        }
        for c in qs
    ]})


# ── Búsqueda inversa ─────────────────────────────────────────────────────────


def _busqueda_inversa(request, tipo: str, entidad_id: int):
    from .models import Referencia
    pagina = max(1, int(request.GET.get("page") or 1))
    tam = 20
    qs = Referencia.objects.filter(tipo=tipo, **{f"{tipo}_id": entidad_id}).order_by("-creado_en")
    total = qs.count()
    items = qs[(pagina - 1) * tam : pagina * tam]
    return JsonResponse({
        "total": total,
        "pagina": pagina,
        "tam": tam,
        "items": [
            {
                "contenedor_tipo": r.contenedor_tipo,
                "contenedor_id": r.contenedor_id,
                "token": r.token_original,
                "creado_en": r.creado_en.isoformat(),
            }
            for r in items
        ],
    })


@login_required
def busqueda_inversa_usuarios(request, usuario_id: int):
    return _busqueda_inversa(request, "usuario", usuario_id)


@login_required
def busqueda_inversa_proyectos(request, proyecto_id: int):
    return _busqueda_inversa(request, "proyecto", proyecto_id)


@login_required
def busqueda_inversa_clientes(request, cliente_id: int):
    from lib.permisos import puede_ver_cartera

    # Mismo permiso que el autocompletar de clientes (antes: rol primario).
    if not puede_ver_cartera(request.user):
        return JsonResponse({"total": 0, "pagina": 1, "tam": 20, "items": []})
    return _busqueda_inversa(request, "cliente", cliente_id)
