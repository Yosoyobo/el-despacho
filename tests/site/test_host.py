"""lib.site.host — lectura de /proc, fallback a no-disponible si falta."""

from __future__ import annotations

import pytest


@pytest.fixture
def proc_falso(tmp_path, monkeypatch):
    """Crea un /proc minimal sintético y apunta SITE_PROC_ROOT ahí."""
    (tmp_path / "loadavg").write_text("0.50 0.42 0.31 1/200 12345\n")
    (tmp_path / "meminfo").write_text(
        "MemTotal:        1024000 kB\n"
        "MemAvailable:     512000 kB\n"
        "MemFree:          400000 kB\n"
        "SwapTotal:             0 kB\n"
    )
    (tmp_path / "cpuinfo").write_text("processor\t: 0\nprocessor\t: 1\n")
    (tmp_path / "uptime").write_text("123456.78 654321.00\n")
    monkeypatch.setenv("SITE_PROC_ROOT", str(tmp_path))
    # Recargar el módulo para que tome la env var
    import importlib

    from lib.site import host as h
    importlib.reload(h)
    yield h
    monkeypatch.delenv("SITE_PROC_ROOT", raising=False)


def test_cpu_y_load(proc_falso):
    r = proc_falso.cpu_y_load()
    assert r["disponible"] is True
    assert r["load_1"] == 0.50
    assert r["load_5"] == 0.42
    assert r["load_15"] == 0.31
    assert r["cores"] == 2


def test_memoria(proc_falso):
    r = proc_falso.memoria()
    assert r["disponible"] is True
    assert r["total_mb"] == round(1024000 / 1024, 1)
    assert 0 < r["pct_usado"] < 100


def test_uptime(proc_falso):
    r = proc_falso.uptime()
    assert r["disponible"] is True
    assert r["segundos"] == 123456
    assert r["humano"].endswith("h")


def test_disco_root_existente():
    from lib.site import host
    r = host.disco("/")
    assert r["disponible"] is True
    assert r["total_gb"] > 0
    assert 0 <= r["pct_usado"] <= 100


def test_proc_no_existe(monkeypatch):
    monkeypatch.setenv("SITE_PROC_ROOT", "/ruta/que/no/existe/12345")
    import importlib

    from lib.site import host as h
    importlib.reload(h)
    assert h.cpu_y_load()["disponible"] is False
    assert h.memoria()["disponible"] is False
    assert h.uptime()["disponible"] is False


def test_snapshot_estructura():
    from lib.site import host
    r = host.snapshot()
    assert set(r.keys()) == {"cpu_load", "memoria", "disco", "disco_io", "uptime"}


class TestActividadDelDisco:
    """El disco OCUPADO no se mueve —14.5% hoy, 14.5% mañana— así que en una
    pared su tendencia es una raya recta. Lo que se mueve, y lo que interesa, es
    cuánto está trabajando: eso mide `disco_io`."""

    def test_la_primera_muestra_no_inventa_una_tasa(self, monkeypatch):
        """`/proc/diskstats` da contadores ACUMULADOS desde el arranque: con una
        sola lectura no hay tasa que calcular, y devolver cero ahí sería mentir
        con «el disco está quieto»."""
        from lib.site import host
        host._IO_PREVIO.clear()
        monkeypatch.setattr(host, "_leer", lambda _p: "   8   0 sda 1 2 100 4 5 6 200 8 9 10 11")
        assert host.disco_io()["disponible"] is False

    def test_la_segunda_muestra_da_la_tasa(self, monkeypatch):
        from lib.site import host
        host._IO_PREVIO.clear()
        # Primera lectura: 0 sectores. Segunda: 2048 leídos y 4096 escritos, que
        # a 512 bytes por sector son 1 MB y 2 MB.
        monkeypatch.setattr(host, "_leer", lambda _p: "   8   0 sda 1 2 0 4 5 6 0 8 9 10 11")
        host.disco_io()
        monkeypatch.setattr(host, "_leer", lambda _p: "   8   0 sda 1 2 2048 4 5 6 4096 8 9 10 11")
        r = host.disco_io()
        assert r["disponible"] is True
        assert r["lectura_mb_s"] > 0
        assert r["escritura_mb_s"] > r["lectura_mb_s"]

    def test_los_snaps_y_la_ram_no_cuentan_como_disco(self, monkeypatch):
        """En este NUC hay una docena de `loop*` (los paquetes snap montados). Si
        se contaran, la cifra de lectura saldría inflada por cosas que no tocan
        el SSD."""
        from lib.site import host
        host._IO_PREVIO.clear()
        solo_loops = "\n".join(
            f"   7   {i} loop{i} 1 2 99999 4 5 6 99999 8 9 10 11" for i in range(3)
        )
        monkeypatch.setattr(host, "_leer", lambda _p: solo_loops)
        host.disco_io()
        r = host.disco_io()
        # Todo era ruido: no hay actividad que reportar, no una cifra inflada.
        assert r.get("lectura_mb_s", 0) == 0

    def test_una_particion_no_se_cuenta_dos_veces(self):
        """`sda` y `sda1` reportan los mismos bytes. Contando las dos, cada byte
        se contaría doble. Se prueba sobre `sumar_sectores` y no sobre la tasa:
        la tasa depende del tiempo entre dos lecturas, así que compararla sería
        comparar relojes."""
        from lib.site.host import sumar_sectores
        con_particion = ("   8   0 sda 1 2 2048 4 5 6 4096 8 9 10 11\n"
                         "   8   1 sda1 1 2 2048 4 5 6 4096 8 9 10 11")
        solo_disco = "   8   0 sda 1 2 2048 4 5 6 4096 8 9 10 11"
        assert sumar_sectores(con_particion) == sumar_sectores(solo_disco) == (2048, 4096)

    def test_en_nvme_la_particion_lleva_p(self):
        """En NVMe la forma es al revés que en SATA: el disco es `nvme0n1` (acaba
        en dígito) y la partición `nvme0n1p1`. Descartar «lo que acaba en dígito»
        tiraría el disco entero."""
        from lib.site.host import sumar_sectores
        crudo = ("259  0 nvme0n1 1 2 1024 4 5 6 2048 8 9 10 11\n"
                 "259  1 nvme0n1p1 1 2 1024 4 5 6 2048 8 9 10 11")
        assert sumar_sectores(crudo) == (1024, 2048)

    def test_sin_proc_no_truena(self, monkeypatch):
        from lib.site import host
        monkeypatch.setattr(host, "_leer", lambda _p: None)
        assert host.disco_io()["disponible"] is False


# ── Gauges ───────────────────────────────────────────────────────────────────

class TestGaugeDeContenedores:
    """«6 de 6 corriendo» tiene que pintar VERDE.

    El gauge de contenedores pasaba `umbral_warn=0, umbral_err=0`, y con ambos en
    cero cualquier porcentaje cae en «error»: el anillo salía rojo aunque todo
    estuviera arriba. Era una alarma que no se podía apagar, y se veía en el panel
    que mira el super_admin. La métrica es de las que «más es mejor», así que el
    color se calcula sobre lo que FALTA (`invertido=True`).
    """

    def test_todo_arriba_pinta_verde(self):
        from lib.site.gauges import gauge

        g = gauge(100.0, invertido=True, umbral_warn=0.1, umbral_err=25)
        assert g["color"] == "success"
        # El anillo sigue lleno: se quiere ver completo, no vacío.
        assert g["pct"] == 100.0

    def test_uno_caido_avisa_y_varios_alarman(self):
        from lib.site.gauges import gauge

        assert gauge(100 * 5 / 6, invertido=True, umbral_warn=0.1, umbral_err=25)["color"] == "warning"
        assert gauge(100 * 4 / 6, invertido=True, umbral_warn=0.1, umbral_err=25)["color"] == "error"
        assert gauge(0.0, invertido=True, umbral_warn=0.1, umbral_err=25)["color"] == "error"

    def test_las_metricas_normales_no_cambian(self):
        """Sin `invertido`, más sigue siendo peor (disco, CPU, memoria)."""
        from lib.site.gauges import gauge

        assert gauge(10.0)["color"] == "success"
        assert gauge(70.0)["color"] == "warning"
        assert gauge(85.0)["color"] == "error"
        assert gauge(None)["disponible"] is False

    def test_el_snapshot_del_taller_usa_el_gauge_invertido(self):
        """El Dashboard del Taller y El Site comparten la lógica: los dos sitios
        que pintan contenedores tienen que estar invertidos."""
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        # Tres sitios calculan este gauge: los dos snapshots de `lib/site/gauges.py`
        # y el tablero de El Site. `count` sobre "invertido=True" a secas también
        # cazaría la mención del docstring, así que se cuentan las LLAMADAS.
        sitios = 0
        for ruta in ("lib/site/gauges.py", "la-gerencia/apps/el_site/views.py"):
            fuente = (raiz / ruta).read_text()
            sitios += fuente.count("(pct_running, invertido=True")
            assert "pct_running, umbral_warn=0, umbral_err=0" not in fuente, (
                f"{ruta} todavía pinta «todo arriba» como error"
            )
        assert sitios == 3, f"esperaba 3 llamadas invertidas, encontré {sitios}"
