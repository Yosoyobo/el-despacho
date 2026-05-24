"""Resolver tokens → entidades de DB.

`resolver_tokens(tokens)` recibe la salida del parser y devuelve un dict
slug → instancia (o None si no se encontró / está inactiva pero igual referenciada).

Política:
- Usuario inactivo (is_active=False) sigue siendo referenciable — pero el render
  lo muestra como "roto" (line-through).
- Cliente con activo=False idem.
- Proyecto con estado cancelado idem.
- Slug no encontrado → entrada con valor None (referencia rota literal).
"""

from __future__ import annotations

from .parser import TokenRef


def resolver_tokens(tokens: list[TokenRef]) -> dict[tuple[str, str], object | None]:
    """Devuelve mapa {(tipo, slug): instancia | None}. Una sola query por tipo."""
    if not tokens:
        return {}

    slugs_por_tipo: dict[str, set[str]] = {"usuario": set(), "proyecto": set(), "cliente": set()}
    for t in tokens:
        slugs_por_tipo[t.tipo].add(t.slug)

    resuelto: dict[tuple[str, str], object | None] = {}

    if slugs_por_tipo["usuario"]:
        from cuentas.models.usuario import Usuario
        for u in Usuario.objects.filter(slug__in=slugs_por_tipo["usuario"]):
            resuelto[("usuario", u.slug)] = u
        for s in slugs_por_tipo["usuario"]:
            resuelto.setdefault(("usuario", s), None)

    if slugs_por_tipo["proyecto"]:
        # S-LC-Feedback-V5 c9: el slug puede venir del campo actual
        # (basado en nombre) o del slug_legacy (basado en código LC-NNNN
        # en mensajes históricos). Resolver consulta ambos.
        from apps.los_proyectos.models.proyecto import Proyecto
        from django.db.models import Q
        slugs = slugs_por_tipo["proyecto"]
        for p in Proyecto.objects.filter(Q(slug__in=slugs) | Q(slug_legacy__in=slugs)):
            if p.slug in slugs:
                resuelto[("proyecto", p.slug)] = p
            if p.slug_legacy and p.slug_legacy in slugs:
                resuelto[("proyecto", p.slug_legacy)] = p
        for s in slugs:
            resuelto.setdefault(("proyecto", s), None)

    if slugs_por_tipo["cliente"]:
        from apps.la_cartera.models.cliente import Cliente
        # objects (no `activos`) — clientes archivados siguen siendo referenciables.
        for c in Cliente.objects.filter(slug__in=slugs_por_tipo["cliente"]):
            resuelto[("cliente", c.slug)] = c
        for s in slugs_por_tipo["cliente"]:
            resuelto.setdefault(("cliente", s), None)

    return resuelto
