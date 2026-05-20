"""S2b.5 — UI de KPIs custom generados por el Chalán.

Flujo:
1. Usuario abre `/kpis/custom/nuevo/` y describe el KPI en lenguaje natural.
2. POST `/kpis/custom/proponer` → Chalán traduce a DSL, retorna preview con
   definición validada + valor calculado.
3. POST `/kpis/custom/crear` → persiste KPICustom (estado=activo si personal,
   pendiente_aprobacion si alcance=equipo).
4. GET `/kpis/custom/` → lista personal (mis KPIs).
"""

from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from lib.kpi_dsl import ValidacionError, ejecutar_con_preview, validar

from .models import KPICustom
from .services_kpi_chalan import nl_a_dsl


@login_required
def lista(request):
    """Mis KPIs custom — personales y los del equipo donde soy autor."""
    user = request.user
    mios = list(KPICustom.objects.filter(autor=user).order_by("-creado_en")[:100])
    aprobados_equipo = list(
        KPICustom.objects.filter(alcance="equipo", estado="activo")
        .exclude(autor=user).order_by("-aprobado_en")[:30],
    )
    return render(request, "taller_home/kpi_custom_lista.html", {
        "mios": mios, "aprobados_equipo": aprobados_equipo,
    })


@login_required
def nuevo(request):
    """Formulario inicial — el usuario describe el KPI en NL."""
    return render(request, "taller_home/kpi_custom_nuevo.html", {})


@login_required
@require_http_methods(["POST"])
def proponer(request):
    """POST: NL → Chalán → DSL validado + preview. NO persiste todavía."""
    texto = (request.POST.get("texto") or "").strip()
    if not texto:
        messages.error(request, "Escribe la pregunta antes de enviarla al Chalán.")
        return redirect("kpi-custom-nuevo")
    res = nl_a_dsl(texto=texto, usuario=request.user)
    if not res.get("ok"):
        messages.error(request, res.get("error", "El Chalán no pudo traducir tu pregunta."))
        return render(request, "taller_home/kpi_custom_nuevo.html", {"texto_previo": texto})
    return render(request, "taller_home/kpi_custom_preview.html", {
        "texto": texto,
        "definicion_json": json.dumps(res["definicion"], indent=2, ensure_ascii=False),
        "definicion": res["definicion"],
        "titulo_sugerido": res["titulo_sugerido"],
        "categoria_sugerida": res["categoria_sugerida"],
        "preview": res["preview"],
    })


@login_required
@require_http_methods(["POST"])
def crear(request):
    """Persiste el KPICustom tras la confirmación del usuario."""
    titulo = (request.POST.get("titulo") or "").strip()[:100]
    descripcion = (request.POST.get("descripcion") or "").strip()
    categoria = (request.POST.get("categoria") or "custom").strip()[:30]
    alcance = (request.POST.get("alcance") or "personal").strip()
    if alcance not in ("personal", "equipo"):
        alcance = "personal"
    try:
        definicion = json.loads(request.POST.get("definicion_json") or "{}")
        normalizada = validar(definicion)
    except (json.JSONDecodeError, ValidacionError) as exc:
        messages.error(request, f"La definición no es válida: {exc}")
        return redirect("kpi-custom-nuevo")
    if not titulo:
        messages.error(request, "Pon un título al KPI.")
        return redirect("kpi-custom-nuevo")

    slug_base = slugify(titulo)[:60] or "kpi"
    slug = slug_base
    n = 2
    while KPICustom.objects.filter(slug=slug).exists():
        slug = f"{slug_base}-{n}"
        n += 1

    estado = "activo" if alcance == "personal" else "pendiente_aprobacion"
    with transaction.atomic():
        kpi = KPICustom.objects.create(
            slug=slug, titulo=titulo, descripcion=descripcion, categoria=categoria,
            definicion_json=normalizada, alcance=alcance, estado=estado, autor=request.user,
        )
    _emitir("kpi_custom.creado", request.user, {
        "kpi_id": kpi.pk, "slug": kpi.slug, "alcance": alcance, "estado": estado,
    })
    if estado == "pendiente_aprobacion":
        messages.success(
            request,
            "KPI creado. Como pediste alcance 'equipo', un super_admin debe aprobarlo antes de que aparezca para todos.",
        )
    else:
        messages.success(request, "KPI personal creado — ya aparece en tu Sala de Juntas.")
    return redirect("kpi-custom-lista")


@login_required
@require_http_methods(["POST"])
def archivar(request, pk: int):
    kpi = get_object_or_404(KPICustom, pk=pk, autor=request.user)
    kpi.estado = "archivado"
    kpi.save(update_fields=["estado"])
    _emitir("kpi_custom.archivado", request.user, {"kpi_id": kpi.pk})
    messages.success(request, "KPI archivado.")
    return redirect("kpi-custom-lista")


@login_required
def previsualizar(request, pk: int):
    """Re-ejecuta el KPI sobre datos actuales (debugging para el autor)."""
    kpi = get_object_or_404(KPICustom, pk=pk, autor=request.user)
    resultado = ejecutar_con_preview(kpi.definicion_json, usuario=request.user)
    return render(request, "taller_home/kpi_custom_detalle.html", {
        "kpi": kpi,
        "resultado": resultado,
        "definicion_json": json.dumps(kpi.definicion_json, indent=2, ensure_ascii=False),
    })


def _emitir(tipo, usuario, payload):
    import contextlib
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo=tipo,  # type: ignore[arg-type]
            actor_id=getattr(usuario, "pk", None),
            actor_email=getattr(usuario, "email", None),
            payload=payload,
        ))
