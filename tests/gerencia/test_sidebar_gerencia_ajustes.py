"""El menú de La Gerencia enseña las cuatro configuraciones que antes vivían
escondidas detrás de los botones del panel de Los Ajustes: Cartero, KPIs,
Rutas y Cobranza (LC 2026-08-24, pedido de Oscar).

**Por qué el menú se renderiza a mano y no se lee de una respuesta del
cliente:** los dos `templates/` están en el mismo `DIRS` y el de El Taller va
primero, así que `_componentes_tailadmin/sidebar.html` resuelve al de EL TALLER
incluso en las pruebas de La Gerencia. Leer el menú de una respuesta daría
verde sin haber mirado nunca el archivo que se está probando. Aquí se abre el
archivo de La Gerencia por su ruta y se pinta con un contexto armado.

Lo que fija cada prueba:

* que los cuatro renglones existan **con su nombre esterilizado** (sin
  artículo, sin paréntesis explicativo) — el menú es donde se busca, y un
  nombre distinto al de la pantalla se lee como otra cosa;
* que se gateen con el mismo permiso que las páginas a las que llevan
  (`ajustes.acceder`): ofrecer un renglón que devuelve 403 es peor que no
  ofrecerlo;
* que al abrir una de esas páginas **sólo su renglón** quede marcado —
  «Los Ajustes» dejó de prenderse para toda ruta que empiece con
  `/ajustes/`, o se verían dos activos a la vez.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]

MENU = (
    Path(__file__).resolve().parents[2]
    / "la-gerencia"
    / "templates"
    / "_componentes_tailadmin"
    / "sidebar.html"
)

# (etiqueta que se ve en el menú, ruta a la que lleva)
RENGLONES = [
    ("Cartero", "/ajustes/cartero/"),
    ("KPIs", "/ajustes/metas-kpi/"),
    ("Rutas", "/ajustes/rutas/"),
    ("Cobranza", "/ajustes/cobranza/"),
]

TODOS_LOS_MODULOS = {
    "directorio": True, "site": True, "interfono": True,
    "chalanes": True, "ajustes": True, "catalogos": True,
}


def _pintar(usuario, ruta, *, permisos=None):
    from django.template import engines
    from django.test import RequestFactory

    peticion = RequestFactory().get(ruta)
    peticion.user = usuario
    plantilla = engines["django"].from_string(MENU.read_text(encoding="utf-8"))
    return plantilla.render({
        "request": peticion,
        "permisos_modulos": TODOS_LOS_MODULOS if permisos is None else permisos,
    })


def _clases_del_renglon(menu: str, ruta: str) -> str:
    """La etiqueta <a> de esa ruta, hasta el `>` que la cierra."""
    assert f'href="{ruta}"' in menu, f"falta el renglón de {ruta}"
    return menu.split(f'href="{ruta}"', 1)[1].split(">", 1)[0]


@pytest.mark.parametrize("etiqueta,ruta", RENGLONES)
def test_el_menu_ofrece_el_renglon(usuario_factory, etiqueta, ruta):
    menu = _pintar(usuario_factory(rol="super_admin"), "/ajustes/")
    fila = menu.split(f'href="{ruta}"', 1)[1].split("</a>", 1)[0]
    assert etiqueta in fila, f"el renglón de {ruta} no dice «{etiqueta}»"


@pytest.mark.parametrize("etiqueta,ruta", RENGLONES)
def test_el_renglon_lleva_a_una_pagina_que_abre(client, usuario_factory, etiqueta, ruta):
    """Un renglón del menú que devuelve error no está entregado."""
    client.force_login(usuario_factory(rol="super_admin"))
    assert client.get(ruta).status_code == 200


@pytest.mark.parametrize("etiqueta,ruta", RENGLONES)
def test_sin_el_permiso_de_ajustes_no_se_ofrece(usuario_factory, etiqueta, ruta):
    """Mismo gate que la página: quien no puede entrar tampoco lo ve ofrecido."""
    sin_ajustes = dict(TODOS_LOS_MODULOS, ajustes=False)
    menu = _pintar(usuario_factory(rol="disenador"), "/", permisos=sin_ajustes)
    assert f'href="{ruta}"' not in menu


@pytest.mark.parametrize("etiqueta,ruta", RENGLONES)
def test_solo_su_renglon_queda_marcado(usuario_factory, etiqueta, ruta):
    """Estando en la página, «Los Ajustes» NO se prende también."""
    menu = _pintar(usuario_factory(rol="super_admin"), ruta)
    assert "menu-item-active" in _clases_del_renglon(menu, ruta), \
        f"{etiqueta} debería quedar marcado"
    assert "menu-item-active" not in _clases_del_renglon(menu, "/ajustes/"), \
        "«Los Ajustes» se prendió también"


@pytest.mark.parametrize("ruta", ["/ajustes/", "/ajustes/fiscal/", "/ajustes/sidebar/"])
def test_los_ajustes_sigue_marcado_en_sus_propias_subpaginas(usuario_factory, ruta):
    """La excepción de la prueba de arriba no puede dejar huérfanas a las
    sub-páginas que NO tienen su propio renglón (fiscal, orden del menú, …)."""
    menu = _pintar(usuario_factory(rol="super_admin"), ruta)
    assert "menu-item-active" in _clases_del_renglon(menu, "/ajustes/"), ruta
