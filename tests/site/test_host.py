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
    assert set(r.keys()) == {"cpu_load", "memoria", "disco", "uptime"}
