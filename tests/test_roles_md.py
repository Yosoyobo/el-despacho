"""`ROLES.md` dice lo mismo que el código de permisos.

La tabla «qué trae cada rol por default» la genera
`infra/scripts/tabla_roles.py` desde `lib/permisos_defaults.py`. Si alguien
agrega una acción o cambia un default y no regenera la tabla, este test falla y
dice el comando que la pone al día.
"""

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _generador():
    ruta = RAIZ / "infra" / "scripts" / "tabla_roles.py"
    spec = importlib.util.spec_from_file_location("tabla_roles", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _roles_md() -> str:
    return (RAIZ / "ROLES.md").read_text(encoding="utf-8")


def test_la_tabla_de_roles_md_coincide_con_defaults_por_rol():
    gen = _generador()
    texto = _roles_md()
    assert gen.INICIO in texto and gen.FIN in texto, "ROLES.md perdió los marcadores de la tabla"
    assert gen.reemplazar(texto) == texto, (
        "La tabla de ROLES.md no coincide con lib/permisos_defaults.py. "
        "Regenérala: python3 infra/scripts/tabla_roles.py --escribir")


def test_la_tabla_cubre_todo_el_catalogo_y_los_roles_del_sistema():
    """El generador no se salta nada: un renglón por módulo del catálogo y una
    columna por rol del sistema con defaults."""
    from lib.permisos_defaults import CATALOGO_PERMISOS, DEFAULTS_POR_ROL, ROLES_SISTEMA

    gen = _generador()
    lineas = gen.tabla().splitlines()
    modulos = [ln.split("|")[1].strip().strip("`") for ln in lineas[2:]]
    assert modulos == list(CATALOGO_PERMISOS)
    columnas = len(lineas[0].split("|")) - 3  # sin «Módulo» ni los bordes
    assert columnas == len([r for r in ROLES_SISTEMA if r in DEFAULTS_POR_ROL])


def test_cada_celda_dice_exactamente_lo_del_rol():
    from lib.permisos_defaults import CATALOGO_PERMISOS, DEFAULTS_POR_ROL, ROLES_SISTEMA

    gen = _generador()
    roles = [r for r in ROLES_SISTEMA if r in DEFAULTS_POR_ROL]
    for linea in gen.tabla().splitlines()[2:]:
        partes = [p.strip() for p in linea.split("|")[1:-1]]
        modulo = partes[0].strip("`")
        for rol, celda in zip(roles, partes[1:], strict=True):
            esperado = set(DEFAULTS_POR_ROL[rol].get(modulo, []))
            if celda == "todo":
                leido = set(CATALOGO_PERMISOS[modulo])
            elif celda == "—":
                leido = set()
            else:
                leido = {a.strip() for a in celda.split(",")}
            assert leido == esperado, (modulo, rol, celda)


def test_roles_md_nombra_las_piezas_del_modelo_actual():
    """Si alguien reescribe ROLES.md, que no vuelva al modelo viejo por rol."""
    texto = _roles_md()
    for pieza in ("CATALOGO_PERMISOS", "DEFAULTS_POR_ROL", "PERMISOS_UNIVERSALES",
                  "roles_extra", "super_admin", "requiere_permiso", "sembrar"):
        assert pieza.lower() in texto.lower(), pieza
    assert "requires_role" not in texto  # borrado en S-Deuda-Sep28
