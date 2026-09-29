"""Candado §4 #23, tercera pieza: la pantalla de mantenimiento explica y se retira.

Cuando el NUC no contesta, El Portero (Caddy, en La Sede) sirve la pantalla del
snippet `(lc_failover)`. Era un literal fijo en el Caddyfile: decir qué entra y qué
falta dependía de editarlo a mano en cada deploy, y retirarlo, de acordarse.
Ahora sale de un ARCHIVO en un directorio montado: la corta del repo
(`infra/mantenimiento/index.html`) o, durante un deploy, la del roadmap
(`data/caddy/mantenimiento/en-curso.html`), que el job `mudanza` escribe antes de
saltar al NUC y borra con un `trap` al terminar.

Qué se exige:
  (a) `lc_failover` sirve el archivo del directorio montado y las sondas siguen
      dando 502 crudo (con Caddy de verdad, si hay Docker);
  (b) el Caddyfile completo es válido para Caddy;
  (c) la mudanza pone el roadmap ANTES del salto al NUC y lo quita al salir por
      cualquier camino, sin cambiar el resultado del deploy;
  (d) las tres pantallas (corta, roadmap y la mínima de reserva) llevan el footer
      «Desarrollado por NoKo Devs» (§4 #21) y las dos de verdad, el video (Oscar).
"""

from __future__ import annotations

import base64
import importlib.util
import os
import re
import shutil
import signal
import socket
import subprocess
import textwrap
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CADDYFILE = RAIZ / "Caddyfile"
CORTA = RAIZ / "infra" / "mantenimiento" / "index.html"
CORTA_PORTAL = RAIZ / "infra" / "mantenimiento" / "index-portal.html"
PLANTILLA = RAIZ / "infra" / "mantenimiento" / "en-curso.plantilla.html"
WORKFLOW = RAIZ / ".github" / "workflows" / "el-mensajero.yml"
COMPOSE = RAIZ / "docker-compose.yml"

FOOTER = re.compile(
    r'Desarrollado por <a href="https://devs\.noko\.mx" target="_blank" rel="noopener"[^>]*>'
    r"NoKo Devs</a>"
)
VIDEO = "youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&amp;mute=1"
PORTAL = "recepcion.learningcenter.mx"


def _modulo():
    ruta = RAIZ / "infra" / "scripts" / "pantalla_mantenimiento.py"
    spec = importlib.util.spec_from_file_location("pantalla_mantenimiento", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _roadmap(**kw) -> str:
    mod = _modulo()
    valores = {
        "version": "2099.01.01",
        "titulo": "Algo nuevo",
        "puntos": ["Uno", "Dos"],
        "commit": "abcdef0123456789",
        "inicio": 1_800_000_000,
    }
    valores.update(kw)
    return mod.armar(**valores)


def _snippet(nombre: str) -> str:
    """El texto de un snippet del Caddyfile, con llaves balanceadas."""
    s = CADDYFILE.read_text(encoding="utf-8")
    ini = s.index(f"({nombre}) {{")
    nivel = 0
    for i in range(ini, len(s)):
        if s[i] == "{":
            nivel += 1
        elif s[i] == "}":
            nivel -= 1
            if nivel == 0:
                return s[ini : i + 1]
    raise AssertionError(f"snippet ({nombre}) sin cerrar")


def _marca(html: str) -> str:
    m = re.search(r'<html[^>]*\sdata-pantalla="([^"]*)"', html)
    assert m, "la pantalla no trae su marca data-pantalla en <html>"
    return m.group(1)


# ── El contenido del roadmap ──────────────────────────────────────────────────


class TestElRoadmapDiceQueEntraYQueFalta:
    def test_con_el_manual_real_dice_la_version_y_el_titulo_de_novedades(self):
        from lib.version import VERSION

        mod = _modulo()
        doc = (RAIZ / "docs" / "DOC_05_MANUAL_USUARIO.md").read_text(encoding="utf-8")
        primero = re.search(r"^## Novedades — (.+?) \(", doc, re.M).group(1)
        titulo, puntos = mod.novedad_reciente(doc)
        assert titulo == primero
        assert puntos, "el bloque de Novedades tiene párrafos: deben salir puntos"
        html = mod.armar(version=mod.version((RAIZ / "lib" / "version.py").read_text()),
                         titulo=titulo, puntos=puntos, commit="0" * 40, inicio=1)
        assert f"Versi&oacute;n {VERSION}" in html
        assert f">{mod.html.escape(primero)}</h2>" in html

    def test_no_quedan_marcadores_sin_llenar(self):
        assert not re.search(r"__[A-Z]+__", _roadmap())

    def test_los_puntos_son_las_negritas_de_cada_parrafo_en_llano(self):
        mod = _modulo()
        doc = textwrap.dedent("""\
            # Manual
            ## Novedades — Cosas nuevas (1 de enero de 2099)

            **La factura se ve en [Ayuda](/ayuda/).** Y el resto del párrafo.

            **El `botón` Guardar ya no brinca:** otra cosa.

            Un párrafo sin negritas. Con segunda oración.

            ## Novedades — Lo de antes (1 de diciembre de 2098)

            **Esto ya no es de este bloque.**
            """)
        titulo, puntos = mod.novedad_reciente(doc)
        assert titulo == "Cosas nuevas"
        assert puntos == [
            "La factura se ve en Ayuda.",
            "El botón Guardar ya no brinca",
            "Un párrafo sin negritas.",
        ]

    def test_no_pasa_de_cuatro_puntos_ni_de_un_renglon_largo(self):
        mod = _modulo()
        cuerpo = "\n\n".join(f"**Punto {i} " + "palabra " * 60 + "**" for i in range(9))
        _, puntos = mod.novedad_reciente(f"## Novedades — T (hoy)\n\n{cuerpo}\n")
        assert len(puntos) == 4
        assert all(len(p) <= mod.MAX_LARGO for p in puntos)

    def test_todo_lo_que_viene_del_manual_se_escapa(self):
        html = _roadmap(titulo='<script>alert("x")</script>', puntos=["<img src=x onerror=y>"])
        assert "<script>alert" not in html
        assert "<img src=x" not in html
        assert "&lt;script&gt;" in html

    def test_la_marca_cambia_con_cada_deploy(self):
        a = _marca(_roadmap(commit="aaaaaaaa11", inicio=10))
        b = _marca(_roadmap(commit="bbbbbbbb22", inicio=10))
        c = _marca(_roadmap(commit="aaaaaaaa11", inicio=20))
        assert len({a, b, c, "corta"}) == 4, "sin marca distinta, la pestaña abierta no se entera"

    def test_trae_la_hora_de_inicio_y_los_tres_pasos(self):
        html = _roadmap(inicio=1_234_567_890)
        assert 'data-inicio="1234567890"' in html
        pasos = re.findall(r'<li data-hasta="(\d+)"><div><b>([^<]+)</b>', html)
        assert [p[1] for p in pasos] == [
            "Bajar la versi&oacute;n nueva",
            "Reiniciar el sistema",
            "Comprobar que todo responde",
        ]
        assert [int(p[0]) for p in pasos] == sorted(int(p[0]) for p in pasos)
        assert 'role="progressbar"' in html

    def test_se_declara_vieja_con_el_mismo_ttl_que_el_banner(self):
        # deploy_nuc.sh abre el banner con ttl_segundos=1800; un roadmap que dura
        # más que su ventana miente.
        assert "ttl_segundos=1800" in (RAIZ / "infra" / "scripts" / "deploy_nuc.sh").read_text()
        assert re.search(r"var CADUCA = 1800;", PLANTILLA.read_text(encoding="utf-8"))

    def test_la_linea_de_comandos_escribe_la_pagina(self, capsys):
        assert _modulo().main(["--commit", "deadbeef", "--inicio", "5"]) == 0
        salida = capsys.readouterr().out
        assert _marca(salida) == "en-curso-deadbeef-5"


# ── (d) Footer y video ───────────────────────────────────────────────────────


class TestLasPantallasLlevanFooterYVideo:
    def test_la_corta_lleva_footer_y_video(self):
        html = CORTA.read_text(encoding="utf-8")
        assert FOOTER.search(html)
        assert VIDEO in html
        assert _marca(html) == "corta"

    def test_la_del_roadmap_lleva_footer_y_video(self):
        html = _roadmap()
        assert FOOTER.search(html)
        assert VIDEO in html

    def test_la_minima_de_reserva_del_caddyfile_lleva_footer(self):
        m = re.search(r"respond `(<!doctype html>.*?)` 503", _snippet("lc_failover"), re.S)
        assert m, "falta la pantalla mínima de reserva en lc_failover"
        assert FOOTER.search(m.group(1))
        assert _marca(m.group(1)) == "minima"

    @pytest.mark.parametrize("ruta", [CORTA, PLANTILLA], ids=["corta", "roadmap"])
    def test_se_recarga_sin_reenviar_formularios(self, ruta):
        html = ruta.read_text(encoding="utf-8")
        assert "location.replace(location.href)" in html
        assert "location.reload" not in html, "reload vuelve a mandar el POST del corte"
        assert "setInterval(revisa, 20000)" in html



class TestElPortalDeClientesVaSinVideo:
    """Decisión de Oscar (2026-09-29): los clientes ven la pantalla de espera SIN
    el video. No es otra página que se pueda quedar atrás: es la misma con el
    bloque del video quitado."""

    def test_la_corta_del_portal_esta_al_dia_con_la_del_equipo(self):
        esperada = _modulo().sin_video(CORTA.read_text(encoding="utf-8"))
        assert CORTA_PORTAL.read_text(encoding="utf-8") == esperada, (
            "infra/mantenimiento/index-portal.html está vieja: regénerala con "
            "`python3 infra/scripts/pantalla_mantenimiento.py --corta --sin-video`")

    @pytest.mark.parametrize("html", [
        pytest.param(lambda: CORTA_PORTAL.read_text(encoding="utf-8"), id="corta"),
        pytest.param(lambda: _roadmap(video=False), id="roadmap"),
    ])
    def test_sin_video_pero_con_footer_y_su_recarga(self, html):
        pagina = html()
        assert "youtube" not in pagina and "<iframe" not in pagina
        assert FOOTER.search(pagina)
        assert "location.replace(location.href)" in pagina
        assert "__" not in pagina.split("<script>")[0].split("-->", 1)[1]

    def test_quitar_el_video_sin_sus_marcas_truena(self):
        with pytest.raises(ValueError):
            _modulo().sin_video("<html><iframe src=x></iframe></html>")

    def test_la_linea_de_comandos_arma_las_dos_variantes(self, capsys):
        mod = _modulo()
        mod.main(["--commit", "abc", "--sin-video"])
        assert "youtube" not in capsys.readouterr().out
        mod.main(["--corta", "--sin-video"])
        assert capsys.readouterr().out == CORTA_PORTAL.read_text(encoding="utf-8")

    def test_el_portero_le_da_al_portal_sus_archivos_y_nunca_los_del_equipo(self):
        s = _snippet("lc_failover")
        rama = s[s.index("handle @portal_clientes {"):]
        rama = rama[: rama.index("\n\t\t}\n")]
        assert "@portal_clientes host recepcion.learningcenter.mx" in s
        assert "try_files /mantenimiento-vivo/en-curso-portal.html /mantenimiento/index-portal.html" in rama
        assert "index.html" not in rama and "en-curso.html" not in rama
        assert "youtube" not in rama
        # Va antes de la pantalla del equipo, y después de las sondas.
        assert s.index("@sondas path") < s.index("handle @portal_clientes") < s.index(
            "try_files /mantenimiento-vivo/en-curso.html")

    def test_la_recepcion_importa_el_failover(self):
        s = CADDYFILE.read_text(encoding="utf-8")
        bloque = s[s.index(f"\n{PORTAL} {{"):]
        assert "import lc_failover" in bloque[: bloque.index("\n}\n")]

    def test_la_mudanza_arma_la_del_portal(self):
        job = _job("mudanza")
        assert "pantalla_mantenimiento.py --commit \"$GITHUB_SHA\" --sin-video > en-curso-portal.html" in job
        assert "PANTALLA_PORTAL_B64: ${{ steps.pantalla.outputs.b64_portal }}" in job
        assert re.search(r"envs: .*\bPANTALLA_PORTAL_B64\b", job)

# ── (a) El Caddyfile sirve el archivo, no un literal ─────────────────────────


class TestLcFailoverSirveElArchivo:
    def test_busca_primero_el_roadmap_y_luego_la_corta(self):
        s = _snippet("lc_failover")
        assert "try_files /mantenimiento-vivo/en-curso.html /mantenimiento/index.html" in s
        assert re.search(r"file_server \{\s*status 503\s*\}", s)
        assert 'header Retry-After "120"' in s

    def test_las_sondas_se_contestan_antes_que_la_pantalla(self):
        s = _snippet("lc_failover")
        assert s.index("@sondas path /ping /salud") < s.index("try_files")
        assert 'respond "upstream unavailable" 502' in s

    def test_ya_no_embute_la_pagina_con_video(self):
        assert VIDEO not in _snippet("lc_failover")

    @pytest.mark.parametrize("host", ["taller.learningcenter.mx", "gerencia.learningcenter.mx"])
    def test_taller_y_gerencia_la_importan(self, host):
        s = CADDYFILE.read_text(encoding="utf-8")
        bloque = s[s.index(f"\n{host} {{") :]
        bloque = bloque[: bloque.index("\n}\n")]
        assert "import lc_failover" in bloque

    def test_el_portero_monta_directorios_no_archivos(self):
        c = COMPOSE.read_text(encoding="utf-8")
        assert "- ./infra/mantenimiento:/srv/mantenimiento:ro" in c
        assert "- ./data/caddy/mantenimiento:/srv/mantenimiento-vivo:ro" in c


def _hay_docker() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


requiere_docker = pytest.mark.skipif(not _hay_docker(), reason="sin Docker no hay Caddy de verdad")


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def portero(tmp_path_factory):
    """Caddy de verdad con el snippet del repo, un upstream muerto y los mismos
    directorios que monta el compose (copiados: Docker Desktop no ve todo disco)."""
    base = tmp_path_factory.mktemp("mant")
    etc, corta, vivo = base / "etc", base / "corta", base / "vivo"
    for d in (etc, corta, vivo):
        d.mkdir()
    shutil.copy(CORTA, corta / "index.html")
    shutil.copy(CORTA_PORTAL, corta / "index-portal.html")
    (etc / "Caddyfile").write_text(
        "{\n\tauto_https off\n\tadmin off\n}\n"
        + _snippet("lc_failover")
        + "\n:8080 {\n\treverse_proxy 127.0.0.1:9\n\timport lc_failover\n}\n",
        encoding="utf-8",
    )
    puerto = _puerto_libre()
    nombre = f"prueba-lc-failover-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", nombre, "-p", f"127.0.0.1:{puerto}:8080",
         "-v", f"{etc}:/etc/caddy:ro",
         "-v", f"{corta}:/srv/mantenimiento:ro",
         "-v", f"{vivo}:/srv/mantenimiento-vivo:ro",
         "caddy:2-alpine"],
        check=True, capture_output=True, timeout=180,
    )
    url = f"http://127.0.0.1:{puerto}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(url + "/ping", timeout=2)
            except urllib.error.HTTPError:
                break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.fail("Caddy no arrancó")
        yield {"url": url, "corta": corta, "vivo": vivo}
    finally:
        subprocess.run(["docker", "rm", "-f", nombre], capture_output=True, timeout=60)


def _pide(url: str, metodo: str = "GET", host: str = "") -> tuple[int, dict, str]:
    datos = b"a=1" if metodo == "POST" else None
    req = urllib.request.Request(url, data=datos, method=metodo)
    if host:
        req.add_header("Host", host)
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, dict(r.headers), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


@requiere_docker
class TestConCaddyDeVerdad:
    def test_sin_deploy_sirve_la_corta_con_503_y_retry_after(self, portero):
        codigo, cab, cuerpo = _pide(portero["url"] + "/proyectos/12/")
        assert codigo == 503
        assert cab.get("Retry-After") == "120"
        assert cab.get("Cache-Control") == "no-store"
        assert cab.get("Content-Type", "").startswith("text/html")
        assert _marca(cuerpo) == "corta"

    @pytest.mark.parametrize("sonda", ["/ping", "/salud"])
    def test_las_sondas_siguen_viendo_la_caida(self, portero, sonda):
        codigo, _, cuerpo = _pide(portero["url"] + sonda)
        assert (codigo, cuerpo) == (502, "upstream unavailable")

    def test_un_formulario_en_el_corte_ve_la_pantalla_y_no_un_405(self, portero):
        codigo, _, cuerpo = _pide(portero["url"] + "/cotizaciones/nueva/", "POST")
        assert codigo == 503
        assert _marca(cuerpo) == "corta"

    def test_con_deploy_sirve_el_roadmap_y_al_quitarlo_vuelve_la_corta(self, portero):
        en_curso = portero["vivo"] / "en-curso.html"
        en_curso.write_text(_roadmap(commit="cafe0000", inicio=7), encoding="utf-8")
        try:
            codigo, _, cuerpo = _pide(portero["url"] + "/")
            assert codigo == 503
            assert _marca(cuerpo) == "en-curso-cafe0000-7"
        finally:
            en_curso.unlink()
        assert _marca(_pide(portero["url"] + "/")[2]) == "corta"

    def test_sin_ningun_archivo_contesta_la_minima_y_no_un_404(self, portero):
        corta = portero["corta"] / "index.html"
        respaldo = corta.read_bytes()
        corta.unlink()
        try:
            codigo, _, cuerpo = _pide(portero["url"] + "/")
            assert codigo == 503
            assert _marca(cuerpo) == "minima"
            assert FOOTER.search(cuerpo)
        finally:
            corta.write_bytes(respaldo)


    # ── El portal de clientes: la misma pantalla, SIN el video ──────────────

    def test_el_portal_ve_su_corta_sin_video(self, portero):
        codigo, cab, cuerpo = _pide(portero["url"] + "/cotizaciones/3/", host=PORTAL)
        assert codigo == 503 and cab.get("Retry-After") == "120"
        assert _marca(cuerpo) == "corta"
        assert VIDEO not in cuerpo and "youtube" not in cuerpo
        assert FOOTER.search(cuerpo)
        # Y el equipo sigue viendo la suya, con video.
        assert VIDEO in _pide(portero["url"] + "/")[2]

    def test_con_deploy_el_portal_ve_su_roadmap_sin_video(self, portero):
        vivo = portero["vivo"]
        (vivo / "en-curso.html").write_text(_roadmap(commit="beef0000", inicio=9), encoding="utf-8")
        (vivo / "en-curso-portal.html").write_text(
            _roadmap(commit="beef0000", inicio=9, video=False), encoding="utf-8")
        try:
            _, _, cuerpo = _pide(portero["url"] + "/", host=PORTAL)
            assert _marca(cuerpo) == "en-curso-beef0000-9"
            assert "youtube" not in cuerpo and FOOTER.search(cuerpo)
            assert VIDEO in _pide(portero["url"] + "/")[2]
        finally:
            for f in ("en-curso.html", "en-curso-portal.html"):
                (vivo / f).unlink()
        assert _marca(_pide(portero["url"] + "/", host=PORTAL)[2]) == "corta"

    def test_el_portal_nunca_cae_a_la_pantalla_con_video(self, portero):
        """Sin sus archivos, la mínima — aunque la del equipo (con video) sí esté."""
        corta = portero["corta"] / "index-portal.html"
        respaldo = corta.read_bytes()
        corta.unlink()
        (portero["vivo"] / "en-curso.html").write_text(_roadmap(), encoding="utf-8")
        try:
            codigo, _, cuerpo = _pide(portero["url"] + "/", host=PORTAL)
            assert codigo == 503 and _marca(cuerpo) == "minima"
            assert "youtube" not in cuerpo and FOOTER.search(cuerpo)
        finally:
            corta.write_bytes(respaldo)
            (portero["vivo"] / "en-curso.html").unlink()

    @pytest.mark.parametrize("sonda", ["/ping", "/salud"])
    def test_las_sondas_del_portal_tambien_ven_la_caida(self, portero, sonda):
        assert _pide(portero["url"] + sonda, host=PORTAL)[:1] == (502,)

# ── (b) El Caddyfile completo es válido ──────────────────────────────────────


@requiere_docker
def test_el_caddyfile_completo_es_valido():
    # Igual que el job `ventana` antes de aplicarlo. Por stdin y no montado:
    # Docker Desktop no comparte todos los discos.
    r = subprocess.run(
        ["docker", "run", "--rm", "-i",
         "-e", "UPSTREAM_TALLER=x:1", "-e", "UPSTREAM_GERENCIA=x:1", "-e", "UPSTREAM_MEDIOS=x:1",
         "-e", "LANDING_ROOT=/srv/lc-fallback", "caddy:2-alpine", "sh", "-c",
         "cat > /etc/caddy/Caddyfile && caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile"],
        input=CADDYFILE.read_bytes(), capture_output=True, timeout=180,
    )
    assert r.returncode == 0, r.stderr.decode()[-2000:]


# ── (c) La mudanza pone el roadmap antes y lo quita siempre ──────────────────


def _job(nombre: str) -> str:
    s = WORKFLOW.read_text(encoding="utf-8")
    ini = s.index(f"\n  {nombre}:\n")
    sig = re.search(r"\n  [a-z_]+:\n", s[ini + 1 :])
    return s[ini : ini + 1 + sig.start()] if sig else s[ini:]


def _script_de_la_mudanza() -> str:
    lineas = _job("mudanza").splitlines()
    i = next(n for n, linea in enumerate(lineas) if linea.strip() == "script: |")
    sangria = len(lineas[i]) - len(lineas[i].lstrip()) + 2
    cuerpo = []
    for linea in lineas[i + 1 :]:
        if linea.strip() and len(linea) - len(linea.lstrip()) < sangria:
            break
        cuerpo.append(linea[sangria:])
    return "\n".join(cuerpo) + "\n"


class TestLaMudanzaPoneYQuitaLaPantalla:
    def test_el_runner_arma_la_pantalla_y_se_la_pasa_a_la_sede(self):
        job = _job("mudanza")
        assert "uses: actions/checkout@v4" in job
        armar = job.index("python3 infra/scripts/pantalla_mantenimiento.py")
        assert armar < job.index("uses: appleboy/ssh-action")
        assert "continue-on-error: true" in job[:armar], "si no se arma, el deploy sigue"
        assert "PANTALLA_B64: ${{ steps.pantalla.outputs.b64 }}" in job
        assert re.search(r"envs: .*\bPANTALLA_B64\b", job)

    def test_el_script_es_bash_valido(self):
        subprocess.run(["bash", "-n"], input=_script_de_la_mudanza().encode(), check=True)

    @pytest.fixture
    def correr(self, tmp_path):
        bin_ = tmp_path / "bin"
        bin_.mkdir()
        log = tmp_path / "log"
        (bin_ / "docker").write_text(
            '#!/bin/sh\necho "docker $*" >> "$LOG"\n'
            'case "$*" in *"cat >"*) cat > "$LOG.stdin" ;; esac\n'
            'exit "${FAKE_DOCKER_RC:-0}"\n'
        )
        (bin_ / "ssh").write_text(
            '#!/bin/sh\necho "ssh $*" >> "$LOG"\n'
            '[ -n "${FAKE_SSH_SLEEP:-}" ] && sleep "$FAKE_SSH_SLEEP"\n'
            'exit "${FAKE_SSH_RC:-0}"\n'
        )
        for f in bin_.iterdir():
            f.chmod(0o755)
        script = tmp_path / "mudanza.sh"
        script.write_text(_script_de_la_mudanza())

        def _correr(pantalla: str | None = "<html>roadmap</html>", fondo=False, **extra):
            env = {
                **os.environ,
                "PATH": f"{bin_}:{os.environ['PATH']}",
                "LOG": str(log),
                "NUC_HOST": "nuc", "NUC_USER": "linux", "SHA": "abc", "CORRIDA": "url",
                **extra,
            }
            env.pop("PANTALLA_B64", None)
            if pantalla is not None:
                env["PANTALLA_B64"] = base64.b64encode(pantalla.encode()).decode()
            if fondo:
                return subprocess.Popen(["bash", str(script)], env=env, start_new_session=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            r = subprocess.run(["bash", str(script)], env=env, capture_output=True, timeout=60)
            return r, (log.read_text().splitlines() if log.exists() else [])

        _correr.log = log
        return _correr

    @staticmethod
    def _orden(lineas: list[str]) -> list[str]:
        def tipo(linea):
            if linea.startswith("ssh "):
                return "ssh"
            if "cat > /m/.en-curso.tmp" in linea:
                return "poner"
            if "rm -f /m/en-curso.html" in linea:
                return "quitar"
            return linea
        return [tipo(linea) for linea in lineas]

    def test_pone_antes_del_salto_y_quita_despues(self, correr):
        r, log = correr()
        assert r.returncode == 0, r.stdout.decode()
        assert self._orden(log) == ["poner", "ssh", "quitar"]
        assert (Path(str(correr.log) + ".stdin")).read_text() == "<html>roadmap</html>"
        assert "/opt/el-despacho/data/caddy/mantenimiento:/m" in log[0]

    def test_pone_y_quita_tambien_la_del_portal(self, correr):
        b64 = base64.b64encode(b"<html>portal</html>").decode()
        r, log = correr(PANTALLA_PORTAL_B64=b64)
        assert r.returncode == 0, r.stdout.decode()
        assert self._orden(log) == ["poner", "ssh", "quitar"]
        assert f"-e P={b64}" in log[0] and "/m/en-curso-portal.html" in log[0]
        assert "/m/en-curso-portal.html" in log[-1]

    def test_si_el_deploy_falla_la_quita_igual_y_el_job_sigue_rojo(self, correr):
        r, log = correr(FAKE_SSH_RC="7")
        assert r.returncode == 7, "quitar la pantalla no puede pintar de verde un deploy rojo"
        assert self._orden(log) == ["poner", "ssh", "quitar"]

    def test_si_no_se_armo_la_pantalla_el_deploy_sigue(self, correr):
        r, log = correr(pantalla=None)
        assert r.returncode == 0
        assert self._orden(log) == ["ssh", "quitar"]

    def test_si_docker_falla_el_deploy_sigue(self, correr):
        r, log = correr(FAKE_DOCKER_RC="1")
        assert r.returncode == 0
        assert self._orden(log) == ["poner", "ssh", "quitar"]
        salida = r.stdout.decode()
        assert "No se pudo poner la pantalla" in salida
        assert "No se pudo quitar la pantalla" in salida

    def test_si_se_corta_la_sesion_la_quita(self, correr):
        p = correr(fondo=True, FAKE_SSH_SLEEP="30")
        try:
            for _ in range(100):
                if correr.log.exists() and "ssh" in correr.log.read_text():
                    break
                time.sleep(0.1)
            os.killpg(p.pid, signal.SIGHUP)
            p.wait(timeout=20)
        finally:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
        assert self._orden(correr.log.read_text().splitlines()) == ["poner", "ssh", "quitar"]
