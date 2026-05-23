"""Página de Ayuda — renderiza docs/DOC_05_MANUAL_USUARIO.md.

Decisión S-LC-Feedback-V3: el manual de usuario es la fuente única de
verdad. Vive en `docs/DOC_05_MANUAL_USUARIO.md`, se actualiza ANTES de
cualquier deploy con los cambios del sprint, y esta vista lo renderiza
para usuarios no técnicos.

El render usa la lib `markdown` con extensiones para tabla de contenidos,
syntax highlight básico (fenced_code), tablas y referencias internas.
Cachea el HTML en memoria del proceso (lectura única por arranque) — si
cambias el .md y quieres ver el cambio sin reiniciar gunicorn, agrega
`?refresh=1` (sólo super_admin).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

# Cache simple en memoria del proceso. La key es la mtime del archivo.
_CACHE: dict[str, Any] = {"mtime": None, "html": None, "toc": None}


def _ruta_manual() -> Path:
    """Encuentra el manual: primero junto al BASE_DIR del project, luego
    en /app/docs (Docker), luego subiendo desde este archivo."""
    candidatos = []
    base = getattr(settings, "BASE_DIR", None)
    if base:
        candidatos.append(Path(base).parent / "docs" / "DOC_05_MANUAL_USUARIO.md")
    candidatos.append(Path("/app/docs/DOC_05_MANUAL_USUARIO.md"))
    # Buscar subiendo por parents (en dev local: parents[3] = root; en
    # Docker varía). Probamos varios niveles para robustez.
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


def _render_markdown() -> dict[str, str]:
    """Lee y convierte el manual. Cachea por mtime."""
    ruta = _ruta_manual()
    if not ruta.exists():
        return {
            "html": "<p>El manual de usuario no está disponible en este servidor.</p>",
            "toc": "",
        }
    mtime = ruta.stat().st_mtime
    if _CACHE["mtime"] == mtime and _CACHE["html"] is not None:
        return {"html": _CACHE["html"], "toc": _CACHE["toc"]}

    import markdown
    md = markdown.Markdown(extensions=[
        "fenced_code", "tables", "toc",
    ], extension_configs={
        "toc": {"permalink": False, "anchorlink": False},
    })
    contenido = ruta.read_text(encoding="utf-8")
    html = md.convert(contenido)
    toc = md.toc  # tabla de contenidos generada
    _CACHE.update({"mtime": mtime, "html": html, "toc": toc})
    return {"html": html, "toc": toc}


@login_required
def ayuda(request):
    """GET /ayuda/ — renderiza el manual de usuario."""
    # Si super_admin pasa ?refresh=1, invalida caché.
    if request.GET.get("refresh") == "1" and getattr(request.user, "rol", "") in ("super_admin", "dueno"):
        _CACHE["mtime"] = None
    data = _render_markdown()
    return render(request, "ayuda/manual.html", {
        "manual_html": data["html"],
        "manual_toc": data["toc"],
    })


def ayuda_raw(request):
    """GET /ayuda/raw — sirve el .md como texto plano (para descargar)."""
    if not request.user.is_authenticated:
        return HttpResponse("Necesitas iniciar sesión.", status=403)
    ruta = _ruta_manual()
    if not ruta.exists():
        return HttpResponse("Manual no disponible.", status=404)
    return HttpResponse(ruta.read_text(encoding="utf-8"), content_type="text/markdown; charset=utf-8")
