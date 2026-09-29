"""La Gerencia → Ajustes → KPIs → Constructor (S-KPIs-V2 · 2, 2026-09-29).

Decisión de Oscar: «catálogo + constructor». Un formulario para crear KPIs sin
programar: qué contar o sumar, con qué filtros, en qué periodo, agrupado por
persona/cliente/…, como porcentaje de un total o comparado con el periodo
anterior. Se arma sobre el DSL v2 (`lib/kpi_dsl`): el formulario sale de
`esquema_para_ui()`, la vista previa de `ejecutar_con_preview()` y la frase de
`describir()`. Nada llega al ORM sin pasar por la whitelist del DSL.

El Chalán puede **llenar el formulario** a partir de una frase
(`services_kpi_chalan.nl_a_dsl`), pero lo que se guarda es lo que dice el
formulario. Un KPI hecho aquí nace **de equipo y activo** (quien tiene
`kpis.configurar` es quien aprueba los que se proponen desde El Taller) y sólo
lo ve quien tiene el permiso de su dato (`kpi_dsl.permisos_de`).
"""

from __future__ import annotations

import contextlib
import json

from django.contrib import messages
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from lib.permisos import requiere_permiso
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .views_kpis import TABS, etiqueta_permisos


def _emitir(tipo: str, request, payload: dict):
    with contextlib.suppress(Exception):
        emitir(EventoPortavoz(tipo=tipo, actor_id=request.user.pk,
                              actor_email=request.user.email, payload=payload))


def _categorias() -> list[tuple[str, str]]:
    from apps.taller_home.kpis import CATEGORIAS

    return [("custom", "🛠 Hechos en el constructor"), *CATEGORIAS]


@requiere_permiso("kpis", "configurar")
def lista(request):
    from apps.taller_home.models import KPICustom

    from lib.kpi_dsl import describir, validar

    filas = []
    for k in KPICustom.objects.select_related("autor").order_by("estado", "-actualizado_en"):
        try:
            frase = describir(validar(dict(k.definicion_json or {})))
        except Exception:  # noqa: BLE001 — una definición vieja rota no tumba la lista
            frase = "La definición ya no es válida: ábrela y corrígela."
        filas.append({"k": k, "frase": frase})
    return render(request, "ajustes/kpis/constructor_lista.html", {
        "tabs": TABS, "activo": "constructor", "filas": filas,
    })


def _contexto_formulario(request, kpi_db=None) -> dict:
    from lib.kpi_dsl import esquema_para_ui

    return {
        "tabs": TABS, "activo": "constructor", "kpi_db": kpi_db,
        "esquema": esquema_para_ui(request.user),
        "definicion": (kpi_db.definicion_json if kpi_db else None),
        "categorias": _categorias(),
    }


@requiere_permiso("kpis", "configurar")
def nuevo(request):
    return render(request, "ajustes/kpis/constructor_form.html", _contexto_formulario(request))


@requiere_permiso("kpis", "configurar")
def editar(request, pk: int):
    from apps.taller_home.models import KPICustom

    kpi_db = get_object_or_404(KPICustom, pk=pk)
    return render(request, "ajustes/kpis/constructor_form.html", _contexto_formulario(request, kpi_db))


def _leer_definicion(request) -> dict | None:
    try:
        definicion = json.loads(request.POST.get("definicion_json") or "{}")
    except json.JSONDecodeError:
        return None
    return definicion if isinstance(definicion, dict) else None


@requiere_permiso("kpis", "configurar")
@require_http_methods(["POST"])
def vista_previa(request):
    """El número de verdad con los datos de hoy, la frase y quién lo verá."""
    from apps.taller_home.kpi_valor import formatear, numero_de

    from lib.kpi_dsl import ejecutar_con_preview

    definicion = _leer_definicion(request)
    if not definicion or not definicion.get("entidad"):
        return render(request, "ajustes/kpis/_constructor_preview.html",
                      {"vacio": True})
    r = ejecutar_con_preview(definicion, usuario=request.user)
    if not r["ok"]:
        return render(request, "ajustes/kpis/_constructor_preview.html", {"error": r["error"]})
    res = r["resultado"]
    formato = res.get("formato") or "numero"
    grupos = [
        {**g, "valor_txt": formatear(numero_de(g.get("valor")), formato)}
        for g in res.get("grupos") or []
    ]
    comparacion = res.get("comparacion") or None
    if comparacion:
        comparacion = {**comparacion,
                       "anterior_txt": formatear(numero_de(comparacion.get("anterior")), formato)}
    return render(request, "ajustes/kpis/_constructor_preview.html", {
        "valor_txt": formatear(numero_de(res.get("valor")), formato),
        "nota": res.get("nota") or "",
        "descripcion": r["descripcion"],
        "permisos": etiqueta_permisos(tuple(r["permisos"])),
        "grupos": grupos, "comparacion": comparacion,
        "direccion": res.get("direccion"),
        "sin_permiso": res.get("sin_permiso"),
    })


@requiere_permiso("kpis", "configurar")
@require_http_methods(["POST"])
def con_chalan(request):
    """Traduce una frase a una definición para llenar el formulario."""
    from apps.taller_home.services_kpi_chalan import nl_a_dsl

    from lib.sanear import sanear_contexto

    texto = (request.POST.get("texto") or "").strip()[:600]
    if not texto:
        return JsonResponse({"ok": False, "error": "Escribe qué quieres medir."}, status=400)
    texto = sanear_contexto(texto)   # §4 #13: input libre antes de la IA
    r = nl_a_dsl(texto=texto, usuario=request.user)
    if not r.get("ok"):
        return JsonResponse({"ok": False, "error": r.get("error") or "El Chalán no pudo."})
    return JsonResponse({"ok": True, "definicion": r["definicion"],
                         "titulo": r.get("titulo_sugerido") or ""})


@requiere_permiso("kpis", "configurar")
@require_http_methods(["POST"])
def guardar(request, pk: int | None = None):
    from apps.taller_home.models import KPICustom

    from lib.kpi_dsl import ValidacionError, validar

    kpi_db = get_object_or_404(KPICustom, pk=pk) if pk else None
    titulo = (request.POST.get("titulo") or "").strip()[:100]
    descripcion = (request.POST.get("descripcion") or "").strip()
    categorias = dict(_categorias())
    categoria = (request.POST.get("categoria") or "custom").strip()
    if categoria not in categorias:
        categoria = "custom"
    definicion = _leer_definicion(request)
    volver = f"/ajustes/kpis/constructor/{kpi_db.pk}/" if kpi_db else "/ajustes/kpis/constructor/nuevo/"
    if not titulo:
        messages.error(request, "Pon un nombre al KPI.")
        return redirect(volver)
    try:
        normalizada = validar(definicion or {})
    except ValidacionError as exc:
        messages.error(request, f"La definición no es válida: {exc}")
        return redirect(volver)

    ahora = timezone.now()
    if kpi_db is None:
        base = slugify(titulo)[:60] or "kpi"
        slug, n = base, 2
        while KPICustom.objects.filter(slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        kpi_db = KPICustom(slug=slug, autor=request.user)
    kpi_db.titulo = titulo
    kpi_db.descripcion = descripcion
    kpi_db.categoria = categoria
    kpi_db.definicion_json = normalizada
    # Hecho o corregido aquí = de equipo y aprobado por quien configura KPIs.
    kpi_db.alcance = "equipo"
    kpi_db.estado = "activo"
    kpi_db.aprobado_por = request.user
    kpi_db.aprobado_en = ahora
    kpi_db.motivo_rechazo = ""
    creado = kpi_db.pk is None
    kpi_db.save()
    _emitir("kpi_custom.creado" if creado else "kpi.configuracion_actualizada", request,
            {"kpi_id": kpi_db.pk, "slug": kpi_db.slug, "que": "constructor", "alcance": "equipo",
             "estado": "activo"})
    messages.success(
        request,
        f"«{titulo}» {'creado' if creado else 'guardado'}. Ya aparece en el catálogo: agrégalo "
        "al tablero de un rol o ponle una meta.",
    )
    return redirect("ajustes-kpis-constructor")


@requiere_permiso("kpis", "configurar")
@require_http_methods(["POST"])
def cambiar_estado(request, pk: int):
    """Archivar o reactivar (los pendientes se aprueban aquí también)."""
    from apps.taller_home.models import KPICustom

    kpi_db = get_object_or_404(KPICustom, pk=pk)
    accion = request.POST.get("accion")
    if accion == "archivar":
        kpi_db.estado = "archivado"
    elif accion in ("reactivar", "aprobar"):
        kpi_db.estado = "activo"
        kpi_db.aprobado_por = request.user
        kpi_db.aprobado_en = timezone.now()
    elif accion == "rechazar":
        kpi_db.estado = "rechazado"
        kpi_db.motivo_rechazo = (request.POST.get("motivo") or "").strip()[:300]
    else:
        return HttpResponseBadRequest("Acción inválida.")
    kpi_db.save()
    _emitir("kpi.configuracion_actualizada", request,
            {"kpi_id": kpi_db.pk, "slug": kpi_db.slug, "que": "constructor", "estado": kpi_db.estado})
    messages.success(request, f"«{kpi_db.titulo}»: {kpi_db.get_estado_display().lower()}.")
    return redirect("ajustes-kpis-constructor")

