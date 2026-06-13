"""Personalización del sidebar POR USUARIO (S-LC-Feedback-V7).

Cada persona reordena y oculta sus propios items desde `/perfil/sidebar/`.
Guarda en `SidebarOrdenUsuario` (pisa el orden global del super_admin).
"Restablecer" borra las filas personales y vuelve al orden global.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from cuentas.models.sidebar_orden import (
    SLUGS_SIDEBAR_TALLER,
    SidebarOrden,
    SidebarOrdenUsuario,
)


def _orden_efectivo(user):
    """Mapa {slug: {orden, oculto, grupo}} efectivo: global pisado por el del usuario."""
    mapa = {f.slug: {"orden": f.orden, "oculto": f.oculto, "grupo": ""} for f in SidebarOrden.objects.all()}
    for f in SidebarOrdenUsuario.objects.filter(usuario=user):
        mapa[f.slug] = {"orden": f.orden, "oculto": f.oculto, "grupo": f.grupo}
    return mapa


@login_required
def sidebar_preferencias(request):
    efectivo = _orden_efectivo(request.user)
    items = []
    grupos_existentes = set()
    for i, (slug, label) in enumerate(SLUGS_SIDEBAR_TALLER):
        fila = efectivo.get(slug)
        grupo = (fila.get("grupo") if fila else "") or ""
        if grupo:
            grupos_existentes.add(grupo)
        items.append({
            "slug": slug,
            "label": label,
            "orden": fila["orden"] if fila else (i + 1) * 10,
            "oculto": fila["oculto"] if fila else False,
            "grupo": grupo,
        })
    items.sort(key=lambda x: (x["orden"], x["slug"]))
    tiene_personal = SidebarOrdenUsuario.objects.filter(usuario=request.user).exists()
    return render(request, "taller_home/sidebar_preferencias.html", {
        "items": items,
        "tiene_personal": tiene_personal,
        "grupos_existentes": sorted(grupos_existentes),
    })


@login_required
@require_http_methods(["POST"])
def sidebar_guardar(request):
    slugs_validos = {s for s, _ in SLUGS_SIDEBAR_TALLER}
    for slug in slugs_validos:
        orden_raw = (request.POST.get(f"orden__{slug}") or "").strip()
        oculto = request.POST.get(f"oculto__{slug}") == "1"
        # V9: carpeta/grupo (texto libre, opcional). Vacío = item suelto.
        grupo = (request.POST.get(f"grupo__{slug}") or "").strip()[:40]
        try:
            orden = int(orden_raw)
        except (TypeError, ValueError):
            continue
        SidebarOrdenUsuario.objects.update_or_create(
            usuario=request.user, slug=slug,
            defaults={"orden": orden, "oculto": oculto, "grupo": grupo},
        )
    messages.success(request, "Tu menú quedó acomodado a tu gusto.")
    return redirect("perfil-sidebar")


@login_required
@require_http_methods(["POST"])
def sidebar_restablecer(request):
    SidebarOrdenUsuario.objects.filter(usuario=request.user).delete()
    messages.success(request, "Tu menú volvió al orden por defecto.")
    return redirect("perfil-sidebar")
