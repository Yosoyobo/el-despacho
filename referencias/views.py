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
    """Todos los roles pueden ver `@usuario`. Excluye inactivos.

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
    """Diseñador sólo ve proyectos donde está asignado.

    Sin prefijo retorna top 8 alfabético (UX Slack-style).
    """
    q = (request.GET.get("q") or "").strip().lower()
    user = request.user
    from apps.los_proyectos.models.proyecto import Proyecto
    base = Proyecto.objects.all()
    if getattr(user, "rol", None) == "disenador":
        base = base.filter(asignaciones__usuario_id=user.pk).distinct()
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
    """Diseñador NO ve clientes — lista vacía silenciosa (DOC_01 §4.4).

    Sin prefijo retorna top 8 alfabético (UX Slack-style).
    """
    q = (request.GET.get("q") or "").strip().lower()
    user = request.user
    if getattr(user, "rol", None) == "disenador":
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
    if getattr(request.user, "rol", None) == "disenador":
        return JsonResponse({"total": 0, "pagina": 1, "tam": 20, "items": []})
    return _busqueda_inversa(request, "cliente", cliente_id)
