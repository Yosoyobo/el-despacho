"""Todo rol nuevo nace con `PERMISOS_UNIVERSALES` (deuda Sep28).

`cuentas/0046` sumó `equipo.ver_actividad` al JSON de los roles que YA existían;
uno creado después nacía sin él. Sólo lo notaba «ver como rol» (evalúa SÓLO el
JSON del rol simulado): el super_admin simulando ese rol veía el Dashboard sin el
recuadro de quién está en línea, aunque la persona de ese rol sí lo ve.
"""

import pytest
from django.test import override_settings
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


@pytest.fixture
def admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    return u


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_el_rol_nuevo_nace_con_los_universales(client, admin):  # noqa: ARG001
    from cuentas.models.rol import Rol
    from lib.permisos_defaults import PERMISOS_UNIVERSALES

    r = client.post(reverse("directorio-rol-nuevo"), {
        "nombre": "Mostrador", "descripcion": "", "permisos": ["cartera.ver"],
    })
    assert r.status_code == 302
    rol = Rol.objects.get(nombre="Mostrador")
    for modulo, acciones in PERMISOS_UNIVERSALES.items():
        for accion in acciones:
            assert accion in rol.permisos.get(modulo, []), (modulo, accion)
    assert rol.permisos["cartera"] == ["ver"], "lo marcado se respeta tal cual"


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_aunque_no_se_marque_ninguna_casilla(client, admin):  # noqa: ARG001
    from cuentas.models.rol import Rol

    client.post(reverse("directorio-rol-nuevo"), {"nombre": "Vacío", "descripcion": ""})
    assert Rol.objects.get(nombre="Vacío").permisos == {"equipo": ["ver_actividad"]}


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_la_casilla_del_universal_sale_marcada_en_el_alta(client, admin):  # noqa: ARG001
    import re

    html = client.get(reverse("directorio-rol-nuevo")).content.decode()
    casilla = re.search(r'<input[^>]*value="equipo\.ver_actividad"[^>]*>', html)
    assert casilla, "la grilla no ofrece equipo.ver_actividad"
    assert "checked" in casilla.group(0)
    otra = re.search(r'<input[^>]*value="cartera\.ver"[^>]*>', html)
    assert "checked" not in otra.group(0), "sólo los universales vienen marcados"


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_ver_como_el_rol_nuevo_ve_quien_esta_en_linea(client, admin):
    """Lo que de verdad importa: la simulación dice lo mismo que la persona."""
    from cuentas.models.rol import Rol
    from lib.permisos import puede

    client.post(reverse("directorio-rol-nuevo"), {"nombre": "Ventas", "descripcion": ""})
    admin._rol_simulado = Rol.objects.get(nombre="Ventas").clave
    assert puede(admin, "equipo", "ver_actividad")
