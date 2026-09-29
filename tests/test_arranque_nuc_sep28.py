"""El NUC vuelve solo tras un reinicio (S-Pendientes-Sep28).

`restart: always` sólo reintenta lo que ya corrió: un servicio que falla al
ARRANCAR porque Tailscale aún no tiene su IP se queda así para siempre. Estos
candados fijan las tres piezas que lo evitan.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CRON = (RAIZ / "infra/cron/el-despacho.cron").read_text()


def _bloque_gestionado() -> str:
    ini = CRON.index("# >>> El Despacho (gestionado por mudanza.sh) >>>")
    fin = CRON.index("# <<< El Despacho <<<")
    return CRON[ini:fin]


def test_el_arranque_esta_en_el_cron_y_dentro_del_bloque():
    assert "@reboot" in _bloque_gestionado()
    assert "arranque_nuc.sh" in _bloque_gestionado()


def test_nada_vive_fuera_de_los_marcadores():
    """sync_crons sólo borra lo que hay ENTRE los marcadores: lo de afuera se
    anexaba en cada deploy (el NUC llegó a tener 38 copias del encabezado)."""
    antes = CRON[: CRON.index("# >>> El Despacho")]
    despues = CRON[CRON.index("# <<< El Despacho <<<") + len("# <<< El Despacho <<<"):]
    assert not antes.strip()
    assert not despues.strip()


def test_deploy_y_arranque_usan_la_misma_lista_de_compose():
    """Si cada guion armara su propia lista, el día que se agregue un servicio uno
    de los dos lo olvidaría y ese servicio no volvería tras un reinicio."""
    for guion in ("deploy_nuc.sh", "arranque_nuc.sh"):
        texto = (RAIZ / "infra/scripts" / guion).read_text()
        assert ". infra/scripts/_compose_nuc.sh" in texto, guion
        assert 'COMPOSE_FILES="-f docker-compose.yml' not in texto, guion


def test_el_arranque_espera_al_tailnet_y_no_recrea():
    texto = (RAIZ / "infra/scripts/arranque_nuc.sh").read_text()
    assert "tailscale0" in texto
    assert "up -d --no-recreate" in texto


def test_los_guiones_son_bash_valido():
    for guion in ("deploy_nuc.sh", "arranque_nuc.sh", "_compose_nuc.sh", "sync_crons.sh", "optimizar.sh"):
        r = subprocess.run(["bash", "-n", str(RAIZ / "infra/scripts" / guion)], capture_output=True, text=True)
        assert r.returncode == 0, f"{guion}: {r.stderr}"
