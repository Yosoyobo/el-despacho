"""Parser de DOC_05 → Novedades (changelog) + Manual (S-Chalanes-UX #5).

El manual de usuario `docs/DOC_05_MANUAL_USUARIO.md` arranca con bloques
`## Novedades …` (changelog para el usuario) y, a partir de `## Bienvenida`,
el manual propiamente dicho.

Este módulo separa ambas partes:
  - `novedades()` → lista de {clave, titulo, html}, más reciente primero.
    `clave` = slug estable del encabezado → identifica el bloque para el
    contador "no vistas" por usuario y la notificación masiva.
  - `manual()` → {html, toc} sólo del manual (sin el changelog).

Cachea por mtime del archivo. Defensivo: si el archivo no existe, devuelve
estructuras vacías (la UI degrada con gracia).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils.text import slugify

_MARCA_MANUAL = "## Bienvenida"
_CACHE: dict[str, Any] = {"mtime": None, "data": None}


def _ruta() -> Path:
    candidatos = []
    base = getattr(settings, "BASE_DIR", None)
    if base:
        candidatos.append(Path(base).parent / "docs" / "DOC_05_MANUAL_USUARIO.md")
    candidatos.append(Path("/app/docs/DOC_05_MANUAL_USUARIO.md"))
    aqui = Path(__file__).resolve()
    for i in range(1, 7):
        try:
            candidatos.append(aqui.parents[i] / "docs" / "DOC_05_MANUAL_USUARIO.md")
        except IndexError:
            break
    for p in candidatos:
        if p.exists():
            return p
    return candidatos[0] if candidatos else Path("/tmp/manual.md")


def _md(texto: str):
    import markdown
    m = markdown.Markdown(extensions=["fenced_code", "tables", "toc"],
                          extension_configs={"toc": {"permalink": False}})
    html = m.convert(texto)
    return html, getattr(m, "toc", "")


def _parse() -> dict:
    ruta = _ruta()
    if not ruta.exists():
        return {"novedades": [], "manual_html": "", "manual_toc": ""}
    mtime = ruta.stat().st_mtime
    if _CACHE["mtime"] == mtime and _CACHE["data"] is not None:
        return _CACHE["data"]

    texto = ruta.read_text(encoding="utf-8")
    idx = texto.find(_MARCA_MANUAL)
    if idx == -1:
        cabecera, manual_md = texto, ""
    else:
        cabecera, manual_md = texto[:idx], texto[idx:]

    # Partir la cabecera en bloques por encabezado `## ` (cada Novedad).
    novedades = []
    # Capturamos cada `## titulo\n…` hasta el siguiente `## ` o el fin.
    patron = re.compile(r"^##\s+(.*?)\s*$", re.MULTILINE)
    matches = list(patron.finditer(cabecera))
    vistos_claves = set()
    for i, m in enumerate(matches):
        titulo = m.group(1).strip()
        if not titulo.lower().startswith("novedad"):
            continue
        # Cuerpo SIN la línea del encabezado (el título ya se muestra aparte).
        cuerpo_inicio = m.end()
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(cabecera)
        bloque_md = cabecera[cuerpo_inicio:fin].strip()
        html, _ = _md(bloque_md)
        clave = slugify(titulo)[:80] or f"novedad-{i}"
        # Desambiguar claves repetidas (encabezados idénticos).
        base = clave
        n = 2
        while clave in vistos_claves:
            clave = f"{base}-{n}"
            n += 1
        vistos_claves.add(clave)
        novedades.append({"clave": clave, "titulo": titulo, "html": html})

    manual_html, manual_toc = _md(manual_md) if manual_md else ("", "")
    data = {"novedades": novedades, "manual_html": manual_html, "manual_toc": manual_toc}
    _CACHE.update({"mtime": mtime, "data": data})
    return data


def invalidar_cache() -> None:
    _CACHE["mtime"] = None


def novedades() -> list[dict]:
    return _parse()["novedades"]


def claves_actuales() -> list[str]:
    return [n["clave"] for n in _parse()["novedades"]]


def manual() -> dict:
    d = _parse()
    return {"html": d["manual_html"], "toc": d["manual_toc"]}


def no_vistas_para(usuario) -> int:
    """Cuántas novedades NO ha visto el usuario (para el badge del sidebar)."""
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return 0
    try:
        from cuentas.models import LecturaNovedades
        actuales = set(claves_actuales())
        if not actuales:
            return 0
        fila = LecturaNovedades.objects.filter(usuario=usuario).first()
        vistas = set(fila.claves_vistas) if fila else set()
        return len(actuales - vistas)
    except Exception:  # noqa: BLE001 — el badge nunca debe tumbar la página
        return 0


def marcar_todas_vistas(usuario) -> None:
    """Marca todas las novedades actuales como vistas por el usuario."""
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return
    from cuentas.models import LecturaNovedades
    fila, _ = LecturaNovedades.objects.get_or_create(usuario=usuario)
    fila.claves_vistas = claves_actuales()
    fila.save(update_fields=["claves_vistas", "actualizado_en"])
