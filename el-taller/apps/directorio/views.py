"""Directorio del equipo en El Taller (S-Directorio-V1) — READ-ONLY.

Cualquier usuario autenticado del Taller consulta la ficha de sus compañeros
(puesto, contacto, oficina, modalidad, horario). La edición vive en La
Gerencia (El Directorio). Los checkins/ponchado llegan con El Checador
(sprint aparte); aquí se muestran como "próximamente".
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from cuentas.models.usuario import Usuario


@login_required
def lista(request):
    q = (request.GET.get("q") or "").strip()
    incluir_inactivos = request.GET.get("inactivos") == "1"
    usuarios = Usuario.objects.all().order_by("nombre_completo")
    if not incluir_inactivos:
        usuarios = usuarios.filter(is_active=True)
    if q:
        usuarios = usuarios.filter(
            Q(nombre_completo__icontains=q) | Q(email__icontains=q)
            | Q(puesto__icontains=q) | Q(oficina__icontains=q)
        )
    return render(request, "directorio/lista.html", {
        "usuarios": usuarios,
        "q": q,
        "incluir_inactivos": incluir_inactivos,
        "total": usuarios.count(),
    })
