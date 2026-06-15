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
    ICONOS_CARPETA,
    ICONOS_CARPETA_CLAVES,
    SLUGS_SIDEBAR_TALLER,
    SidebarCarpetaUsuario,
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
    # V11: icono guardado por carpeta (nombre → clave). Default "folder".
    iconos_guardados = {
        c.nombre: c.icono for c in SidebarCarpetaUsuario.objects.filter(usuario=request.user)
    }
    # V11 (decisión Oscar: "las carpetas deben poder intercalarse entre las
    # opciones fuera de una carpeta"). Construimos UNA secuencia ordenada donde
    # cada elemento es un item suelto O una carpeta (con sus items). La carpeta
    # se coloca en la posición de su PRIMER item (menor orden), así puede quedar
    # entre dos items de nivel superior.
    elementos: list[dict] = []
    carpetas_por_nombre: dict[str, dict] = {}
    for it in items:
        g = it["grupo"]
        if not g:
            elementos.append({"tipo": "item", "item": it})
        else:
            carpeta = carpetas_por_nombre.get(g)
            if carpeta is None:
                carpeta = {"tipo": "carpeta", "grupo": g,
                           "icono": iconos_guardados.get(g, "folder"), "items": []}
                carpetas_por_nombre[g] = carpeta
                elementos.append(carpeta)
            carpeta["items"].append(it)
    tiene_personal = SidebarOrdenUsuario.objects.filter(usuario=request.user).exists()
    return render(request, "taller_home/sidebar_preferencias.html", {
        "items": items,
        "elementos": elementos,
        "tiene_personal": tiene_personal,
        "grupos_existentes": sorted(grupos_existentes),
        "iconos_carpeta": ICONOS_CARPETA,
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
    # V11: icono por carpeta. Llegan dos arrays paralelos (nombre ↔ icono).
    # Reescribimos las filas del usuario para dejar SOLO las carpetas actuales.
    nombres = request.POST.getlist("carpeta_nombre")
    iconos = request.POST.getlist("carpeta_icono")
    SidebarCarpetaUsuario.objects.filter(usuario=request.user).delete()
    vistos = set()
    for nombre, icono in zip(nombres, iconos, strict=False):
        nombre = (nombre or "").strip()[:40]
        icono = icono if icono in ICONOS_CARPETA_CLAVES else "folder"
        if nombre and nombre not in vistos:
            vistos.add(nombre)
            SidebarCarpetaUsuario.objects.create(
                usuario=request.user, nombre=nombre, icono=icono)
    messages.success(request, "Tu menú quedó acomodado a tu gusto.")
    return redirect("perfil-sidebar")


@login_required
@require_http_methods(["POST"])
def sidebar_restablecer(request):
    SidebarOrdenUsuario.objects.filter(usuario=request.user).delete()
    SidebarCarpetaUsuario.objects.filter(usuario=request.user).delete()
    messages.success(request, "Tu menú volvió al orden por defecto.")
    return redirect("perfil-sidebar")
