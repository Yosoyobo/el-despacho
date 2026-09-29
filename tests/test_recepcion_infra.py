"""La Recepción encendida en producción: compose, NUC, ventana, Caddy, deploy.

Cada prueba es una trampa que ya mordió en el repo (§14): una app compartida
sin su COPY (Bug A), un segundo `migrate` (Bug B), un deploy verde que no
desplegó (Bug J), un bloque de Caddy que dice «Próximamente» con el contenedor
arriba.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent


def _leer(ruta: str) -> str:
    return (RAIZ / ruta).read_text(encoding="utf-8")


def _compose(ruta: str) -> dict:
    return yaml.safe_load(_leer(ruta))


def _installed_apps_recepcion() -> list[str]:
    arbol = ast.parse(_leer("la-recepcion/la_recepcion/settings.py"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign) and any(getattr(t, "id", "") == "INSTALLED_APPS" for t in nodo.targets):
            return [e.value for e in nodo.value.elts]
    raise AssertionError("sin INSTALLED_APPS")


# ── Bug A: cada app instalada tiene su COPY ──────────────────────────────────


def test_cada_app_de_la_recepcion_tiene_su_copy_en_el_dockerfile():
    docker = _leer("la-recepcion/Dockerfile")
    for app in _installed_apps_recepcion():
        if app.startswith("django."):
            continue
        raiz = app.split(".")[0]
        if raiz == "apps":
            carpeta = app.split(".")[1]
            if carpeta == "portal_cliente":
                continue  # vive en la-recepcion/, que se copia entero
            assert f"COPY el-taller/apps/{carpeta}/ /app/apps/{carpeta}/" in docker, app
        else:
            assert f"COPY {raiz}/ /app/{raiz}/" in docker, app


def test_la_app_raiz_portal_se_copia_en_las_tres_imagenes():
    for dockerfile in ("el-taller/Dockerfile", "la-gerencia/Dockerfile", "la-recepcion/Dockerfile"):
        assert "COPY portal/ /app/portal/" in _leer(dockerfile), dockerfile


def test_la_caja_es_opcional_en_la_imagen():
    """Sin su carpeta el build no truena, y `settings` pregunta por el módulo."""
    docker = _leer("la-recepcion/Dockerfile")
    assert "COPY el-taller/apps/caja/" not in docker
    assert "COPY --from=opcionales /opt/caja/ /app/apps/caja/" in docker
    assert 'find_spec("apps.caja.apps")' in _leer("la-recepcion/la_recepcion/settings.py")


# ── Bug B: sólo La Gerencia migra ───────────────────────────────────────────


def test_la_recepcion_no_corre_migrate_y_la_gerencia_si_migra_el_portal():
    entry = _leer("la-recepcion/entrypoint.sh")
    comandos = [ln for ln in entry.splitlines() if not ln.strip().startswith("#")]
    assert not any("migrate" in ln for ln in comandos)
    assert '"portal.apps.PortalConfig"' in _leer("la-gerencia/la_gerencia/settings.py")
    assert "migrate --noinput" in _leer("la-gerencia/entrypoint.sh")


def test_compose_la_enciende_y_espera_a_la_gerencia():
    svc = _compose("docker-compose.yml")["services"]["la-recepcion"]
    assert "profiles" not in svc, "La Recepción sigue apagada por profile"
    assert svc["depends_on"]["la-gerencia"]["condition"] == "service_healthy"
    assert svc["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert "8002/ping" in " ".join(svc["healthcheck"]["test"])
    portero = _compose("docker-compose.yml")["services"]["el-portero"]
    assert portero["depends_on"]["la-recepcion"]["condition"] == "service_healthy"


def test_el_nuc_la_publica_por_el_tailnet_y_la_ventana_la_alcanza():
    nuc = _compose("docker-compose.nuc.yml")["services"]["la-recepcion"]
    assert "8203:8002" in nuc["ports"]
    assert nuc["restart"] == "always"  # §14 Bug G: vuelve sola tras un apagón
    ventana = _compose("docker-compose.ventana.yml")["services"]["el-portero"]["environment"]
    assert ventana["UPSTREAM_RECEPCION"] == "100.121.244.5:8203"
    usados = set()
    for s in _compose("docker-compose.nuc.yml")["services"].values():
        for p in s.get("ports", []) or []:
            if isinstance(p, str):
                usados.add(p.split(":")[0])
    assert "8203" in usados


def test_caddy_manda_la_recepcion_al_nuc_con_failover():
    caddy = _leer("Caddyfile")
    bloque = caddy.split("recepcion.learningcenter.mx {", 1)[1].split("\n}\n", 1)[0]
    assert "reverse_proxy {$UPSTREAM_RECEPCION:la-recepcion:8002}" in bloque
    assert "import lc_failover" in bloque
    assert "respond *" not in bloque and "Próximamente" not in bloque
    # La validación de la ventana tiene que conocer la variable nueva.
    assert "UPSTREAM_RECEPCION=x:1" in _leer(".github/workflows/el-mensajero.yml")
    assert "UPSTREAM_RECEPCION=x:1" in _leer("ops/ventana/aplicar.sh")


# ── Bug J: el deploy comprueba que lo que corre es lo nuevo ─────────────────


def test_el_deploy_comprueba_la_imagen_de_la_recepcion():
    guion = _leer("infra/scripts/deploy_nuc.sh")
    lazo = re.search(r"for svc in ([^;]+); do\n  CID=", guion)
    assert lazo and "la-recepcion" in lazo.group(1).split()
    assert "recepcion.learningcenter.mx" in guion  # y su /ping entra a los healthchecks


def test_la_cadena_completa_de_la_ventana_prueba_la_recepcion():
    ci = _leer(".github/workflows/el-mensajero.yml")
    assert "for h in gerencia taller recepcion; do" in ci


def test_el_vigia_cuenta_las_peticiones_de_la_recepcion():
    from lib.site.actividad import SERVICIOS
    from lib.site.contenedores import bautizar

    assert ("despacho-la-recepcion", "Recepción") in SERVICIOS
    assert bautizar("despacho-la-recepcion")[0] == "La Recepción"


def test_la_cadena_de_middleware_de_las_pruebas_es_la_de_verdad():
    """`tests/recepcion/conftest.py` reproduce el middleware de La Recepción:
    si el de verdad cambia y las pruebas no, estarían probando otro portal."""
    from tests.recepcion.conftest import CONTEXT_PROCESSORS_RECEPCION, MIDDLEWARE_RECEPCION

    settings_txt = _leer("la-recepcion/la_recepcion/settings.py")
    for mw in MIDDLEWARE_RECEPCION:
        assert f'"{mw}"' in settings_txt, mw
    assert "django.contrib.auth.middleware.AuthenticationMiddleware" not in settings_txt
    for cp in CONTEXT_PROCESSORS_RECEPCION:
        assert f'"{cp}"' in settings_txt, cp
    assert 'SESSION_COOKIE_NAME = "recepcion_session"' in settings_txt
