"""Candado §4 #23: el deploy abre y cierra SOLO su ventana de mantenimiento.

La ventana (el banner ámbar) la abría `mudanza.sh`. Cuando el deploy se mudó al
NUC (`deploy_nuc.sh`) el paso se perdió y quedó dependiendo de que alguien lo
corriera a mano; el 2026-09-28 un deploy salió sin aviso por eso. Este candado
exige que el guion la abra ANTES de tocar contenedores y que la cierre al salir
por cualquier camino (verde, rollback o error).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_GUION = Path(__file__).resolve().parent.parent / "infra" / "scripts" / "deploy_nuc.sh"


def _texto() -> str:
    return _GUION.read_text(encoding="utf-8")


def test_la_ventana_se_abre_antes_del_pull():
    s = _texto()
    abre = s.index("ventana abrir")
    assert "marcar_deploy_en_curso" in s
    assert abre < s.index("compose $COMPOSE_FILES pull"), "la ventana se abre DESPUÉS de bajar imágenes"
    assert abre < s.index("compose $COMPOSE_FILES up -d"), "la ventana se abre DESPUÉS de recrear"


def test_la_ventana_se_cierra_al_salir_por_cualquier_camino():
    s = _texto()
    assert "limpiar_deploy_en_curso" in s
    # El trap cubre el rollback y los `exit 1`; va pegado a la apertura.
    assert "trap 'ventana cerrar' EXIT" in s
    assert s.index("trap 'ventana cerrar' EXIT") < s.index("compose $COMPOSE_FILES pull")


def test_la_ventana_se_cierra_en_cuanto_el_deploy_esta_comprobado():
    s = _texto()
    comprobado = s.index("Las imágenes que corren son las de este despliegue")
    cierre = s.index("ventana cerrar", comprobado)
    assert cierre < s.index("anunciar_novedades"), "la ventana sigue abierta durante el aviso de Novedades"


def test_la_ventana_trae_ttl_de_la_jornada():
    # TTL_DEFAULT son 10 min, corto para un deploy de 3+ min con rollback.
    assert "ttl_segundos=1800" in _texto()


def test_abrir_la_ventana_no_tumba_el_deploy():
    s = _texto()
    bloque = s[s.index("ventana() {"): s.index("echo \"=== Ventana de mantenimiento: abierta")]
    assert "|| echo" in bloque, "si Redis no contesta, la ventana no debe abortar el deploy"


def test_el_guion_es_bash_valido():
    subprocess.run(["bash", "-n", str(_GUION)], check=True)
