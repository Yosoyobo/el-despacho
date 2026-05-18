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


@login_required
def autocomplete_usuarios(request):
    """Sólo prefijo. Todos los roles pueden ver `@usuario`. Excluye inactivos."""
    q = (request.GET.get("q") or "").strip().lower()
    if not q:
        return JsonResponse({"resultados": []})
    from cuentas.models.usuario import Usuario
    qs = Usuario.objects.filter(is_active=True).filter(
        Q(slug__istartswith=q)
        | Q(email__istartswith=q)
        | Q(nombre_completo__istartswith=q)
    ).order_by("slug")[:LIMITE_AUTOCOMPLETE]
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
    """Diseñador sólo ve proyectos donde está asignado."""
    q = (request.GET.get("q") or "").strip().lower()
    if not q:
        return JsonResponse({"resultados": []})
    user = request.user
    from apps.los_proyectos.models.proyecto import Proyecto
    qs = Proyecto.objects.filter(
        Q(slug__istartswith=q) | Q(codigo__istartswith=q.upper()) | Q(nombre__istartswith=q)
    )
    if getattr(user, "rol", None) == "disenador":
        qs = qs.filter(asignaciones__usuario_id=user.pk).distinct()
    qs = qs.order_by("-creado_en")[:LIMITE_AUTOCOMPLETE]
    return JsonResponse({"resultados": [
        {
            "slug": p.slug,
            "etiqueta": p.codigo,
            "secundario": p.nombre,
            "tipo": "proyecto",
            "sigil": "#",
        }
        for p in qs
    ]})


@login_required
def autocomplete_clientes(request):
    """Diseñador NO ve clientes — lista vacía silenciosa (DOC_01 §4.4)."""
    q = (request.GET.get("q") or "").strip().lower()
    if not q:
        return JsonResponse({"resultados": []})
    user = request.user
    if getattr(user, "rol", None) == "disenador":
        return JsonResponse({"resultados": []})
    from apps.la_cartera.models.cliente import Cliente
    qs = Cliente.objects.filter(activo=True).filter(
        Q(slug__istartswith=q) | Q(razon_social__istartswith=q)
    ).order_by("razon_social")[:LIMITE_AUTOCOMPLETE]
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
