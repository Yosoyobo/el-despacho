"""n8n 2.x — el cliente, el respaldo, la copia de los flujos y el compose.

Sprint n8n-MCP (2026-09-28). Todo lo de aquí se ensayó antes contra un n8n
2.40.7 real, levantado sobre una COPIA de la base del NUC. Estas pruebas fijan
lo que ese ensayo encontró, para que un cambio posterior no lo deshaga en
silencio:

- «prender» y «apagar» se llaman ahora publicar/despublicar;
- borrar pasa por archivar, y el borrado puede chocar con la baja en segundo
  plano (409/500) y pasar un segundo después;
- la API sigue entregando los flujos archivados;
- la base va en modo WAL, así que el respaldo no puede ser un `cp`.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from lib import n8n

RAIZ = Path(__file__).resolve().parent.parent


# ── El cliente ──────────────────────────────────────────────────────────────


class _Grabadora:
    """Reemplaza `n8n._pedir`: anota cada llamada y contesta lo que se le diga."""

    def __init__(self, respuestas: dict | None = None, fallan: set | None = None):
        self.llamadas: list[tuple[str, str]] = []
        self.respuestas = respuestas or {}
        self.fallan = fallan or set()

    def __call__(self, ruta, *, metodo="GET", cuerpo=None):
        self.llamadas.append((metodo, ruta))
        if (metodo, ruta) in self.fallan:
            return None
        return self.respuestas.get((metodo, ruta), {})


@pytest.fixture
def api(monkeypatch):
    def armar(**kw):
        g = _Grabadora(**kw)
        monkeypatch.setattr(n8n, "_pedir", g)
        monkeypatch.setattr("time.sleep", lambda _s: None)
        return g
    return armar


def test_prender_pide_publicar(api):
    g = api()
    assert n8n.activar("w1") is True
    assert g.llamadas == [("POST", "/workflows/w1/publish")]


def test_prender_cae_a_la_ruta_vieja_si_publicar_no_contesta(api):
    g = api(fallan={("POST", "/workflows/w1/publish")})
    assert n8n.activar("w1") is True
    assert g.llamadas[-1] == ("POST", "/workflows/w1/activate")


def test_apagar_pide_despublicar(api):
    g = api()
    assert n8n.desactivar("w1") is True
    assert g.llamadas == [("POST", "/workflows/w1/unpublish")]


def test_borrar_archiva_primero(api):
    g = api()
    assert n8n.borrar("w1") is True
    assert g.llamadas == [("POST", "/workflows/w1/archive"), ("DELETE", "/workflows/w1")]


def test_borrar_reintenta_la_carrera_con_la_baja(api, monkeypatch):
    """Medido en el ensayo: tras despublicar, el primer DELETE dio 409/500 y el
    siguiente, 200. Sin el reintento, «quitar» fallaba en ese caso."""
    g = api()
    intentos = {"n": 0}

    def pedir(ruta, *, metodo="GET", cuerpo=None):
        g.llamadas.append((metodo, ruta))
        if metodo == "DELETE":
            intentos["n"] += 1
            return None if intentos["n"] < 2 else {}
        return {}

    monkeypatch.setattr(n8n, "_pedir", pedir)
    assert n8n.borrar("w1") is True
    assert intentos["n"] == 2


def test_borrar_no_insiste_si_no_pudo_archivar(api):
    g = api(fallan={("POST", "/workflows/w1/archive")})
    assert n8n.borrar("w1") is False
    assert ("DELETE", "/workflows/w1") not in g.llamadas


def test_la_lista_no_ensena_los_archivados(api):
    api(respuestas={("GET", f"/workflows?limit={n8n.TOPE}"): {"data": [
        {"id": "a", "name": "Vivo", "nodes": []},
        {"id": "b", "name": "Archivado", "nodes": [], "isArchived": True},
    ]}})
    assert [f["nombre"] for f in n8n.listar_flujos()] == ["Vivo"]


@pytest.mark.parametrize("tipo,esperado", [
    ("n8n-nodes-base.webhook", "Recibe"),
    ("n8n-nodes-base.scheduleTrigger", "Recibe"),
    ("n8n-nodes-base.emailReadImap", "Recibe"),
    ("n8n-nodes-base.set", "manual"),
])
def test_el_disparador_de_webhook_no_se_reporta_como_manual(tipo, esperado):
    """Antes un flujo que espera un webhook salía como «manual»: el tipo
    `webhook` no trae la palabra «trigger»."""
    w = {"id": "x", "name": "f", "nodes": [{"name": "Recibe", "type": tipo}]}
    assert n8n._resumir(w)["disparador"] == esperado


# ── La copia de los flujos en el repo ─────────────────────────────────────────


def _exportador():
    import importlib.util

    spec = importlib.util.spec_from_file_location("exportar_flujos", RAIZ / "infra/n8n/exportar_flujos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_la_copia_no_lleva_lo_que_cambia_solo():
    ex = _exportador()
    w = {"id": "abc", "name": "F", "active": True, "nodes": [{"name": "N"}], "connections": {},
         "settings": {}, "updatedAt": "hoy", "versionId": "v9", "staticData": {"x": 1},
         "shared": [{"project": {}}], "tags": [{"id": "t1", "name": "🤖 Claude"}]}
    limpio = ex.normalizar(w)
    for volatil in ("updatedAt", "versionId", "staticData", "shared"):
        assert volatil not in limpio
    assert limpio["tags"] == ["🤖 Claude"]


def test_el_archivo_lleva_el_id_para_que_renombrar_lo_reemplace():
    ex = _exportador()
    assert ex.nombre_archivo({"id": "Q1w", "name": "Aviso · cotización aprobada"}) == \
        "aviso-cotizacion-aprobada-Q1w.json"


def test_la_copia_retira_el_archivo_de_un_flujo_que_ya_no_existe(tmp_path):
    ex = _exportador()
    (tmp_path / "viejo-zzz.json").write_text("{}")
    (tmp_path / ".gitkeep").write_text("")
    r = ex.escribir([{"id": "a1", "name": "Nuevo", "nodes": []}], tmp_path)
    assert r["retirados"] == ["viejo-zzz.json"]
    assert (tmp_path / "nuevo-a1.json").exists()
    assert (tmp_path / ".gitkeep").exists()
    json.loads((tmp_path / "nuevo-a1.json").read_text())


def test_la_copia_sin_llave_no_intenta_nada(monkeypatch, tmp_path):
    ex = _exportador()
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    assert ex.main(["--destino", str(tmp_path)]) == 2


# ── El respaldo ─────────────────────────────────────────────────────────────


def _bloque_n8n_de_archivo() -> str:
    t = (RAIZ / "infra/scripts/archivo.sh").read_text()
    m = re.search(r"<<'PY'\n(.*?)\nPY\n", t, re.S)
    assert m, "no encontré la copia de la base de n8n en archivo.sh"
    return m.group(1)


def test_el_respaldo_copia_una_base_wal_mientras_alguien_escribe(tmp_path):
    """La 2.x usa WAL: lo recién escrito vive en `-wal` hasta el checkpoint, y
    un `cp` del archivo principal lo perdería. La API de copia no."""
    origen = tmp_path / "database.sqlite"
    con = sqlite3.connect(origen)
    con.execute("pragma journal_mode=wal")
    con.execute("create table workflow_entity (id text, name text)")
    con.execute("insert into workflow_entity values ('w1', 'Facturas')")
    con.commit()  # sigue abierta: los datos están en el WAL, sin checkpoint
    destino = tmp_path / "copia.sqlite"
    r = subprocess.run([sys.executable, "-", str(origen), str(destino)],
                       input=_bloque_n8n_de_archivo(), text=True, capture_output=True)
    con.close()
    assert r.returncode == 0, r.stderr
    filas = sqlite3.connect(destino).execute("select name from workflow_entity").fetchall()
    assert filas == [("Facturas",)]


def test_el_respaldo_no_se_lleva_la_llave_de_cifrado():
    t = (RAIZ / "infra/scripts/archivo.sh").read_text()
    empaque = re.search(r'tar -czf "\$N8N_FILE"[^\n]*', t).group(0)
    assert "config" not in empaque, "config guarda la llave de cifrado de n8n: va aparte"
    assert "database.sqlite" in empaque


def test_el_respaldo_de_n8n_rota_como_los_demas():
    t = (RAIZ / "infra/scripts/archivo.sh").read_text()
    assert "ls -1t n8n-*.tar.gz" in t
    assert "'n8n-*.tar.gz'" in t


# ── El compose ──────────────────────────────────────────────────────────────


def _bloque_compose_n8n() -> str:
    t = (RAIZ / "docker-compose.servicios.yml").read_text()
    m = re.search(r"\n  n8n:\n(.*?)\n  # ── Paperless", t, re.S)
    assert m
    return m.group(1)


def test_n8n_queda_en_la_version_ensayada():
    assert "image: n8nio/n8n:2.40.7" in _bloque_compose_n8n()


def test_n8n_escucha_en_localhost_y_no_en_la_ip_del_tailnet():
    """Atado a la IP del tailnet, un reinicio en que Docker gana a Tailscale lo
    deja sin poder arrancar — pasó el 2026-09-18 y estuvo diez días caído."""
    b = _bloque_compose_n8n()
    assert 'host_ip: "127.0.0.1"' in b
    assert "100.121.244.5" not in b


def test_n8n_se_nombra_por_https_y_con_cookie_segura():
    b = _bloque_compose_n8n()
    assert 'N8N_PROTOCOL: "https"' in b
    assert "N8N_SECURE_COOKIE" not in b.split("# (Se retiró")[0]
    assert 'N8N_WEBHOOK_URL: "https://nuc-learning-center.tailedd04d.ts.net/"' in b
    assert "\n      WEBHOOK_URL:" not in b  # obsoleta en la 2.x


def test_n8n_tiene_memoria_para_su_proceso_de_codigo():
    m = re.search(r"mem_limit: (\d+)g", _bloque_compose_n8n())
    assert m and int(m.group(1)) >= 2, "la 2.40.7 ocupa ~810 MB en reposo"
