"""Context processor del Buzón — badge de no leídos por usuario (S-Chalanes-UX #3)."""

from __future__ import annotations


def buzon_no_leidos(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"buzon_no_leidos_count": 0}
    try:
        from buzon.lecturas import contar_no_leidos
        from buzon.models import MensajeBuzon
        from lib.permisos import puede
        base = (MensajeBuzon.objects.all() if puede(user, "buzon", "ver_todos")
                else MensajeBuzon.objects.filter(autor=user))
        return {"buzon_no_leidos_count": contar_no_leidos(user, base)}
    except Exception:  # noqa: BLE001
        return {"buzon_no_leidos_count": 0}
