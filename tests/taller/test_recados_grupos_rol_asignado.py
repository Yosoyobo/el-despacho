"""Los grupos «por rol» de Los Recados cuentan también el rol asignado encima.

Decisión de Oscar (2026-09-28): se reconoce el rol asignado (un Director sobre
rol primario `miembro` lee comentarios). Lo mismo para los recados a
«Dirección» o «Finanzas»: antes el grupo miraba sólo el rol primario.
"""
import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _rol(clave):
    from cuentas.models.rol import Rol

    return Rol.objects.get(clave=clave)


def test_direccion_incluye_a_quien_tiene_dueno_asignado(usuario_factory):
    from apps.recados.services import expandir_grupo_estatico

    director = usuario_factory(rol="miembro")
    director.roles_extra.add(_rol("dueno"))
    disenador = usuario_factory(rol="disenador")
    ids = expandir_grupo_estatico("direccion")
    assert director.pk in ids
    assert disenador.pk not in ids


def test_el_primario_sigue_contando_y_el_inactivo_no(usuario_factory):
    from apps.recados.services import expandir_grupo_estatico

    contador = usuario_factory(rol="contador")
    baja = usuario_factory(rol="contador")
    baja.is_active = False
    baja.save(update_fields=["is_active"])
    ids = expandir_grupo_estatico("finanzas")
    assert contador.pk in ids and baja.pk not in ids


def test_todos_es_todo_el_equipo_activo(usuario_factory):
    from apps.recados.services import expandir_grupo_estatico

    a = usuario_factory(rol="miembro")
    b = usuario_factory(rol="disenador")
    ids = expandir_grupo_estatico("todos")
    assert {a.pk, b.pk} <= ids
