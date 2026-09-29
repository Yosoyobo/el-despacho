"""«Nuevo asiento»: los campos de las partidas se ven como campos (deuda Sep28).

Las celdas de la tabla de partidas no llevaban `campo-form`, y el preflight de
Tailwind deja los inputs sin borde: la cuenta y los montos se adivinaban por su
contenido («---------», «0.00»), pero la Descripción vacía era un hueco blanco
sin orilla (y en oscuro, rectángulos blancos). Medido en Chrome: borde 0px →
1px en los cuatro, claro y oscuro. Esto fija que las celdas —las del formset y
las de la plantilla que agrega renglones— lleven la clase de campo.
"""

from __future__ import annotations

import re

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

CAMPOS = ("cuenta", "descripcion", "cargo", "abono")


def _clase_de_la_celda(html: str, nombre: str) -> str:
    """La clase del <td> que contiene el campo `nombre`."""
    pos = html.index(f'name="{nombre}"')
    td = html.rfind("<td", 0, pos)
    assert td != -1 and "</td>" not in html[td:pos], nombre
    return re.match(r'<td class="([^"]*)"', html[td:]).group(1)


def test_las_partidas_llevan_la_clase_de_campo(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.get("/contaduria/asientos/nuevo/")
    assert r.status_code == 200
    html = r.content.decode()
    for prefijo in ("partidas-0", "partidas-1", "partidas-__prefix__"):
        for campo in CAMPOS:
            clase = _clase_de_la_celda(html, f"{prefijo}-{campo}")
            assert "campo-form" in clase.split(), f"{prefijo}-{campo} sin borde"


def test_la_casilla_de_eliminar_no_se_estira_como_campo(client, usuario_factory):
    """`campo-form` también pinta sus `label` como etiqueta de bloque: la celda
    de «eliminar» se queda fuera."""
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get("/contaduria/asientos/nuevo/").content.decode()
    assert "campo-form" not in _clase_de_la_celda(html, "partidas-0-DELETE").split()
