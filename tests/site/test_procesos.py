"""Quién usa la máquina — el panel de procesos (S-NUC-Servicios, 2026-08-24).

Oscar lo pidió mirando los relojes: «así puedo entender los cuellos de botella
del CPU y RAM y SSD». Los relojes dicen cuánto; esto dice quién.

Lo que cuidan estas pruebas, en orden de lo que dolería:

1. Que **el nombre no corra las columnas**. En `/proc/PID/stat` el nombre va
   entre paréntesis y puede llevar espacios y paréntesis dentro; partir por
   espacios daría memoria y CPU de otro campo — números creíbles y falsos.
2. Que **el CPU necesite dos muestras** y no invente un porcentaje con una.
3. Que **un PID reusado no dé un número disparatado**.
4. Que **sin `/proc` no truene**, porque en macOS y en las pruebas no existe.
"""

from __future__ import annotations

import pytest

from lib.site import procesos


@pytest.fixture(autouse=True)
def _sin_muestra():
    procesos.olvidar_muestra()
    yield
    procesos.olvidar_muestra()


def _fabricar_proc(tmp_path, pid, nombre, utime, stime, arranque, rss_paginas):
    """Un /proc de mentiras con la forma exacta del real."""
    d = tmp_path / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    # OJO con el corrimiento: el parser cuenta desde el estado (campo 3), que
    # aquí se escribe aparte como "S". Así que `campos[i]` es el campo i+4 y
    # los índices van uno menos que en el parser. Verificado contra una línea
    # real del NUC en `test_el_parseo_contra_una_linea_real`.
    campos = ["0"] * 24
    campos[10], campos[11] = str(utime), str(stime)
    campos[18] = str(arranque)
    campos[20] = str(rss_paginas)
    (d / "stat").write_text(f"{pid} ({nombre}) S " + " ".join(campos))
    (d / "comm").write_text(nombre)
    (d / "cmdline").write_text(f"/usr/bin/{nombre}\0--flag\0")
    return d


def test_un_nombre_con_espacios_y_parentesis_no_corre_las_columnas(tmp_path, monkeypatch):
    """El caso que rompe el parseo ingenuo. Si se parte por espacios, la
    memoria sale de otro campo: un número creíble y falso."""
    monkeypatch.setattr(procesos, "PROC_ROOT", tmp_path)
    _fabricar_proc(tmp_path, 42, "Web Content (tab)", utime=10, stime=5,
                   arranque=100, rss_paginas=2560)

    procesos.top()  # primera muestra
    r = procesos.top()
    uno = r["procesos"][0]
    assert uno["pid"] == 42
    assert uno["memoria_mb"] == 10.0, "la memoria salió de otro campo"


def test_la_primera_lectura_no_inventa_un_porcentaje(tmp_path, monkeypatch):
    """El CPU es la diferencia entre dos lecturas: con una sola no se puede."""
    monkeypatch.setattr(procesos, "PROC_ROOT", tmp_path)
    _fabricar_proc(tmp_path, 7, "gunicorn", 100, 0, 50, 1000)

    r = procesos.top()
    assert r["primera_lectura"] is True
    assert r["procesos"][0]["cpu"] is None


def test_con_dos_muestras_ya_hay_porcentaje(tmp_path, monkeypatch):
    monkeypatch.setattr(procesos, "PROC_ROOT", tmp_path)
    _fabricar_proc(tmp_path, 7, "gunicorn", 100, 0, 50, 1000)
    procesos.top()

    # El proceso consumió más tiempo de CPU desde la lectura anterior.
    _fabricar_proc(tmp_path, 7, "gunicorn", 200, 0, 50, 1000)
    r = procesos.top()
    assert r["primera_lectura"] is False
    assert r["procesos"][0]["cpu"] is not None
    assert r["procesos"][0]["cpu"] > 0


def test_un_pid_reusado_no_da_un_numero_disparatado(tmp_path, monkeypatch):
    """Linux recicla los PID. Comparar dos procesos distintos daría un
    porcentaje absurdo; el arranque es lo que los distingue."""
    monkeypatch.setattr(procesos, "PROC_ROOT", tmp_path)
    _fabricar_proc(tmp_path, 7, "viejo", 5000, 0, arranque=50, rss_paginas=1000)
    procesos.top()

    # Mismo PID, arranque distinto: es OTRO proceso.
    _fabricar_proc(tmp_path, 7, "nuevo", 10, 0, arranque=99999, rss_paginas=1000)
    r = procesos.top()
    assert r["procesos"][0]["cpu"] is None, "se comparó contra un proceso que ya no existe"


def test_sin_proc_no_truena(tmp_path, monkeypatch):
    monkeypatch.setattr(procesos, "PROC_ROOT", tmp_path / "no-existe")
    r = procesos.top()
    assert r["disponible"] is False
    assert r["procesos"] == []


def test_se_devuelven_a_lo_mucho_los_del_tope(tmp_path, monkeypatch):
    """Más de un puñado es ruido en una pared."""
    monkeypatch.setattr(procesos, "PROC_ROOT", tmp_path)
    for pid in range(1, 30):
        _fabricar_proc(tmp_path, pid, f"proc{pid}", pid * 10, 0, 1, pid * 100)
    r = procesos.top()
    assert len(r["procesos"]) <= procesos.TOPE


def test_el_nombre_pierde_la_ruta_larga(tmp_path, monkeypatch):
    """«/usr/local/bin/gunicorn» no dice más que «gunicorn» a tres metros."""
    monkeypatch.setattr(procesos, "PROC_ROOT", tmp_path)
    _fabricar_proc(tmp_path, 3, "gunicorn", 1, 0, 1, 100)
    r = procesos.top()
    assert "/usr/bin/" not in r["procesos"][0]["nombre"]
    assert "gunicorn" in r["procesos"][0]["nombre"]


def test_un_proceso_que_muere_a_media_lectura_no_rompe(tmp_path, monkeypatch):
    """Entre listar /proc y leer cada PID, algunos ya no están. Es normal."""
    monkeypatch.setattr(procesos, "PROC_ROOT", tmp_path)
    _fabricar_proc(tmp_path, 5, "vivo", 1, 0, 1, 100)
    (tmp_path / "999").mkdir()  # carpeta sin `stat`: como si acabara de morir
    r = procesos.top()
    assert r["disponible"] is True
    assert [p["pid"] for p in r["procesos"]] == [5]


def test_el_parseo_contra_una_linea_real(tmp_path, monkeypatch):
    """Una línea de verdad, tomada del NUC el 2026-08-24 con `ps` al lado.

    Es la prueba que atrapa un corrimiento de índice: los campos de
    `/proc/PID/stat` no se pueden verificar de memoria, y un índice equivocado
    da números creíbles y falsos. Aquí `ps` decía 28512 KB para ese proceso, y
    7100 páginas × 4 KB son 27.7 MB — coinciden.
    """
    real = (
        "140191 (gunicorn) S 140144 140191 140191 0 -1 4194560 8915 35818 0 0 "
        "59 6 348 14 20 0 1 0 1195313 38252544 7100 18446744073709551615 1 1 0 0 0"
    )
    d = tmp_path / "140191"
    d.mkdir()
    (d / "stat").write_text(real)
    (d / "comm").write_text("gunicorn")
    (d / "cmdline").write_text("/usr/local/bin/gunicorn\0el_taller.wsgi\0")
    monkeypatch.setattr(procesos, "PROC_ROOT", tmp_path)

    ticks, rss_paginas, arranque = procesos._stat(140191)
    assert ticks == 59 + 6, "utime/stime salieron de otro campo"
    assert rss_paginas == 7100, "la memoria salió de otro campo"
    assert arranque == 1195313

    r = procesos.top()
    assert r["procesos"][0]["memoria_mb"] == 27.7
