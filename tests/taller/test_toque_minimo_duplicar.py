"""El botón de duplicar proyecto se puede picar con el dedo (deuda Sep28).

Medido en Chrome a 390 px (móvil, táctil): el ⧉ medía 19×28 en la lista (que en
el celular se vuelve tarjetas) y 13×15 en el Kanban; un dedo que no le atinaba
por poco abría el proyecto en vez de duplicarlo. Con `.toque-minimo` mide 44×44
en pantalla chica y las cuatro esquinas de ese cuadro caen en el botón; en
escritorio (1440 px) sigue midiendo lo mismo que antes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _botones_duplicar(html: str) -> list[str]:
    return re.findall(r'<button[^>]*aria-label="Duplicar proyecto"[^>]*>', html, re.S)


def test_el_modulo_vive_en_la_hoja_y_solo_en_pantalla_chica():
    css = (RAIZ / "el-taller/static/css/input.css").read_text()
    inicio = css.index(".toque-minimo {")
    media = css.rfind("@media", 0, inicio)
    assert "not all and (min-width: 768px)" in css[media:inicio], (
        "fuera de la media query de móvil cambiaría escritorio")
    regla = css[inicio:css.index("}", inicio)]
    assert "min-width: 44px" in regla and "min-height: 44px" in regla


@pytest.mark.django_db
@pytest.mark.taller
@pytest.mark.parametrize("url", ["/proyectos/", "/proyectos/kanban/"])
def test_los_botones_de_duplicar_lo_llevan(client, usuario_factory, proyecto_factory, url):
    client.force_login(usuario_factory(rol="super_admin"))
    proyecto_factory(nombre="Menú de temporada")
    html = client.get(url).content.decode()
    botones = _botones_duplicar(html)
    assert botones, f"{url} no pintó el botón de duplicar"
    for b in botones:
        assert re.search(r'class="[^"]*\btoque-minimo\b', b), b


def test_todo_boton_que_es_solo_el_icono_de_duplicar_lo_lleva():
    """Un botón cuyo único contenido es «⧉» es chico para el dedo por definición:
    sin `.toque-minimo` se vuelve a abrir la fila en vez de duplicar."""
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[2] / "el-taller" / "templates"
    faltan = []
    for html in raiz.rglob("*.html"):
        texto = html.read_text(encoding="utf-8")
        for m in re.finditer(r"<button\b([^>]*)>\s*⧉\s*</button>", texto):
            if not re.search(r'class="[^"]*\btoque-minimo\b', m.group(1)):
                faltan.append(f"{html.relative_to(raiz)}:{texto[:m.start()].count(chr(10)) + 1}")
    assert not faltan, "botones ⧉ sin área táctil de 44×44: " + ", ".join(faltan)
