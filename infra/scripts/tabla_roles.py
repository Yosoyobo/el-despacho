"""Genera la tabla «qué trae cada rol por default» de `ROLES.md`.

La tabla sale de `lib/permisos_defaults.py` (`CATALOGO_PERMISOS` y
`DEFAULTS_POR_ROL`), no se escribe a mano: una tabla a mano de permisos miente
al primer sprint que agrega una acción. `tests/test_roles_md.py` falla si la de
`ROLES.md` ya no coincide con el código.

Uso:
  python3 infra/scripts/tabla_roles.py            # imprime la tabla
  python3 infra/scripts/tabla_roles.py --escribir # la reemplaza en ROLES.md

Sólo biblioteca estándar + `lib/permisos_defaults.py` (no necesita Django).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from lib.permisos_defaults import (  # noqa: E402
    CATALOGO_PERMISOS,
    DEFAULTS_POR_ROL,
    ROLES_SISTEMA,
)

INICIO = "<!-- tabla-roles:inicio · la genera infra/scripts/tabla_roles.py, no editar a mano -->"
FIN = "<!-- tabla-roles:fin -->"

# Cómo se llama cada columna. La clave es la del código; el nombre visible del
# rol se puede cambiar en El Directorio (el de `dueno` hoy es «Director»).
ENCABEZADOS = {
    "super_admin": "super_admin",
    "dueno": "dueno (Director)",
    "contador": "contador",
    "disenador": "disenador",
}


def _celda(acciones: list[str], catalogo: list[str]) -> str:
    if not acciones:
        return "—"
    if set(acciones) == set(catalogo):
        return "todo"
    # En el orden del catálogo, no en el del rol: así dos roles se comparan a ojo.
    return ", ".join(a for a in catalogo if a in acciones)


def tabla() -> str:
    roles = [r for r in ROLES_SISTEMA if r in DEFAULTS_POR_ROL]
    lineas = [
        "| Módulo | " + " | ".join(ENCABEZADOS.get(r, r) for r in roles) + " |",
        "|---|" + "---|" * len(roles),
    ]
    for modulo, catalogo in CATALOGO_PERMISOS.items():
        celdas = [_celda(DEFAULTS_POR_ROL[r].get(modulo, []), catalogo) for r in roles]
        lineas.append(f"| `{modulo}` | " + " | ".join(celdas) + " |")
    return "\n".join(lineas)


def bloque() -> str:
    return f"{INICIO}\n{tabla()}\n{FIN}"


def reemplazar(texto: str) -> str:
    """El `ROLES.md` con el bloque entre los marcadores puesto al día."""
    ini, fin = texto.index(INICIO), texto.index(FIN) + len(FIN)
    return texto[:ini] + bloque() + texto[fin:]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--escribir", action="store_true", help="reemplaza la tabla en ROLES.md")
    args = p.parse_args(argv)
    if not args.escribir:
        print(tabla())
        return 0
    ruta = RAIZ / "ROLES.md"
    ruta.write_text(reemplazar(ruta.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"✓ {ruta.relative_to(RAIZ)} al día")
    return 0


if __name__ == "__main__":
    sys.exit(main())
