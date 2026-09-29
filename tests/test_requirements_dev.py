"""`requirements-dev.txt` no se aparta de lo que corre El Mensajero.

El `.venv` local se arma con `requirements-dev.txt`; el CI instala
`requirements.txt` para la suite y fija ruff aparte en el job «Ruff». Si las
dos fuentes divergen, la Mac deja de predecir al CI: un ruff distinto marca
reglas distintas, y un `-r requirements.txt` olvidado arma un venv sin Django.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _dev() -> str:
    return (RAIZ / "requirements-dev.txt").read_text(encoding="utf-8")


def test_dev_incluye_las_dependencias_de_la_app():
    lineas = [ln.strip() for ln in _dev().splitlines()]
    assert "-r requirements.txt" in lineas


def test_ruff_de_dev_es_el_mismo_que_el_del_ci():
    workflow = (RAIZ / ".github/workflows/el-mensajero.yml").read_text(encoding="utf-8")
    del_ci = re.findall(r"pip install ruff==([\w.]+)", workflow)
    local = re.findall(r"^ruff==([\w.]+)\s*$", _dev(), re.M)
    assert del_ci, "el job de lint ya no fija la versión de ruff"
    assert local == [del_ci[0]], (local, del_ci)


def test_el_ci_y_los_dockerfiles_usan_el_mismo_python():
    """El README pide crear el `.venv` con esta versión: si el CI sube de
    Python, el README y este candado se actualizan juntos."""
    workflow = (RAIZ / ".github/workflows/el-mensajero.yml").read_text(encoding="utf-8")
    versiones_ci = set(re.findall(r'python-version:\s*"([\d.]+)"', workflow))
    versiones_docker = {
        m for df in ("el-taller", "la-gerencia", "la-recepcion")
        for m in re.findall(r"FROM python:([\d.]+)-slim",
                            (RAIZ / df / "Dockerfile").read_text(encoding="utf-8"))
    }
    assert versiones_ci == versiones_docker == {"3.12"}, (versiones_ci, versiones_docker)
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    assert "python3.12 -m venv .venv" in readme
