"""La Gerencia trae dentro de su imagen toda app de El Taller que importa.

La suite corre con `tests.django_settings`, que instala las apps de los dos
proyectos juntas. Por eso un `from apps.<x> import …` en La Gerencia pasa en
verde aunque su Dockerfile no copie `el-taller/apps/<x>/`: el hueco sólo
aparece en producción, como un 500 (§14 Bug A).

Así rompió «Metas de KPI» (2026-09-29): el panel importaba `apps.taller_home`
dentro de un `try` y salía vacío en silencio; el guardado lo importaba sin
`try` y tronaba con `ModuleNotFoundError`. La aprobación de KPIs custom en
Los Chalanes tenía el mismo hueco.

Este candado lee el código, no lo ejecuta: toda app `apps.<x>` que se importe
desde `la-gerencia/` y no viva ahí tiene que (a) copiarse en el Dockerfile y
(b) estar en `INSTALLED_APPS` (sus modelos se consultan).
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
GERENCIA = RAIZ / "la-gerencia"
IMPORT_APP = re.compile(r"^\s*(?:from|import)\s+apps\.([a-z_]+)", re.MULTILINE)


def _apps_del_taller_que_importa_gerencia() -> set[str]:
    propias = {p.name for p in (GERENCIA / "apps").iterdir() if p.is_dir()}
    importadas: set[str] = set()
    for archivo in GERENCIA.rglob("*.py"):
        if "__pycache__" in archivo.parts:
            continue
        importadas.update(IMPORT_APP.findall(archivo.read_text(encoding="utf-8")))
    return importadas - propias


def test_hay_apps_del_taller_importadas():
    # Si esto queda vacío, la regex dejó de ver los imports y el candado
    # pasaría por la razón equivocada.
    assert "tesoreria" in _apps_del_taller_que_importa_gerencia()


def test_el_dockerfile_copia_cada_app_del_taller_que_importa():
    dockerfile = (GERENCIA / "Dockerfile").read_text(encoding="utf-8")
    faltan = sorted(
        app for app in _apps_del_taller_que_importa_gerencia()
        if f"COPY el-taller/apps/{app}/ /app/apps/{app}/" not in dockerfile
    )
    assert not faltan, f"la-gerencia/Dockerfile no copia: {faltan}"


def test_installed_apps_registra_cada_app_del_taller_que_importa():
    settings = (GERENCIA / "la_gerencia" / "settings.py").read_text(encoding="utf-8")
    faltan = sorted(
        app for app in _apps_del_taller_que_importa_gerencia()
        if f'"apps.{app}.' not in settings
    )
    assert not faltan, f"INSTALLED_APPS de La Gerencia no registra: {faltan}"
