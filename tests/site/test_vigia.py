"""El Vigía — la pantalla de pared del NUC.

Lo que estas pruebas fijan, en orden de importancia:

1. **No sale a internet.** Por el dominio público devuelve 404, y también si la
   petición trae `X-Forwarded-For` (o sea, si pasó por El Portero). Es lo único
   que la protege: la página no pide sesión, porque no puede — en producción
   `SESSION_COOKIE_SECURE=True` y la cookie no viaja por `http://localhost`.
2. **Se abre sin sesión** desde la máquina. Si esto se rompiera, la pantalla de
   kiosco se quedaría en el login tras cada reinicio.
3. **El parseo de los logs de Docker**, que es la parte con protocolo de por
   medio: el stream viene multiplexado en tramas de 8 bytes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from lib.site import actividad

# ── Acceso ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSoloEnLaMaquinaQueVigila:

    def _get(self, client, settings, ruta="/site/vivo/", host="localhost", **extra):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        return client.get(ruta, HTTP_HOST=host, **extra)

    def test_desde_la_maquina_abre_sin_sesion(self, client, settings):
        """Cliente anónimo, host loopback: 200. Una pantalla de kiosco no puede
        depender de un login que nadie va a escribir tras un reinicio."""
        r = self._get(client, settings)
        assert r.status_code == 200
        assert b"El Vig" in r.content

    def test_por_el_dominio_publico_no_existe(self, client, settings):
        r = self._get(client, settings, host="gerencia.learningcenter.mx")
        assert r.status_code == 404

    def test_una_peticion_proxeada_no_pasa(self, client, settings):
        """Aunque el Host sea local: si trae `X-Forwarded-For` vino de El Portero,
        y El Portero sólo recibe de internet. Es el candado que sobrevive a que
        alguien agregue el dominio a la lista de locales por error."""
        r = self._get(client, settings, host="localhost", HTTP_X_FORWARDED_FOR="187.189.28.130")
        assert r.status_code == 404

    def test_la_lan_y_el_tailnet_entran(self, client, settings):
        for host in ("127.0.0.1", "100.121.244.5", "192.168.100.95", "10.0.0.7"):
            assert self._get(client, settings, host=host).status_code == 200, host

    def test_una_ip_publica_no_entra(self, client, settings):
        assert self._get(client, settings, host="157.230.48.232").status_code == 404

    @pytest.mark.parametrize("ruta", [
        "/site/vivo/fierro",
        "/site/vivo/peticiones",
        "/site/vivo/contenedores",
        "/site/vivo/negocio",
    ])
    def test_los_paneles_tambien_estan_cerrados(self, client, settings, ruta):
        assert self._get(client, settings, ruta, host="gerencia.learningcenter.mx").status_code == 404
        # Y desde la máquina responden, incluso sin socket de Docker ni /proc:
        # cada panel degrada solo en vez de tumbar la pantalla.
        assert self._get(client, settings, ruta).status_code == 200

    def test_la_pagina_no_acepta_post(self, client, settings):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        assert client.post("/site/vivo/", HTTP_HOST="localhost").status_code == 405


# ── Lectura de los logs de Docker ────────────────────────────────────────────

def _trama(texto: str) -> bytes:
    """Una trama del stream multiplexado de Docker: tipo, 3 ceros, tamaño BE(4)."""
    carga = texto.encode()
    return bytes([1, 0, 0, 0]) + len(carga).to_bytes(4, "big") + carga


class TestDemultiplexado:

    def test_separa_las_tramas(self):
        datos = _trama("primera\n") + _trama("segunda\n")
        assert actividad._demultiplexar(datos) == ["primera", "segunda"]

    def test_un_stream_plano_tambien_se_lee(self):
        """Si el contenedor tuviera TTY, Docker no multiplexa."""
        assert actividad._demultiplexar(b"hola\nmundo\n") == ["hola", "mundo"]

    def test_vacio_no_truena(self):
        assert actividad._demultiplexar(b"") == []


class TestParseo:

    def test_gunicorn_con_duracion(self):
        linea = ('100.75.35.63 - - [21/Aug/2026:22:07:28 -0600] '
                 '"GET /catalogo/ HTTP/1.1" 200 150233 "-" "Safari" 48213')
        d = actividad._parsear_gunicorn(linea)
        assert d["metodo"] == "GET"
        assert d["ruta"] == "/catalogo/"
        assert d["codigo"] == 200
        assert d["bytes"] == 150233
        assert d["ms"] == 48.2  # 48213 microsegundos

    def test_gunicorn_sin_duracion_deja_ms_en_none(self):
        """El formato viejo no la traía. Mejor vacío que un cero que miente."""
        linea = ('1.2.3.4 - - [21/Aug/2026:22:07:28 -0600] '
                 '"POST /x HTTP/1.1" 302 0 "-" "curl"')
        assert actividad._parsear_gunicorn(linea)["ms"] is None

    def test_caddy_del_mostrador(self):
        cuerpo = json.dumps({
            "request": {"method": "GET", "uri": "/medios/ab/cd/x/w400.png"},
            "status": 200, "size": 20773, "duration": 0.002246672,
        })
        d = actividad._parsear_caddy(f"INFO http.log.access.log0 handled request {cuerpo}")
        assert d["ruta"] == "/medios/ab/cd/x/w400.png"
        assert d["codigo"] == 200
        assert d["ms"] == 2.2

    def test_una_linea_que_no_es_peticion_se_ignora(self):
        for basura in ("[INFO] Booting worker with pid: 10",
                       "Traceback (most recent call last):",
                       ""):
            assert actividad._parsear_gunicorn(basura) is None
            assert actividad._parsear_caddy(basura) is None

    def test_la_marca_de_docker_da_el_reloj_comun(self):
        cuando, resto = actividad._marca("2026-08-22T05:23:12.461123456Z el resto")
        assert cuando is not None
        assert cuando.tzinfo is not None
        assert resto == "el resto"

    def test_sin_marca_devuelve_la_linea_entera(self):
        cuando, resto = actividad._marca("no-soy-una-fecha y algo mas")
        assert cuando is None
        assert resto == "no-soy-una-fecha y algo mas"


class TestResumenYRuido:

    def test_el_resumen_cuenta_errores_y_el_pico(self):
        filas = [
            {"codigo": 200, "ms": 2.0},
            {"codigo": 500, "ms": 1200.0},
            {"codigo": 404, "ms": None},
        ]
        r = actividad.resumen(filas)
        assert r["total"] == 3
        assert r["errores"] == 2
        assert r["ms_max"] == 1200.0

    def test_sin_filas_no_divide_entre_cero(self):
        assert actividad.resumen([])["ms_medio"] is None

    def test_las_sondas_y_el_propio_sondeo_son_ruido(self):
        """Sin esto el flujo se llena de /ping cada 10 s y tapa lo real."""
        for ruta in ("/ping", "/salud", "/sistema/aviso-deploy/", "/site/vivo/fierro"):
            assert actividad._RUIDO.match(ruta), ruta
        for ruta in ("/catalogo/", "/medios/ab/cd/x/w400.png", "/proyectos/kanban/"):
            assert not actividad._RUIDO.match(ruta), ruta


class TestMezclaOrdenada:

    def test_lo_mas_reciente_arriba_y_lo_sin_marca_al_final(self, monkeypatch):
        """Las líneas sin marca de tiempo no se descartan: se van al final."""
        ahora = datetime(2026, 8, 22, 5, 0, 0, tzinfo=UTC)
        filas = [
            {"cuando": None, "ruta": "/sin-marca"},
            {"cuando": ahora, "ruta": "/vieja"},
            {"cuando": ahora.replace(second=30), "ruta": "/nueva"},
        ]
        filas.sort(key=lambda f: f["cuando"] or datetime.min.replace(tzinfo=UTC),
                   reverse=True)
        assert [f["ruta"] for f in filas] == ["/nueva", "/vieja", "/sin-marca"]

    def test_sin_socket_devuelve_vacio_sin_lanzar(self, monkeypatch):
        monkeypatch.setattr(actividad, "disponible", lambda: False)
        assert actividad.peticiones() == []
