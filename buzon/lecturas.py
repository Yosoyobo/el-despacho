"""Helpers de lectura por usuario del Buzón (S-Chalanes-UX #3)."""

from __future__ import annotations

from django.db.models import Exists, OuterRef


def marcar_leido(usuario, mensaje) -> None:
    from buzon.models import LecturaBuzon
    LecturaBuzon.objects.get_or_create(usuario=usuario, mensaje=mensaje)


def marcar_no_leido(usuario, mensaje) -> None:
    from buzon.models import LecturaBuzon
    LecturaBuzon.objects.filter(usuario=usuario, mensaje=mensaje).delete()


def anotar_leido(qs, usuario):
    """Anota cada mensaje con `leido_para_mi` (bool) vía Exists subquery."""
    from buzon.models import LecturaBuzon
    sub = LecturaBuzon.objects.filter(usuario=usuario, mensaje=OuterRef("pk"))
    return qs.annotate(leido_para_mi=Exists(sub))


def contar_no_leidos(usuario, base_qs) -> int:
    """Cuántos mensajes de `base_qs` NO ha leído el usuario."""
    from buzon.models import LecturaBuzon
    leidos = LecturaBuzon.objects.filter(usuario=usuario).values_list("mensaje_id", flat=True)
    return base_qs.exclude(pk__in=leidos).count()
