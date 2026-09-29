"""La suite da lo mismo en la Mac que en el CI.

Dos cosas hacían que pasara en El Mensajero y fallara en local:

1. Un test con Redis en `localhost:6379` fijo: en la Mac el Redis de pruebas
   vive en otro puerto (`REDIS_URL`), y en vez de saltarse daba ERROR.
2. Candados que barren el árbol con `RAIZ.rglob(...)`: en la Mac el repo trae
   adentro `.claude/worktrees/` (copias enteras del repo), venvs y `data/`.

Aquí se prueba el helper que evita (2) y se amarran los dos patrones.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests._arbol import RAIZ, archivos_del_repo

CARPETA_TESTS = Path(__file__).resolve().parent


# ── El helper ────────────────────────────────────────────────────────────────

@pytest.fixture
def arbol(tmp_path):
    raiz = tmp_path / "repo"
    fuera = tmp_path / "fuera"

    def toca(rel, base=raiz):
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")

    toca("el-taller/templates/cotizaciones/pdf.html")
    toca("el-taller/templates/base.html")
    toca(".claude/worktrees/otra/el-taller/templates/cotizaciones/pdf.html")
    toca(".venv/lib/python3.12/site-packages/x/templates/cotizaciones/pdf.html")
    toca(".venv.nuevo/lib/templates/cotizaciones/pdf.html")
    toca("envoltorio/node_modules/y/templates/cotizaciones/pdf.html")
    toca("data/media/templates/cotizaciones/pdf.html")
    # Un clon o worktree en cualquier otra carpeta: su `.git` es un archivo.
    toca("copia/.git")
    toca("copia/el-taller/templates/cotizaciones/pdf.html")
    # Un enlace simbólico a una carpeta fuera del repo no se sigue.
    toca("templates/cotizaciones/pdf.html", base=fuera)
    (raiz / "enlace").symlink_to(fuera, target_is_directory=True)
    return raiz


def _rel(rutas, raiz):
    return sorted(p.relative_to(raiz).as_posix() for p in rutas)


def test_el_helper_ve_sólo_el_repo_real(arbol):
    assert _rel(archivos_del_repo("templates/cotizaciones/*.html", arbol), arbol) == [
        "el-taller/templates/cotizaciones/pdf.html",
    ]
    assert _rel(archivos_del_repo("*.html", arbol), arbol) == [
        "el-taller/templates/base.html",
        "el-taller/templates/cotizaciones/pdf.html",
    ]


def test_rglob_a_secas_sí_se_sale(arbol):
    """El testigo de que el caso de arriba es real: `rglob` ve las copias."""
    assert len(list(arbol.rglob("templates/cotizaciones/*.html"))) > 1


# ── Los patrones prohibidos en la suite ──────────────────────────────────────

def _archivos_de_test():
    for ruta in sorted(CARPETA_TESTS.rglob("*.py")):
        yield ruta, ast.parse(ruta.read_text(encoding="utf-8"))


def _es_raiz_del_repo(nodo: ast.AST, ruta: Path) -> bool:
    """¿`nodo` es `Path(__file__).resolve().parents[N]` con N = la raíz del repo?"""
    if not (isinstance(nodo, ast.Subscript) and isinstance(nodo.value, ast.Attribute)
            and nodo.value.attr == "parents" and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, int)):
        return False
    padres = ruta.resolve().parents
    return nodo.slice.value < len(padres) and padres[nodo.slice.value] == RAIZ


class _BarridoDeRaiz(ast.NodeVisitor):
    """Encuentra `X.rglob(...)`/`X.walk(...)` con `X` = la raíz del repo.

    Los nombres se resuelven por ámbito: el mismo `raiz` es la raíz en un test y
    una subcarpeta en el de al lado. Un nombre de la raíz asignado en el módulo
    vale en las funciones mientras éstas no lo reasignen."""

    def __init__(self, ruta: Path):
        self.ruta = ruta
        self.ambitos: list[dict[str, bool]] = [{}]
        self.culpables: list[int] = []

    def _es_raiz(self, nombre: str) -> bool:
        for ambito in reversed(self.ambitos):
            if nombre in ambito:
                return ambito[nombre]
        return False

    def visit_FunctionDef(self, nodo):
        self.ambitos.append({})
        self.generic_visit(nodo)
        self.ambitos.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, nodo):
        self.generic_visit(nodo)
        for t in nodo.targets:
            if isinstance(t, ast.Name):
                self.ambitos[-1][t.id] = _es_raiz_del_repo(nodo.value, self.ruta)

    def visit_Call(self, nodo):
        self.generic_visit(nodo)
        if isinstance(nodo.func, ast.Attribute) and nodo.func.attr in ("rglob", "walk"):
            receptor = nodo.func.value
            if ((isinstance(receptor, ast.Name) and self._es_raiz(receptor.id))
                    or _es_raiz_del_repo(receptor, self.ruta)):
                self.culpables.append(nodo.lineno)


def test_ningún_test_barre_la_raíz_con_rglob():
    """`RAIZ.rglob(...)` entra a `.claude/worktrees/`, a los venvs y a `data/`.
    Desde la raíz se barre con `tests._arbol.archivos_del_repo`."""
    culpables = []
    for ruta, arbol in _archivos_de_test():
        barrido = _BarridoDeRaiz(ruta)
        barrido.visit(arbol)
        culpables += [f"{ruta.relative_to(RAIZ)}:{n}" for n in barrido.culpables]
    assert not culpables, culpables


def test_ningún_test_fija_la_dirección_de_redis():
    """Un cliente de Redis armado con una URL literal ignora `REDIS_URL`: en una
    máquina con el Redis en otro puerto el test da ERROR en vez de saltarse."""
    culpables = [
        f"{ruta.relative_to(RAIZ)}:{n.lineno}"
        for ruta, arbol in _archivos_de_test()
        for n in ast.walk(arbol)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "from_url" and n.args
        and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)
    ]
    assert not culpables, culpables


def test_la_razón_del_salto_dice_a_dónde_sin_la_contraseña():
    from tests.conftest import razon_sin_redis

    assert razon_sin_redis("redis://127.0.0.1:56390/7") == (
        "Redis no contesta en REDIS_URL=redis://127.0.0.1:56390/7")
    assert razon_sin_redis("redis://:secreto@h:1/0").endswith("=redis://h:1/0")
    assert razon_sin_redis("redis://yo:secreto@h:1/0").endswith("=redis://h:1/0")
