"""Candado: un deploy verde tiene que haber desplegado (2026-08-24).

El 24 de agosto el despliegue al NUC terminó **en verde dos veces seguidas sin
desplegar nada**. `docker compose up -d` abortaba con «Conflict. The container
name /despacho-osrm is already in use» —un contenedor recreado a mano con
`docker run` nace sin las etiquetas de compose, así que compose no lo adopta,
intenta crear el suyo y choca por el nombre— y el guion seguía adelante sin
mirar el resultado. Como los contenedores VIEJOS seguían sanos, los healthchecks
pasaban al primer intento y el job reportaba «✅ Deploy verde» mientras
producción llevaba horas sirviendo la versión anterior.

Las dos comprobaciones que lo cierran, y por qué hacen falta las DOS:

1. **Mirar el resultado de `up -d`.** Sin esto, cualquier forma futura de fallar
   al recrear vuelve a pasar de largo.
2. **Comparar la imagen que CORRE contra los digests fijados.** Es la única que
   contesta «¿desplegó?»: el healthcheck sólo dice que el sitio contesta, y unos
   contenedores viejos y sanos lo pasan igual.

Es la misma familia que la regla «un job verde puede no haber hecho nada»
(§8, mudanza al NUC): la conclusión no dice si se desplegó — hay que mirar lo
que corre.
"""

from __future__ import annotations

from pathlib import Path

_GUION = Path(__file__).resolve().parent.parent / "infra" / "scripts" / "deploy_nuc.sh"


def _texto() -> str:
    return _GUION.read_text(encoding="utf-8")


def test_el_guion_existe():
    assert _GUION.exists()


def test_up_d_falla_aborta_el_deploy():
    """Sin esto, `up -d` puede abortar y el guion sigue como si nada."""
    t = _texto()
    assert "if ! docker compose $COMPOSE_FILES up -d; then" in t, (
        "El resultado de `up -d` tiene que mirarse: es lo que falló en silencio "
        "el 2026-08-24."
    )
    # Y tiene que TERMINAR, no sólo quejarse: seguir adelante lleva a los
    # healthchecks, que los contenedores viejos pasan.
    bloque = t.split("if ! docker compose $COMPOSE_FILES up -d; then", 1)[1].split("\nfi", 1)[0]
    assert "exit 1" in bloque


def test_se_comprueba_que_la_imagen_que_corre_es_la_fijada():
    """La comprobación que de verdad contesta «¿desplegó?»."""
    t = _texto()
    assert "{{.Config.Image}}" in t, "hay que preguntar qué imagen corre"
    assert 'grep -qF "$CORRIENDO" docker-compose.prod.yml' in t, (
        "y compararla contra los digests que este despliegue trajo"
    )
    assert "EL DEPLOY NO SURTIÓ EFECTO" in t


def test_la_comprobacion_va_despues_de_los_healthchecks_y_antes_de_dar_por_bueno():
    """Orden: primero que responda, luego que sea lo nuevo. Al revés, un arranque
    lento se leería como despliegue fallido."""
    t = _texto()
    assert t.index("Validando healthchecks") < t.index("Comprobando que lo que corre")
    assert t.index("Comprobando que lo que corre") < t.index("Deploy verde")


def test_ninguna_ayuda_del_guion_ejecuta_comandos_por_accidente():
    """Las comillas invertidas dentro de comillas dobles NO son adorno: bash las
    EJECUTA. Escribir la ayuda con ellas habría vuelto a correr
    `docker compose up -d` dentro del propio manejador de error."""
    peligrosas = [ln for ln in _texto().splitlines()
                  if ln.strip().startswith("echo \"") and "`" in ln and "\\`" not in ln]
    assert not peligrosas, f"comillas invertidas sin escapar en: {peligrosas}"
