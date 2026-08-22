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


class TestLosEstaticosQueReferenciaExisten:
    """Candado: en producción `CompressedManifestStaticFilesStorage` **revienta** al
    renderizar si un `{% static %}` apunta a un archivo que no está — no avisa al
    hacer `collectstatic`, avisa con un 500 en la cara del usuario. Y no lo caza ni
    la suite (en pruebas el storage es el simple) ni el smoke test (que no renderiza
    la página). Pasó con `branding/favicon-32.png`, que no existe: el archivo se
    llama `Icono_LC-32.png`.
    """

    def test_cada_static_de_la_pantalla_esta_en_disco(self):
        import re
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        plantilla = raiz / "la-gerencia" / "templates" / "site" / "vivo.html"
        # Lo que NO vive en el repo porque lo genera el build de Docker: el
        # Dockerfile compila `input.css` con el binario de Tailwind (§6). No es un
        # hueco, así que se declara aquí en vez de aflojar la comprobación.
        generados = {"css/tailwind.css"}

        estaticos = re.findall(r"{%\s*static\s+'([^']+)'\s*%}", plantilla.read_text())
        assert estaticos, "¿la plantilla ya no usa {% static %}?"
        faltantes = [
            r for r in estaticos
            if r not in generados and not (raiz / "la-gerencia" / "static" / r).is_file()
        ]
        assert not faltantes, (
            f"estos {{% static %}} no existen en la-gerencia/static/: {faltantes}. "
            "En producción, con el storage de manifest, eso es un 500 al renderizar."
        )


# ── Lo que enseñó la captura de la pantalla real ─────────────────────────────

class TestDefectosQueSoloSeVenEnPantalla:
    """Cuatro defectos que el código no delataba y la captura sí.

    Van juntos porque comparten la lección: una pantalla se revisa MIRÁNDOLA.
    Los cuatro pasaban las pruebas de acceso y de parseo sin problema.
    """

    def test_la_ruta_se_queda_con_el_ancho_sobrante(self):
        """La celda de la ruta llevaba `max-w-0`: con layout automático, las
        columnas `whitespace-nowrap` reclaman su ancho intrínseco y a la ruta le
        quedaban las migajas — se leía «/sit…», o sea el dato más útil del panel
        ilegible con media pantalla vacía al lado."""
        from pathlib import Path
        t = (Path(__file__).resolve().parents[2] / "la-gerencia" / "templates"
             / "site" / "vivo" / "_peticiones.html").read_text()
        assert "table-fixed" in t, "sin `table-fixed` los anchos del colgroup no mandan"
        # Exactamente una columna sin ancho: la del texto, que absorbe el sobrante.
        assert t.count("<col>") == 1, "la columna del texto debe ser la única sin ancho"
        # Y su contenido trunca, para que una ruta larga no desborde la tabla.
        assert "truncate" in t, "sin `truncate` un texto largo desborda la tabla"
        # Ninguna celda pide cero ancho (era la causa del «/sit…»).
        celdas = [ln for ln in t.splitlines() if "<td" in ln]
        assert not [c for c in celdas if "max-w-0" in c], "una celda sigue pidiendo cero ancho"

    def test_la_fecha_del_respaldo_va_en_hora_local_y_separada(self):
        """`|slice:":16"|cut:"T"` pegaba la fecha a la hora («2026-08-2205:03»)
        y dejaba la hora en **UTC**, mientras el reloj de la cabecera va en
        local. Dos relojes en zonas distintas en la misma pared se leen mal:
        «el respaldo corrió a las 5 de la mañana» cuando fueron las 11 de la
        noche."""
        from apps.el_site.views_vivo import _cuando
        from django.utils import timezone

        # Una marca UTC que en México cae el día ANTERIOR: si no se convierte,
        # la prueba lo caza por el día, no sólo por la hora.
        salida = _cuando("2026-08-22T05:03:12+00:00")
        esperado = timezone.localtime(
            datetime(2026, 8, 22, 5, 3, 12, tzinfo=UTC)
        ).strftime("%d/%m %H:%M")
        assert salida == esperado
        assert "T" not in salida
        assert salida.count(":") == 1, f"fecha y hora pegadas: {salida!r}"

    def test_una_marca_ilegible_no_tumba_el_panel(self):
        from apps.el_site.views_vivo import _cuando
        assert _cuando(None) == ""
        assert _cuando("") == ""
        assert _cuando("no-soy-fecha") == "no-soy-fecha"[:16]

    def test_el_hash_del_despliegue_se_acorta(self):
        """Venía completo (64 caracteres) y se comía el renglón. Siete
        identifican el commit, que es para lo que se mira en una pared."""
        from apps.el_site.views_vivo import _fechas_locales
        largo = "84ec4f5138391202f67ed50645fe50c22555480c"
        snap = _fechas_locales({
            "deploy": {"disponible": True, "commit": largo,
                       "creado_en": "2026-08-21T05:35:00+00:00"},
        })
        assert snap["deploy"]["commit_corto"] == largo[:7]
        assert snap["deploy"]["cuando"]

    def test_un_snapshot_sin_esas_llaves_no_truena(self):
        from apps.el_site.views_vivo import _fechas_locales
        assert _fechas_locales({}) == {}
        assert _fechas_locales({"deploy": {"disponible": False}})["deploy"] == {"disponible": False}


# ── El rediseño: quién, qué, a dónde ─────────────────────────────────────────

class TestQuienQueYADonde:
    """El flujo mostraba rutas, que son correctas y son ilegibles desde tres
    metros. Estas pruebas fijan las tres respuestas que ahora da cada renglón."""

    def test_la_ruta_se_traduce_a_lo_que_la_persona_hace(self):
        from lib.site import acciones
        casos = {
            "/proyectos/kanban/":        "Tablero de proyectos",
            "/medios/ab/cd/x/w400.png":  "Foto de producto",
            "/proyectos/44/":            "Ficha de proyecto",
            "/tesoreria/por-cobrar/":    "Cuentas por cobrar y pagar",
            "/recados/buzon/":           "Mi buzón",
            "/checador/api/sync":        "Checadas guardadas sin señal",
        }
        for ruta, esperado in casos.items():
            assert acciones.nombrar(ruta) == esperado, ruta

    def test_lo_especifico_gana_sobre_lo_general(self):
        """El mapa se recorre en orden. Si `/proyectos/` ganara, el tablero y la
        ficha se llamarían igual y la pared perdería el detalle."""
        from lib.site import acciones
        assert acciones.nombrar("/proyectos/kanban/") != acciones.nombrar("/proyectos/")

    def test_una_ruta_que_nadie_mapeo_sale_tal_cual(self):
        """Inventarle un nombre a algo que no se reconoce sería peor que la
        verdad cruda: se leería como si el sistema supiera lo que no sabe."""
        from lib.site import acciones
        assert acciones.nombrar("/algo/nuevo/sin/mapear/") == "/algo/nuevo/sin/mapear/"
        assert acciones.nombrar("") == "?"

    def test_el_quien_es_el_visitante_no_el_proxy(self):
        """Detrás de El Portero, la IP que ve gunicorn es siempre la del proxy.
        La del visitante es el PRIMER salto del X-Forwarded-For; los demás son
        proxies que se fueron agregando."""
        from lib.site import acciones
        assert acciones.quien("187.189.28.130, 10.0.0.1", "100.121.244.5") == "187.189.28.130"
        # Sin XFF (petición directa), la IP del peer es la buena.
        assert acciones.quien("-", "100.121.244.5") == "100.121.244.5"
        assert acciones.quien("", "") == ""

    def test_el_aparato_distingue_los_que_se_disfrazan(self):
        """Edge y Chrome se anuncian los dos como Chrome; iPad se anuncia como
        Macintosh en modo escritorio. El orden del mapa es lo que los separa."""
        from lib.site import acciones
        assert acciones.aparato("Mozilla/5.0 Chrome/120 Safari/537 Edg/120") == "Edge"
        assert acciones.aparato("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Safari/604") == "iPhone"
        assert acciones.aparato("curl/8.4.0") == "Un guion"
        assert acciones.aparato(None) == ""
        assert acciones.aparato("-") == ""

    def test_el_log_de_gunicorn_trae_el_visitante(self):
        """El entrypoint agrega `%({x-forwarded-for}i)s` ANTES de los
        microsegundos: `_RE_MICROS` ancla al final de la línea, así que un campo
        después lo rompería en silencio."""
        linea = ('100.75.35.63 - - [22/Aug/2026:01:34:32 -0600] "GET /catalogo/ HTTP/1.1" '
                 '200 150233 "-" "Mozilla/5.0 (Macintosh) Safari/605" "187.189.28.130" 48213')
        d = actividad._parsear_gunicorn(linea)
        assert d["quien"] == "187.189.28.130"
        assert d["aparato"] == "Safari"
        assert d["ms"] == 48.2

    def test_el_formato_viejo_no_se_pierde(self):
        """Al reciclarse el contenedor quedan líneas del formato anterior en el
        buffer. Se leen igual, con la IP del peer como «quién»."""
        linea = ('100.75.35.63 - - [22/Aug/2026:01:34:32 -0600] "GET /catalogo/ HTTP/1.1" '
                 '200 150233 "-" "curl/8.0" 48213')
        d = actividad._parsear_gunicorn(linea)
        assert d is not None
        assert d["quien"] == "100.75.35.63"
        assert d["ms"] == 48.2

    def test_el_entrypoint_de_las_dos_apps_loguea_el_visitante(self):
        """Sin esto el «quién» sale vacío en producción y el panel miente por
        omisión. Va en las dos apps: son dual-copy (regla §18)."""
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[2]
        for app in ("el-taller", "la-gerencia"):
            t = (raiz / app / "entrypoint.sh").read_text()
            assert "x-forwarded-for" in t, f"{app} no loguea el visitante"
            # Y la duración sigue al final, que es donde la busca el parseador.
            assert t.index("x-forwarded-for") < t.index("%(D)s")


class TestNombresConSentido:
    """Los nombres de contenedor son estériles y no dicen nada a quien mira la
    pared. Cada pieza de El Despacho tiene su nombre y su oficio."""

    def test_cada_pieza_tiene_nombre_y_oficio(self):
        from lib.site.contenedores import bautizar
        casos = {
            "despacho-el-taller":       "El Taller",
            "despacho-gerencia":        "La Gerencia",
            "despacho-el-mostrador":    "El Mostrador",
            "despacho-portavoz-worker": "El Portavoz",
            "despacho-postgres":        "El Archivero",
            "despacho-redis":           "La Libreta",
        }
        for contenedor, nombre in casos.items():
            bautizado, oficio = bautizar(contenedor)
            assert bautizado == nombre, contenedor
            assert oficio, f"{contenedor} sin oficio: el nombre solo no explica nada"

    def test_una_pieza_nueva_sale_con_su_nombre_tecnico(self):
        """Feo y visible, que es la señal correcta para venir a bautizarla —
        mejor que un nombre inventado que oculte que falta."""
        from lib.site.contenedores import bautizar
        assert bautizar("despacho-algo-nuevo") == ("despacho-algo-nuevo", "")


class TestElPulso:
    """La serie corta que dibujan las gráficas. Vive en Redis porque gunicorn
    corre con varios workers: en memoria del proceso, la gráfica saltaría según
    quién atienda el refresco."""

    def test_una_linea_de_un_punto_no_es_una_tendencia(self):
        from lib.site import pulso
        assert pulso.trazo([]) == ""
        assert pulso.trazo([42.0]) == ""
        assert pulso.trazo([None, None]) == ""

    def test_los_porcentajes_se_dibujan_contra_100(self):
        """Con el máximo tomado del dato, un 20% plano llenaría la gráfica y se
        leería como saturación."""
        from lib.site import pulso
        bajo = pulso.trazo([20.0, 20.0, 20.0], alto=30, maximo=100)
        # y = alto - (20/100)*30 = 24 → cerca del piso, que es la verdad.
        assert all(p.split(",")[1] == "24.0" for p in bajo.split(" "))

    def test_sin_tope_la_serie_usa_su_propio_maximo(self):
        """Para milisegundos importa el relieve, no el techo absoluto."""
        from lib.site import pulso
        t = pulso.trazo([10.0, 20.0], alto=30)
        assert t.split(" ")[0].split(",")[1] == "15.0"   # 10 de 20 → mitad
        assert t.split(" ")[1].split(",")[1] == "0.0"    # el máximo, al techo

    def test_un_hueco_no_se_inventa_como_cero(self):
        """Un cero ahí diría «la memoria bajó a 0». El hueco se salta."""
        from lib.site import pulso
        t = pulso.trazo([50.0, None, 50.0], maximo=100)
        assert len(t.split(" ")) == 2, "el hueco no debe aportar un punto"

    def test_el_area_cierra_contra_el_piso(self):
        from lib.site import pulso
        a = pulso.area([10.0, 90.0], ancho=100, alto=30, maximo=100)
        assert a.startswith("0.0,30")   # arranca en el piso
        assert a.endswith("100.0,30")   # y cierra en el piso

    def test_sin_redis_no_truena_ni_inventa(self, monkeypatch):
        """Redis caído es un problema más grande, con su propia alerta. La pared
        sale sin gráficas y con los números grandes intactos."""
        from lib.site import pulso

        def explota(*a, **k):
            raise RuntimeError("sin Redis")

        monkeypatch.setattr(pulso, "_client", explota)
        pulso.anotar("cpu", 50)                    # no lanza
        pulso.anotar_varias({"cpu": 50})           # no lanza
        assert pulso.leer("cpu") == []
        assert pulso.leer_varias(["cpu"]) == {"cpu": []}


class TestPanelesNuevos:
    """Los Chalanes y La ventana. Los dos deben degradar sin base ni internet."""

    def _get(self, client, settings, ruta):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        return client.get(ruta, HTTP_HOST="localhost")

    @pytest.mark.django_db
    def test_los_chalanes_abren_vacios_sin_llamadas(self, client, settings):
        r = self._get(client, settings, "/site/vivo/chalanes")
        assert r.status_code == 200
        assert b"Los Chalanes" in r.content

    @pytest.mark.django_db
    def test_los_chalanes_no_exponen_el_contenido(self, client, settings):
        """La auditoría es hash-only por decisión del proyecto: `AnalistaLog` no
        guarda prompt ni respuesta. La plantilla no puede pedir campos que no
        existen, así que este candado fija la intención."""
        import re
        from pathlib import Path
        t = (Path(__file__).resolve().parents[2] / "la-gerencia" / "templates"
             / "site" / "vivo" / "_chalanes.html").read_text()
        # Se mira lo que se RENDERIZA, no el archivo entero: el comentario que
        # explica la regla menciona las palabras prohibidas, y un candado que
        # busca en todo el texto choca con su propia explicación.
        pintado = " ".join(re.findall(r"\{\{(.*?)\}\}", t))
        for prohibido in ("prompt_texto", "prompt_completo", "respuesta", "contenido"):
            assert prohibido not in pintado, f"la pared no puede pintar {prohibido}"
        assert "huella" in pintado, "la huella del prompt es la prueba de la auditoría"

    @pytest.mark.django_db
    def test_la_ventana_abre_sin_llave_de_digitalocean(self, client, settings, monkeypatch):
        """Sin la llave no se leen las especificaciones, pero las tres puertas se
        sondean igual: eso es lo que de verdad importa saber."""
        monkeypatch.setattr("apps.el_site.views_vivo._sondear_puertas",
                            lambda: [{"nombre": "El Taller", "codigo": 200, "ms": 12, "ok": True}])
        r = self._get(client, settings, "/site/vivo/ventana")
        assert r.status_code == 200
        assert b"La ventana" in r.content

    @pytest.mark.django_db
    def test_los_paneles_nuevos_estan_cerrados_por_fuera(self, client, settings):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        for ruta in ("/site/vivo/chalanes", "/site/vivo/ventana"):
            r = client.get(ruta, HTTP_HOST="gerencia.learningcenter.mx")
            assert r.status_code == 404, ruta


class TestLaEscalaDeLaTendencia:
    """Elegir mal la escala es elegir mal la historia. Oscar lo reportó: «no veo
    que se muevan las tendencias de el RAM ni el almacenamiento»."""

    def test_con_eje_de_cero_a_cien_lo_que_se_mueve_poco_se_aplasta(self):
        """La memoria oscilando medio punto sale como una raya recta: es el
        síntoma que se reportó."""
        from lib.site import pulso
        casi_plana = [25.4, 25.6, 25.5, 25.9]
        ys = [float(p.split(",")[1]) for p in
              pulso.trazo(casi_plana, alto=30, maximo=100).split(" ")]
        assert max(ys) - min(ys) < 0.5, "medio punto de 100 no se ve, y así era"

    def test_con_relieve_ese_medio_punto_se_ve(self):
        from lib.site import pulso
        casi_plana = [25.4, 25.6, 25.5, 25.9]
        ys = [float(p.split(",")[1]) for p in
              pulso.trazo(casi_plana, alto=30, relieve=True).split(" ")]
        assert max(ys) - min(ys) > 10, "con el eje ajustado, la pendiente se ve"

    def test_una_serie_de_verdad_plana_no_inventa_movimiento(self):
        """El relieve amplifica lo que se mueve; lo que NO se mueve tiene que
        seguir quieto, o la pared mentiría."""
        from lib.site import pulso
        ys = {p.split(",")[1] for p in
              pulso.trazo([50.0, 50.0, 50.0], alto=30, relieve=True).split(" ")}
        assert len(ys) == 1, "una serie constante debe salir como una línea recta"

    def test_el_relieve_deja_la_linea_dentro_del_marco(self):
        from lib.site import pulso
        ys = [float(p.split(",")[1]) for p in
              pulso.trazo([0.0, 100.0, 50.0], alto=30, relieve=True).split(" ")]
        assert min(ys) >= 0 and max(ys) <= 30


class TestLosRespaldosSeEncuentran:
    """La ruta estaba cableada a `/opt/el-despacho/backups`, la del droplet. Con
    la mudanza el proyecto pasó a `/mnt/el-despacho` y el panel decía «no existe»
    sin que nada estuviera roto."""

    def test_encuentra_la_carpeta_donde_esté(self, tmp_path, monkeypatch):
        from lib.site import internos
        carpeta = tmp_path / "backups"
        carpeta.mkdir()
        (carpeta / "db-20260821-230351.sql.gz").write_bytes(b"x" * 449106)
        monkeypatch.setattr(internos, "_RUTAS_RESPALDOS", (str(carpeta),))
        r = internos.ultimo_backup_local()
        assert r["disponible"] is True
        assert r["carpeta"] == str(carpeta)
        assert r["cuantos"] == 1

    def test_sin_carpeta_lo_dice_sin_lanzar(self, monkeypatch):
        from lib.site import internos
        monkeypatch.setattr(internos, "_RUTAS_RESPALDOS", ("/no/existe/nunca",))
        monkeypatch.setattr(internos, "_DONDE_BUSCAR_RESPALDOS", ())
        assert internos.ultimo_backup_local()["disponible"] is False


class TestElPanelDelFierroEnLaPrimeraMuestra:
    """`disco_io` devuelve `{disponible: False, motivo: "primera muestra"}` en su
    primera lectura: son contadores acumulados y una sola no es una tasa. El panel
    reventaba con un 500 justo ahí, o sea **en el primer refresco tras recrear el
    contenedor** — el peor momento para descubrirlo, y se descubrió así.

    La causa: la plantilla pasaba `io.escritura_mb_s` como ARGUMENTO de un filtro
    `add:`. Django **no silencia los argumentos de filtro** (a diferencia de las
    variables sueltas), así que una llave ausente levanta `VariableDoesNotExist`.
    Es un patrón que este repo ya tiene documentado como prohibido (§8, jul25-r2)
    y volvió a colarse: por eso el candado.
    """

    @pytest.mark.django_db
    def test_abre_aunque_el_disco_no_tenga_dos_muestras(self, client, settings, monkeypatch):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        from lib.site import host
        # Se fuerza el estado exacto de la primera muestra.
        monkeypatch.setattr(host, "disco_io",
                            lambda: {"disponible": False, "motivo": "primera muestra"})
        r = client.get("/site/vivo/fierro", HTTP_HOST="localhost")
        assert r.status_code == 200, "el panel del fierro no puede caerse por eso"

    def test_ningun_filtro_recibe_una_llave_de_diccionario_como_argumento(self):
        """Candado del patrón, no sólo de este caso. `{{ x|add:y.z }}` con `y.z`
        ausente es un 500; `{{ y.z }}` a secas sale vacío. La diferencia está en
        que el argumento se resuelve sin silenciar."""
        import re
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[2] / "la-gerencia" / "templates" / "site"
        sospechosos = []
        for ruta in list(raiz.rglob("vivo*.html")) + list(raiz.rglob("vivo/*.html")):
            for i, linea in enumerate(ruta.read_text().splitlines(), 1):
                # Un filtro cuyo argumento es `algo.algo` (una llave anidada).
                if re.search(r"\|(add|default|default_if_none|yesno):[a-z_]+\.[a-z_]+", linea):
                    sospechosos.append(f"{ruta.name}:{i}")
        assert not sospechosos, (
            "argumento de filtro con llave anidada — un 500 si la llave falta: "
            + ", ".join(sospechosos)
        )


class TestElTemaYElContraste:
    """La pared se mira de lejos y a veces con el sol encima. Los grises de la
    paleta general del repo —pensados para una pantalla a medio metro— ahí no se
    leen, y no había forma de tener modo claro sin duplicar cada clase."""

    def _plantillas(self):
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[2] / "la-gerencia" / "templates" / "site"
        return [raiz / "vivo.html"] + sorted((raiz / "vivo").glob("*.html"))

    def test_ninguna_plantilla_clava_un_gris_de_texto(self):
        """Un `text-gray-*` clavado no puede cambiar con el tema: en claro queda
        gris claro sobre blanco. Es justo lo que pasó con el riel de los anillos,
        que se quedó negro y el anillo se leía como un aro negro con un trocito
        verde."""
        import re
        malos = []
        for f in self._plantillas():
            for i, linea in enumerate(f.read_text().splitlines(), 1):
                # Sólo dentro de atributos de clase; los comentarios que explican
                # la regla mencionan los nombres a propósito.
                if re.search(r'class="[^"]*\b(text|bg|border|divide)-gray-\d', linea):
                    malos.append(f"{f.name}:{i}")
        assert not malos, (
            "grises clavados: no siguen el tema y en claro no se leen → " + ", ".join(malos)
        )

    def test_los_dos_temas_definen_los_mismos_niveles(self):
        """Si un token existe en oscuro y no en claro, ese texto hereda el valor
        del otro tema y se vuelve ilegible — el modo de falla es exactamente el
        que se reportó."""
        import re
        t = (self._plantillas()[0]).read_text()
        oscuro = set(re.findall(r"^\s*(--vg-[\w-]+):", t.split(':root[data-tema="claro"]')[0], re.M))
        claro = set(re.findall(r"^\s*(--vg-[\w-]+):", t.split(':root[data-tema="claro"]')[1], re.M))
        assert oscuro, "no se encontraron los tokens del tema oscuro"
        assert oscuro == claro, f"faltan en un tema: {oscuro ^ claro}"

    def test_el_tema_se_aplica_antes_del_primer_pintado(self):
        """Si el script viviera al final del <body>, la pared arrancaría con un
        destello del tema equivocado en cada refresco — y una pared parpadeando se
        nota mucho más que una pantalla que alguien abre y cierra."""
        t = (self._plantillas()[0]).read_text()
        cabeza = t[: t.index("</head>")]
        assert "vigia-tema" in cabeza, "el anti-FOUC del tema debe ir en el <head>"

    @pytest.mark.django_db
    def test_la_url_puede_forzar_el_tema(self, client, settings):
        """`?tema=claro` sirve para revisar la pantalla sin ir a picar el botón en
        la máquina, y para arreglarla desde el tailnet si quedó en el que no se ve."""
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        r = client.get("/site/vivo/?tema=claro", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"'tema'" in r.content or b'"tema"' in r.content


class TestElLanzadorNoPeleaConElNavegador:
    """El fullscreen lo pone una extensión de Firefox, instalada a propósito para
    poder SALIR de él y operar el NUC. El lanzador tiene que respetar eso."""

    def _guion(self):
        from pathlib import Path
        return (Path(__file__).resolve().parents[2] / "infra" / "vigia"
                / "vigia-kiosco.sh").read_text()

    def test_no_fuerza_kiosco_ni_perfil_propio(self):
        """`--kiosk` quita la salida del fullscreen que la extensión sí da, y un
        perfil propio abre una segunda instancia: con Firefox como snap el
        `--profile` se ignora, choca con la de la sesión y sale «Firefox is
        running, but is not responding»."""
        # Se mira sólo lo EJECUTABLE: el encabezado del guion explica por qué no
        # se usan esas banderas, y un candado que busque en todo el texto choca
        # con su propia explicación.
        codigo = "\n".join(
            ln for ln in self._guion().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        )
        for prohibido in ("--kiosk", "--new-instance", "--profile", "--user-data-dir"):
            assert prohibido not in codigo, f"el lanzador no debe usar {prohibido}"

    def test_no_vigila_para_relanzar(self):
        """Si relanza solo, cerrar el navegador a mano no sirve de nada: vuelve a
        los diez segundos. Justo lo contrario de poder operar la máquina."""
        g = self._guion()
        assert "pkill" not in g, "el lanzador no debe matar navegadores"
        # Un solo `while` (el de esperar a que la app conteste), no un bucle de
        # vigilancia.
        assert g.count("while true") == 1

    def test_espera_a_que_la_app_conteste_antes_de_abrir(self):
        """Tras un reinicio el escritorio está listo antes que Docker, y nadie
        recarga una pared."""
        g = self._guion()
        assert "curl -sf" in g and "ESPERA_MAX" in g

    def test_llama_al_navegador_por_su_nombre_no_a_xdg_open(self):
        """`xdg-open` obedece al handler de `text/html` del escritorio, y en este
        NUC eso resolvía a LibreOffice: la pared abría un procesador de texto."""
        g = self._guion()
        i_firefox = g.index("for cmd in firefox")
        i_xdg = g.index("xdg-open", i_firefox)
        assert i_firefox < i_xdg, "los navegadores por nombre van ANTES de xdg-open"


class TestLasClasesDeColorExistenEnElCss:
    """Una clase de Tailwind que la plantilla usa y el CSS no generó **no falla**:
    el elemento sale sin color y parece un problema de diseño. Pasó con las barras
    de «Las piezas» (`bg-brand-400`), que se veían como un riel gris vacío.

    Y la trampa de la comprobación: `grep -c` cuenta LÍNEAS, y un CSS minificado
    es una sola línea, así que siempre devuelve 0 o 1 y no dice si la regla existe.
    Hay que buscar la regla completa `.clase{`.
    """

    def test_las_clases_de_fondo_de_color_estan_declaradas(self):
        import re
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[2] / "la-gerencia"
        css = raiz / "static" / "css" / "tailwind.css"
        if not css.is_file():
            pytest.skip("el CSS lo compila el build de Docker (§6)")
        texto = css.read_text()
        usadas = set()
        for f in [raiz / "templates" / "site" / "vivo.html"] + sorted(
                (raiz / "templates" / "site" / "vivo").glob("*.html")):
            usadas |= set(re.findall(
                r"\b(bg-(?:brand|success|warning|error|blue-light|purple|orange)-\d{2,3})\b",
                f.read_text()))
        assert usadas, "¿las plantillas ya no usan fondos de color?"
        faltantes = [c for c in sorted(usadas) if f".{c}{{" not in texto]
        assert not faltantes, (
            f"usadas en las plantillas y NO generadas en el CSS: {faltantes}. "
            "Recompilar Tailwind — sin la regla, el elemento sale sin color y "
            "parece un problema de diseño."
        )
