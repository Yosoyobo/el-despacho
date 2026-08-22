"""La Limpieza — el botón que suelta caché, RAM y disco.

Lo que estas pruebas fijan, en orden de importancia:

1. **Que no se lleve datos por delante.** El caché se borra por llaves y jamás
   con `FLUSHDB`, porque en esta máquina comparte base de datos con la cola del
   Portavoz; la poda de Docker nunca toca volúmenes; y la señal a gunicorn va por
   dentro del contenedor y nunca con `docker kill` (§14 Bug G).
2. **La puerta.** Por el dominio público no existe; desde La Gerencia hace falta
   el permiso `site.limpiar` y el token de CSRF; en la pared, donde no puede
   haber token, hace falta la cabecera de HTMX.
3. **Que nunca truene.** Sin Redis, sin Docker y sin `/proc`, cada paso se
   reporta con su motivo y el botón sigue contestando.
"""

from __future__ import annotations

import json

import pytest

from lib.site import contenedores, limpieza

RUTA = "/site/vivo/limpieza"


# ── Una Libreta de mentiras, para las pruebas del caché ──────────────────────

class LibretaFalsa:
    """Lo mínimo de Redis que usa La Limpieza. Guarda lo que se le borra."""

    def __init__(self, llaves: dict[str, str] | None = None):
        self.datos: dict[str, str] = dict(llaves or {})
        self.borradas: list[str] = []
        self.compactada = False
        self.purgada = False

    # -- caché
    def scan_iter(self, match: str = "*", count: int = 100):
        import fnmatch
        for k in list(self.datos):
            if fnmatch.fnmatch(k, match):
                yield k.encode()

    def unlink(self, *llaves):
        n = 0
        for k in llaves:
            texto = k.decode() if isinstance(k, bytes) else k
            if texto in self.datos:
                del self.datos[texto]
                self.borradas.append(texto)
                n += 1
        return n

    # -- libreta
    def info(self, section: str = ""):
        return {"aof_current_size": 1024}

    def bgrewriteaof(self):
        self.compactada = True

    def execute_command(self, *args):
        if args[:2] == ("MEMORY", "PURGE"):
            self.purgada = True
        return True

    # -- candado y memoria de la última corrida
    def set(self, clave, valor, nx=False, ex=None):
        if nx and clave in self.datos:
            return None
        self.datos[clave] = valor
        return True

    def get(self, clave):
        valor = self.datos.get(clave)
        return valor.encode() if isinstance(valor, str) else valor

    def delete(self, clave):
        self.datos.pop(clave, None)

    def exists(self, clave):
        return 1 if clave in self.datos else 0


@pytest.fixture
def libreta(monkeypatch):
    falsa = LibretaFalsa()
    monkeypatch.setattr(limpieza, "_redis", lambda: falsa)
    return falsa


# ── 1. Lo que no se puede llevar por delante ─────────────────────────────────

class TestNoSeLlevaNadaPorDelante:

    def test_el_cache_no_se_borra_con_flushdb(self):
        """`cache.clear()` del backend de Redis de Django hace `FLUSHDB`, y aquí
        el caché comparte base con la cola del Portavoz (que no caduca): un
        `clear()` se llevaría los eventos pendientes sin dejar rastro.

        Se revisa el ÁRBOL del módulo y no su texto: el encabezado explica la
        regla y menciona las palabras prohibidas a propósito, así que un candado
        que buscara en el texto chocaría con su propia explicación.
        """
        import ast
        from pathlib import Path

        arbol = ast.parse(Path(limpieza.__file__).read_text())
        metodos = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
        for prohibido in ("flushdb", "flushall", "clear"):
            assert prohibido not in metodos, f"La Limpieza no puede llamar a {prohibido}()"
        # Y tampoco mandando el comando crudo por `execute_command`.
        argumentos = {
            a.value.upper()
            for n in ast.walk(arbol) if isinstance(n, ast.Call)
            for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)
        }
        assert not (argumentos & {"FLUSHDB", "FLUSHALL"})

    def test_borra_las_llaves_del_cache_y_deja_la_cola_del_portavoz(
            self, libreta, settings):
        settings.CACHES = {"default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://localhost:6379/15",
        }}
        libreta.datos.update({
            ":1:alias-de-productos": "x",
            ":1:django.contrib.sessions.cacheabc": "y",
            "portavoz:cola": "NO SE TOCA",
            "portavoz:fallidos": "NO SE TOCA",
            "despacho:vigia:pulso:cpu": "NO SE TOCA",
        })
        paso = limpieza.borrar_cache()
        assert paso["estado"] == "ok"
        assert "2" in paso["detalle"]
        assert libreta.datos["portavoz:cola"] == "NO SE TOCA"
        assert libreta.datos["portavoz:fallidos"] == "NO SE TOCA"
        assert libreta.datos["despacho:vigia:pulso:cpu"] == "NO SE TOCA"
        assert sorted(libreta.borradas) == [
            ":1:alias-de-productos", ":1:django.contrib.sessions.cacheabc"]

    def test_la_poda_nunca_toca_volumenes(self):
        """Regla §12 del CLAUDE.md. Hoy los datos viven en bind mounts y un prune
        de volúmenes no los tocaría; el candado se queda para el día en que
        alguien agregue un volumen nombrado."""
        for _, ruta in contenedores._PODAS:
            assert "volume" not in ruta, ruta

    def test_las_imagenes_se_podan_solo_colgantes(self):
        """Con `dangling=false` se borraría cualquier imagen sin contenedor, y eso
        incluye la del despliegue anterior — la que permite volver atrás."""
        rutas = [r for _, r in contenedores._PODAS if "images" in r]
        assert rutas and all("dangling" not in r for r in rutas)

    def test_la_senal_a_gunicorn_no_va_con_docker_kill(self):
        """§14 Bug G: `docker kill` marca el contenedor como «detenido a mano»
        aunque el proceso sobreviva a la señal, y desde ahí `restart:
        unless-stopped` ya no lo levanta tras un apagón. La señal va por un
        `exec` dentro del contenedor."""
        import inspect
        codigo = inspect.getsource(contenedores.reciclar_trabajadores)
        ejecutable = "\n".join(
            ln for ln in codigo.splitlines() if not ln.strip().startswith("#"))
        assert "/kill" not in ejecutable
        assert "/exec" in ejecutable

    def test_el_portavoz_no_esta_entre_los_reciclables(self):
        """Comparte la imagen de La Gerencia pero su PID 1 es Python, no
        gunicorn: para Python la acción por default de SIGHUP es MORIR."""
        nombre = "despacho-portavoz-worker"
        assert not any(f in nombre for f in contenedores._RECICLABLES)
        # Y las apps sí:
        for contenedor in ("despacho-el-taller", "despacho-gerencia"):
            assert any(f in contenedor for f in contenedores._RECICLABLES), contenedor


# ── 2. La puerta ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLaPuerta:

    def _pedir(self, client, settings, metodo="get", host="localhost", **extra):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        return getattr(client, metodo)(RUTA, HTTP_HOST=host, **extra)

    def test_por_el_dominio_publico_no_existe(self, client, settings):
        assert self._pedir(client, settings,
                           host="gerencia.learningcenter.mx").status_code == 404

    def test_desde_la_maquina_se_ve_sin_sesion_y_con_boton(self, client, settings, libreta):
        r = self._pedir(client, settings)
        assert r.status_code == 200
        assert b"La Limpieza" in r.content
        assert b"Limpiar ahora" in r.content

    def test_en_la_pared_un_post_sin_htmx_no_pasa(self, client, settings, monkeypatch):
        """La pared no puede traer token de CSRF (la cookie es `Secure` y no
        viaja por http), así que lo que se exige es la cabecera de HTMX: un
        formulario de otro sitio no puede ponerla, y un `fetch` que sí choca con
        el permiso previo de CORS."""
        corridas = []
        monkeypatch.setattr(limpieza, "limpiar", lambda **k: corridas.append(k) or {})
        r = self._pedir(client, settings, "post")
        assert r.status_code == 403
        assert corridas == [], "no debió correr la limpieza"

    def test_en_la_pared_un_post_de_htmx_corre(self, client, settings, monkeypatch, libreta):
        corridas = []

        def _falsa(**kwargs):
            corridas.append(kwargs)
            return {"cuando": "2026-08-23T10:00:00-06:00", "quien": "la pared",
                    "segundos": 1.0, "liberado_mb": 12.0, "pasos": [], "problemas": 0,
                    "resumen": "liberó 12.0 MB de disco"}

        monkeypatch.setattr(limpieza, "limpiar", _falsa)
        monkeypatch.setattr(limpieza, "ultima", _falsa)
        r = self._pedir(client, settings, "post", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert len(corridas) >= 1
        assert b"liber" in r.content

    def test_un_anonimo_de_internet_no_ve_nada(self, client, settings):
        assert self._pedir(client, settings, "post",
                           host="gerencia.learningcenter.mx").status_code == 404

    def test_desde_la_gerencia_sin_el_permiso_se_ve_pero_no_hay_boton(
            self, client, settings, usuario_factory, libreta):
        from cuentas.models.permiso_usuario import PermisoUsuario
        u = usuario_factory(rol="disenador")
        PermisoUsuario.objects.update_or_create(
            usuario=u, modulo="site", permiso="ver", defaults={"activo": True})
        client.force_login(u)
        r = self._pedir(client, settings, host="gerencia.learningcenter.mx")
        assert r.status_code == 200
        assert b"La Limpieza" in r.content
        assert b"Limpiar ahora" not in r.content, "sin `site.limpiar` no hay botón"
        assert self._pedir(client, settings, "post", host="gerencia.learningcenter.mx",
                           HTTP_HX_REQUEST="true").status_code == 403

    def test_desde_la_gerencia_el_super_admin_si_puede(
            self, client, settings, usuario_factory, monkeypatch, libreta):
        corridas = []
        monkeypatch.setattr(limpieza, "limpiar",
                            lambda **k: corridas.append(k) or {"pasos": [], "problemas": 0})
        monkeypatch.setattr(limpieza, "ultima", lambda: {})
        client.force_login(usuario_factory(rol="super_admin"))
        r = self._pedir(client, settings, "post", host="gerencia.learningcenter.mx",
                        HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert len(corridas) == 1
        assert corridas[0]["quien"], "el evento tiene que decir quién la pidió"

    def test_desde_la_gerencia_sin_token_de_csrf_no_pasa(
            self, settings, usuario_factory, monkeypatch, libreta):
        """El cliente de pruebas desactiva CSRF por default; con la comprobación
        encendida, la petición sin token se rechaza igual que cualquier otro POST
        del sistema. Es lo que impide que la exención del decorador —que existe
        por la pared— abra un hueco en La Gerencia."""
        from django.test import Client
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        monkeypatch.setattr(limpieza, "limpiar",
                            lambda **k: pytest.fail("no debió correr"))
        estricto = Client(enforce_csrf_checks=True)
        estricto.force_login(usuario_factory(rol="super_admin"))
        r = estricto.post(RUTA, HTTP_HOST="gerencia.learningcenter.mx",
                          HTTP_HX_REQUEST="true")
        assert r.status_code == 403

    def test_la_pagina_de_la_pared_sigue_sin_aceptar_post(self, client, settings):
        """El único POST del archivo es el de La Limpieza."""
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        assert client.post("/site/vivo/", HTTP_HOST="localhost").status_code == 405


# ── 3. Que nunca truene ──────────────────────────────────────────────────────

class TestDegradaSinNada:

    def test_sin_redis_el_cache_lo_dice_sin_lanzar(self, monkeypatch, settings):
        settings.CACHES = {"default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://localhost:6379/15",
        }}

        def explota():
            raise RuntimeError("sin Redis")

        monkeypatch.setattr(limpieza, "_redis", explota)
        assert limpieza.borrar_cache()["estado"] == "error"
        assert limpieza.compactar_libreta()["estado"] == "error"
        assert limpieza.ultima() == {}
        assert limpieza.corriendo() is False

    def test_con_el_cache_fuera_de_redis_no_borra_nada(self, settings):
        """En las pruebas (y en cualquier máquina con caché en memoria) el paso
        se declara «no aplica» en vez de barrer llaves ajenas de Redis."""
        settings.CACHES = {"default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique",
        }}
        paso = limpieza.borrar_cache()
        assert paso["estado"] == "no_aplica"

    def test_sin_socket_de_docker_los_dos_pasos_lo_dicen(self, monkeypatch):
        monkeypatch.setattr(contenedores, "disponible", lambda: False)
        paso, bytes_ = limpieza.podar_disco()
        assert paso["estado"] == "no_aplica" and bytes_ == 0
        assert limpieza.reciclar_trabajadores()["estado"] == "no_aplica"

    def test_sin_proc_escribible_lo_dice_en_vez_de_fingir(self):
        """`/proc` se monta en sólo-lectura a propósito; el paso lo declara en vez
        de reportar que soltó un caché que no soltó."""
        paso = limpieza.soltar_paginas()
        assert paso["estado"] in ("no_aplica", "ok")
        if paso["estado"] == "no_aplica":
            assert "nocturno" in paso["detalle"]

    @pytest.mark.django_db
    def test_la_corrida_completa_con_todo_roto_no_lanza(self, monkeypatch, libreta):
        monkeypatch.setattr(contenedores, "disponible", lambda: False)
        res = limpieza.limpiar(quien="oscar@ejemplo.com")
        assert res["quien"] == "oscar@ejemplo.com"
        assert {p["clave"] for p in res["pasos"]} == {
            "cache", "libreta", "base", "disco", "memoria", "paginas"}
        assert res["resumen"]
        assert "cuando" in res and "segundos" in res

    @pytest.mark.django_db
    def test_el_candado_evita_dos_corridas_a_la_vez(self, monkeypatch, libreta):
        monkeypatch.setattr(contenedores, "disponible", lambda: False)
        libreta.datos[limpieza.LLAVE_CANDADO] = "1"   # como si otra estuviera corriendo
        assert limpieza.limpiar() == {"ocupado": True}

    @pytest.mark.django_db
    def test_el_resultado_se_guarda_para_las_dos_pantallas(self, monkeypatch, libreta):
        """La respuesta al botón y el refresco automático tienen que decir lo
        mismo: si el resultado viviera sólo en la respuesta del POST, el siguiente
        refresco lo borraría de la pantalla."""
        monkeypatch.setattr(contenedores, "disponible", lambda: False)
        limpieza.limpiar(quien="oscar@ejemplo.com")
        guardado = json.loads(libreta.datos[limpieza.LLAVE_ULTIMA])
        assert guardado["quien"] == "oscar@ejemplo.com"
        assert limpieza.ultima()["quien"] == "oscar@ejemplo.com"


class TestElTopeDeTiempoSeDevuelve:
    """`CONN_MAX_AGE = 60`: la conexión se reusa en las peticiones siguientes. Un
    `statement_timeout` de 10 s olvidado aquí se les aplicaría a consultas que no
    tienen nada que ver, durante un minuto, y el síntoma sería «a veces un reporte
    truena». Por eso se devuelve en un `finally` — incluso si el aspirado explota.
    """

    class _CursorFalso:
        def __init__(self, diario, revienta_en=""):
            self.diario = diario
            self.revienta_en = revienta_en

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, *a):
            self.diario.append(sql)
            if self.revienta_en and self.revienta_en in sql:
                raise RuntimeError("boom")

        def fetchone(self):
            return ("29 MB",)

    class _ConexionFalsa:
        def __init__(self, diario, revienta_en=""):
            self.diario = diario
            self.revienta_en = revienta_en

        def get_autocommit(self):
            return True

        def cursor(self):
            return TestElTopeDeTiempoSeDevuelve._CursorFalso(
                self.diario, self.revienta_en)

    def _correr(self, monkeypatch, revienta_en=""):
        diario: list[str] = []
        conexion = self._ConexionFalsa(diario, revienta_en)
        import django.db
        monkeypatch.setattr(django.db, "connection", conexion)
        paso = limpieza.aspirar_la_base()
        return diario, paso

    def test_se_devuelve_cuando_todo_sale_bien(self, monkeypatch):
        diario, paso = self._correr(monkeypatch)
        assert any("VACUUM" in s for s in diario)
        assert any("statement_timeout = DEFAULT" in s for s in diario)
        assert paso["estado"] == "ok"

    def test_se_devuelve_aunque_el_aspirado_explote(self, monkeypatch):
        diario, paso = self._correr(monkeypatch, revienta_en="VACUUM")
        assert any("statement_timeout = DEFAULT" in s for s in diario), (
            "el tope se quedaría pegado en una conexión que se reusa"
        )
        assert paso["estado"] == "error"

    def test_dentro_de_una_transaccion_no_lo_intenta(self, monkeypatch):
        """`VACUUM` no corre dentro de una transacción: si alguien pusiera
        `ATOMIC_REQUESTS`, esto lo dice en vez de reventar."""
        class _EnTransaccion:
            def get_autocommit(self):
                return False

        import django.db
        monkeypatch.setattr(django.db, "connection", _EnTransaccion())
        assert limpieza.aspirar_la_base()["estado"] == "no_aplica"


# ── 4. Las dos pantallas, a la par ───────────────────────────────────────────

class TestLasDosPantallasLoTienen:
    """Regla §22. El botón vive en un partial compartido y las dos páginas lo
    piden al mismo endpoint: si alguien lo quitara de una, esto lo caza."""

    def _leer(self, nombre):
        from pathlib import Path
        return (Path(__file__).resolve().parents[2] / "la-gerencia" / "templates"
                / "site" / nombre).read_text()

    def test_la_pared_y_el_site_piden_la_limpieza(self):
        for pagina in ("vivo.html", "tablero.html"):
            assert "site-vivo-limpieza" in self._leer(pagina), pagina

    def test_el_boton_vive_en_un_solo_lugar(self):
        """Si el botón estuviera escrito en cada página serían dos copias, y dos
        copias divergen."""
        partial = self._leer("vivo/_limpieza.html")
        assert "hx-post" in partial and "Limpiar ahora" in partial
        for pagina in ("vivo.html", "tablero.html"):
            assert "Limpiar ahora" not in self._leer(pagina), pagina

    def test_el_aviso_de_que_esta_trabajando_vive_en_la_hoja_compartida(self):
        """Si el estilo viviera en una de las dos pantallas, en la otra el botón
        se quedaría mudo mientras corre."""
        from pathlib import Path
        css = (Path(__file__).resolve().parents[2] / "la-gerencia" / "static"
               / "css" / "vigia-paneles.css").read_text()
        assert "[data-limpieza].htmx-request" in css


# ── 5. El Chalán lo puede consultar (regla del repo: toda herramienta nueva) ──

class TestElChalanPuedePreguntar:
    """Regla del proyecto: una herramienta nueva se declara en el contrato de
    capacidades y se documenta cómo se usa con El Chalán. Aquí la capacidad es de
    LECTURA a propósito: correr la limpieza es un botón de la pantalla, no algo
    que se dispare por chat — el mismo criterio que los barridos de aprendizajes.
    """

    def test_la_capacidad_esta_registrada_y_es_de_lectura(self):
        from capacidades.lecturas import _LECTURAS
        cap = _LECTURAS.get("ultima_limpieza")
        assert cap is not None, "la capacidad no está en el contrato"
        assert cap.modo == "lectura"
        assert cap.gating == "abierto", "el estado de la máquina lo ve cualquiera"

    def test_contesta_sin_haberse_corrido_nunca(self, monkeypatch):
        from capacidades.lecturas import _LECTURAS
        monkeypatch.setattr(limpieza, "ultima", dict)
        monkeypatch.setattr(limpieza, "corriendo", lambda: False)
        r = _LECTURAS["ultima_limpieza"].fn({}, None)
        assert r["hubo_corrida"] is False
        assert "botón" in r["como_se_corre"]

    def test_cuenta_lo_que_liberó_la_última(self, monkeypatch):
        from capacidades.lecturas import _LECTURAS
        monkeypatch.setattr(limpieza, "ultima", lambda: {
            "cuando": "2026-08-23T10:00:00-06:00", "quien": "oscar@ejemplo.com",
            "segundos": 3.4, "liberado_mb": 128.3, "problemas": 0,
            "resumen": "liberó 128.3 MB de disco",
            "pasos": [{"clave": "cache", "titulo": "x", "estado": "ok", "detalle": ""}],
        })
        monkeypatch.setattr(limpieza, "corriendo", lambda: False)
        r = _LECTURAS["ultima_limpieza"].fn({}, None)
        assert r["liberado_mb"] == 128.3
        assert r["pasos"] == {"cache": "ok"}

    def test_esta_en_el_catalogo_que_ve_la_gente(self):
        """Si no está aquí, El Chalán no sabe que puede contestarlo y nadie sabe
        que existe la pregunta."""
        from lib.dictado_catalogo import CONSULTAS_CHAT
        nombres = " ".join(c["nombre"] for c in CONSULTAS_CHAT)
        assert "ultima_limpieza" in nombres


class TestElHaceUnRato:
    """«hace 0 minutos» es lo que devuelve `timesince` para lo que acaba de
    pasar, y es justo el momento en que más gente va a leer ese renglón: se lee
    como un error. Se vio MIRANDO la pantalla, no el código."""

    def test_lo_recien_hecho_no_dice_cero_minutos(self):
        from apps.el_site.views_vivo import _hace
        from django.utils import timezone
        assert _hace(timezone.now()) == "hace un momento"

    def test_un_rato_largo_se_cuenta(self):
        from datetime import timedelta

        from apps.el_site.views_vivo import _hace
        from django.utils import timezone
        texto = _hace(timezone.now() - timedelta(minutes=17))
        assert "17" in texto and texto.startswith("hace ")

    def test_los_relojes_desfasados_no_producen_un_negativo(self):
        from datetime import timedelta

        from apps.el_site.views_vivo import _hace
        from django.utils import timezone
        assert _hace(timezone.now() + timedelta(minutes=3)) == "hace un momento"

    def test_una_marca_ilegible_no_tumba_el_renglon(self):
        from apps.el_site.views_vivo import _con_fecha
        assert _con_fecha({}) == {}
        assert "hace" not in _con_fecha({"cuando": "no-soy-fecha"})
        assert "hace" not in _con_fecha({"quien": "x"})


class TestElResumenSeLeeComoEspanol:
    """«1 paso(s) con problemas» se lee como un error de programa. Lo va a leer
    una persona desde tres metros, así que se conjuga."""

    def _resumen(self, **cambios):
        base = {"liberado_mb": 0, "problemas": 0, "pasos": []}
        return limpieza._resumir({**base, **cambios})

    def test_un_paso_no_lleva_parentesis(self):
        assert self._resumen(problemas=1).endswith("1 paso con problemas")

    def test_dos_pasos_van_en_plural(self):
        assert self._resumen(problemas=2).endswith("2 pasos con problemas")

    def test_el_cache_se_redacta_como_frase(self):
        """El resumen no repite el texto del paso: dice «liberó 1,204 llaves de
        caché», que se lee después del verbo."""
        linea = self._resumen(pasos=[
            {"clave": "cache", "titulo": "x", "estado": "ok",
             "detalle": "1,204 llaves borradas", "n": 1204}])
        assert linea == "liberó 1,204 llaves de caché"

    def test_sin_nada_que_soltar_lo_dice(self):
        assert self._resumen() == "no había nada que soltar"

    def test_sin_nada_pero_con_un_fallo_tambien_lo_dice(self):
        """Antes los problemas sólo se contaban si además se había liberado
        algo: una corrida que sólo falló decía «no había nada que soltar»."""
        assert self._resumen(problemas=1) == "no había nada que soltar · 1 paso con problemas"


@pytest.mark.django_db
class TestLaParedNoSePuedeCongelar:
    """`hx-confirm` usa `window.confirm`, que BLOQUEA el JavaScript de la página.
    En un muro eso significa que si alguien abre la pregunta y se va, la pantalla
    se queda congelada —sin refrescar nada y sin poder ni avisarlo— hasta que
    alguien vuelva. Así que la pregunta va sólo fuera de la pared."""

    def _pedir(self, client, settings, host):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        return client.get(RUTA, HTTP_HOST=host)

    def test_en_la_pared_no_hay_pregunta(self, client, settings, libreta):
        assert b"hx-confirm" not in self._pedir(client, settings, "localhost").content

    def test_desde_la_gerencia_si_pregunta(self, client, settings, usuario_factory, libreta):
        client.force_login(usuario_factory(rol="super_admin"))
        cuerpo = self._pedir(client, settings, "gerencia.learningcenter.mx").content
        assert b"hx-confirm" in cuerpo


class TestElPresupuestoDeTiempo:
    """Gunicorn mata al trabajador que no contesta en 30 s (su default). El
    presupuesto se mide contra lo que UNA poda más podría tardar, no contra lo ya
    transcurrido: si se midiera así, arrancar una poda justo antes del límite
    sumaría un tiempo de espera entero por encima del presupuesto."""

    def test_no_arranca_una_poda_que_no_cabe_en_el_presupuesto(self, monkeypatch):
        pedidas: list[str] = []

        def _lento(ruta, cuerpo=None, **kw):
            pedidas.append(ruta)
            return {"SpaceReclaimed": 0}

        monkeypatch.setattr(contenedores, "disponible", lambda: True)
        monkeypatch.setattr(contenedores, "_post", _lento)
        res = contenedores.podar(timeout=8.0, presupuesto_s=4.0)
        assert pedidas == [], "con 4 s de presupuesto y 8 s de espera no cabe ninguna"
        assert len(res["fallos"]) == len(contenedores._PODAS)

    def test_con_presupuesto_de_sobra_corren_todas(self, monkeypatch):
        pedidas: list[str] = []
        monkeypatch.setattr(contenedores, "disponible", lambda: True)
        monkeypatch.setattr(contenedores, "_post",
                            lambda ruta, cuerpo=None, **kw: pedidas.append(ruta) or {})
        contenedores.podar(timeout=1.0, presupuesto_s=60.0)
        assert len(pedidas) == len(contenedores._PODAS)

    def test_lo_que_mas_libera_va_primero(self):
        """La poda parcial sólo es segura si el orden es el correcto: contenedores
        e imágenes liberan espacio de verdad; la caché de construcción, en este
        servidor, está vacía (aquí no se compila — regla §4 #4)."""
        rutas = [r for _, r in contenedores._PODAS]
        assert "containers" in rutas[0] and "build" in rutas[-1]


class TestLaReservaDelReciclado:
    """El reciclado va al final y es lo único que devuelve RAM. Si el
    presupuesto se repartiera por orden de llegada, una poda lenta se comería
    justo el paso que le da sentido al botón."""

    def test_el_reciclado_tiene_su_pedazo_apartado(self):
        assert limpieza.RESERVA_RECICLADO_S > 0
        assert limpieza.RESERVA_RECICLADO_S < limpieza.PRESUPUESTO_S

    def test_la_poda_no_puede_usar_la_reserva(self, monkeypatch):
        pedido = {}
        monkeypatch.setattr(limpieza, "borrar_cache", lambda: limpieza._paso("cache", "x", "nada"))
        monkeypatch.setattr(limpieza, "compactar_libreta", lambda: limpieza._paso("libreta", "x", "nada"))
        monkeypatch.setattr(limpieza, "aspirar_la_base", lambda: limpieza._paso("base", "x", "nada"))
        monkeypatch.setattr(limpieza, "soltar_paginas", lambda: limpieza._paso("paginas", "x", "nada"))
        monkeypatch.setattr(limpieza, "reciclar_trabajadores",
                            lambda: limpieza._paso("memoria", "x", "nada"))

        def _espia(*, presupuesto_s):
            pedido["presupuesto"] = presupuesto_s
            return limpieza._paso("disco", "x", "nada"), 0

        monkeypatch.setattr(limpieza, "podar_disco", _espia)
        monkeypatch.setattr(limpieza, "_tomar_candado", lambda: True)
        monkeypatch.setattr(limpieza, "_soltar_candado", lambda: None)
        monkeypatch.setattr(limpieza, "_guardar", lambda r: None)
        limpieza.limpiar()
        techo = limpieza.PRESUPUESTO_S - limpieza.RESERVA_RECICLADO_S
        assert pedido["presupuesto"] <= techo

    def test_el_reciclado_no_arranca_lo_que_no_cabe(self, monkeypatch):
        llamadas: list[str] = []
        monkeypatch.setattr(contenedores, "disponible", lambda: True)
        monkeypatch.setattr(contenedores, "listar", lambda: [
            {"id": "aaa", "nombre": "despacho-el-taller", "estado": "running"},
            {"id": "bbb", "nombre": "despacho-gerencia", "estado": "running"},
        ])
        monkeypatch.setattr(contenedores, "_post",
                            lambda *a, **k: llamadas.append(a[0]) or {"Id": "x"})
        res = contenedores.reciclar_trabajadores(timeout=4.0, presupuesto_s=1.0)
        assert llamadas == [], "con 1 s de presupuesto y 4 s de espera no cabe ninguno"
        assert len(res["fallos"]) == 2


class TestElTamanoDeLaBaseSeComparaEnBytes:
    """`pg_size_pretty` devuelve texto («29 MB»), y comparar textos dice que
    «9 MB» es mayor que «31 MB»: el renglón afirmaría que la base bajó cuando
    creció. Los bytes son para comparar; el texto, para mostrar."""

    def _correr(self, monkeypatch, antes, despues):
        filas = iter([antes, despues])

        class _Cursor:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def execute(self, sql, *a):
                self._es_tamano = "pg_database_size" in sql
            def fetchone(self):
                return next(filas) if getattr(self, "_es_tamano", False) else None

        class _Conexion:
            def get_autocommit(self): return True
            def cursor(self): return _Cursor()

        import django.db
        monkeypatch.setattr(django.db, "connection", _Conexion())
        return limpieza.aspirar_la_base()

    def test_no_dice_que_bajo_cuando_creció(self, monkeypatch):
        paso = self._correr(monkeypatch, (9_000_000, "9 MB"), (31_000_000, "31 MB"))
        assert "bajó" not in paso["detalle"]
        assert "31 MB" in paso["detalle"]

    def test_dice_que_bajo_cuando_de_verdad_bajo(self, monkeypatch):
        paso = self._correr(monkeypatch, (31_000_000, "31 MB"), (29_000_000, "29 MB"))
        assert paso["detalle"] == "bajó de 31 MB a 29 MB"


@pytest.mark.django_db
class TestElTokenSoloDondeSirve:
    """En la pared la cookie de CSRF es `Secure` y no viaja por http, así que
    pedir el token no sirve de nada y además haría que cada refresco del renglón
    cargara un `Set-Cookie` que el navegador va a tirar."""

    def _pedir(self, client, settings, host):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        return client.get(RUTA, HTTP_HOST=host)

    def test_la_pared_no_pide_token_ni_cookie(self, client, settings, libreta):
        r = self._pedir(client, settings, "localhost")
        assert b"X-CSRFToken" not in r.content
        assert "gerencia_csrftoken" not in r.cookies

    def test_desde_la_gerencia_el_token_va_en_la_cabecera(
            self, client, settings, usuario_factory, libreta):
        client.force_login(usuario_factory(rol="super_admin"))
        assert b"X-CSRFToken" in self._pedir(
            client, settings, "gerencia.learningcenter.mx").content


class TestLaPodaNoDiceQueSalioBienSiNoSalio:
    """«0 MB liberados · con problemas: …» se lee como que salió bien. Si no se
    liberó nada Y además falló, el paso es un fallo."""

    def test_todo_fallado_es_un_fallo(self, monkeypatch):
        monkeypatch.setattr(contenedores, "podar", lambda **k: {
            "disponible": True, "liberado_bytes": 0, "liberado_mb": 0.0,
            "detalle": [], "fallos": ["contenedores parados: docker API 500"]})
        paso, bytes_ = limpieza.podar_disco()
        assert paso["estado"] == "error" and bytes_ == 0
        assert "500" in paso["detalle"]

    def test_nada_que_podar_no_es_un_fallo(self, monkeypatch):
        monkeypatch.setattr(contenedores, "podar", lambda **k: {
            "disponible": True, "liberado_bytes": 0, "liberado_mb": 0.0,
            "detalle": [], "fallos": []})
        paso, _ = limpieza.podar_disco()
        assert paso["estado"] == "nada"

    def test_algo_liberado_con_un_fallo_lo_dice_sin_esconderlo(self, monkeypatch):
        monkeypatch.setattr(contenedores, "podar", lambda **k: {
            "disponible": True, "liberado_bytes": 5_242_880, "liberado_mb": 5.0,
            "detalle": ["3 contenedores parados"], "fallos": ["caché de construcción: no alcanzó el tiempo"]})
        paso, bytes_ = limpieza.podar_disco()
        assert paso["estado"] == "ok" and bytes_ == 5_242_880
        assert "con problemas" in paso["detalle"]
