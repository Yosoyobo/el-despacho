"""Páginas de Ayuda — Manual + Novedades (S-Chalanes-UX #5).

`docs/DOC_05_MANUAL_USUARIO.md` es la fuente única de verdad. Arranca con
bloques `## Novedades …` (changelog) y, desde `## Bienvenida`, el manual.
`lib.novedades` separa ambas partes.

- `/ayuda/`           → Manual (sin el changelog). TOC + cuerpo.
- `/ayuda/novedades/` → Novedades (changelog en acordeón). Al abrirla se
  marcan todas como vistas → limpia el badge contador del sidebar.

`?refresh=1` (super_admin) invalida el caché si editaste el .md sin reiniciar.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from lib import novedades as _nov
from lib.permisos import tiene_rol


def _ruta_manual() -> Path:
    candidatos = []
    base = getattr(settings, "BASE_DIR", None)
    if base:
        candidatos.append(Path(base).parent / "docs" / "DOC_05_MANUAL_USUARIO.md")
    candidatos.append(Path("/app/docs/DOC_05_MANUAL_USUARIO.md"))
    aqui = Path(__file__).resolve()
    for i in range(2, 7):
        try:
            candidatos.append(aqui.parents[i] / "docs" / "DOC_05_MANUAL_USUARIO.md")
        except IndexError:
            break
    for p in candidatos:
        if p.exists():
            return p
    return candidatos[0] if candidatos else Path("/tmp/manual.md")


def _quizas_refresca(request) -> None:
    # V6 Bloque 10: tiene_rol reconoce rol primario + roles personalizados.
    if request.GET.get("refresh") == "1" and tiene_rol(request.user, "super_admin", "dueno"):
        _nov.invalidar_cache()


@login_required
def ayuda(request):
    """GET /ayuda/ — sólo el manual (sin changelog)."""
    _quizas_refresca(request)
    data = _nov.manual()
    return render(request, "ayuda/manual.html", {
        "manual_html": data["html"],
        "manual_toc": data["toc"],
    })


@login_required
def novedades(request):
    """GET /ayuda/novedades/ — changelog. Abrirla marca todo como visto."""
    _quizas_refresca(request)
    items = _nov.novedades()
    _nov.marcar_todas_vistas(request.user)
    return render(request, "ayuda/novedades.html", {"novedades": items})


def ayuda_raw(request):
    """GET /ayuda/raw — sirve el .md como texto plano (para descargar)."""
    if not request.user.is_authenticated:
        return HttpResponse("Necesitas iniciar sesión.", status=403)
    ruta = _ruta_manual()
    if not ruta.exists():
        return HttpResponse("Manual no disponible.", status=404)
    return HttpResponse(ruta.read_text(encoding="utf-8"), content_type="text/markdown; charset=utf-8")
