"""Recorrer el árbol del repo sin salirse de él.

Los candados que barren «todas las plantillas» o «todos los .py» desde la RAÍZ
no pueden usar `RAIZ.rglob(...)` a secas: en la Mac el repo trae adentro cosas
que no son el repo —

- `.claude/worktrees/<rama>/`: copias ENTERAS del repo de otras sesiones. Un
  candado que cuenta copias («sólo hay una plantilla del PDF») ve cuatro y
  truena sólo en local; en el CI esa carpeta no existe.
- `.venv*/`, `node_modules/`: plantillas y código de terceros.
- `data/`: los datos de Postgres/Redis/medios del stack local (miles de
  archivos, algunos sin permiso de lectura).

`archivos_del_repo()` poda esas carpetas ANTES de entrar (no filtra después:
recorrer `data/` o un venv es lento aunque luego se descarte), no sigue enlaces
simbólicos y no entra a ninguna subcarpeta que sea otra copia del repo (tiene su
propio `.git`, como todo worktree).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parents[1]

CARPETAS_AJENAS = frozenset({
    ".git", ".claude", "node_modules", "venv", "data", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov", "staticfiles",
})


def es_ajena(carpeta: Path) -> bool:
    """¿Esta carpeta (bajo la raíz) no es parte del repo?"""
    nombre = carpeta.name
    if nombre in CARPETAS_AJENAS or nombre.startswith(".venv"):
        return True
    # Otra copia del repo (un worktree o un clon) trae su propio `.git`.
    return (carpeta / ".git").exists()


def archivos_del_repo(patron: str, desde: Path = RAIZ) -> Iterator[Path]:
    """Como `desde.rglob(patron)`, pero sólo con archivos del repo real.

    `patron` se compara contra la ruta relativa con la semántica de
    `PurePath.match` (desde la derecha): `"*.html"` casa cualquier HTML y
    `"templates/cotizaciones/*.html"` casa `el-taller/templates/cotizaciones/x.html`.
    Sale en orden, para que los mensajes de los candados sean estables.
    """
    desde = Path(desde)
    for actual, carpetas, nombres in os.walk(desde):
        base = Path(actual)
        carpetas[:] = sorted(c for c in carpetas if not es_ajena(base / c))
        for nombre in sorted(nombres):
            ruta = base / nombre
            if PurePosixPath(ruta.relative_to(desde).as_posix()).match(patron):
                yield ruta
