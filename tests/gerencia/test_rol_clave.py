"""S-Mandados-V2 — Rol.clave estable + nombre editable.

Renombrar un rol (incluso uno de sistema) NO debe romper los permisos: la
identidad la lleva la `clave` interna, no el `nombre` visible.
"""

import pytest

from lib.permisos import es_admin, roles_efectivos

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def _rol(clave):
    from cuentas.models.rol import Rol
    return Rol.objects.get(clave=clave)


def test_roles_de_sistema_tienen_clave():
    for clave in ("super_admin", "dueno", "contador", "disenador"):
        assert _rol(clave).clave == clave


def test_renombrar_rol_no_rompe_permisos(client, usuario_factory):
    """Renombrar el rol 'dueno' a 'Socio' desde la GUI: un usuario con ese rol
    sigue siendo admin (la clave 'dueno' no cambió)."""
    sa = usuario_factory(rol="super_admin", email="sa@lc.mx")
    socio = usuario_factory(rol="disenador", email="socio@lc.mx")
    socio.roles_extra.add(_rol("dueno"))
    assert es_admin(socio) is True

    client.force_login(sa)
    rol = _rol("dueno")
    resp = client.post(f"/directorio/roles/{rol.pk}/editar", {
        "nombre": "Socio", "descripcion": "Dueño renombrado",
        "permisos": [f"{m}.{a}" for m, accs in (rol.permisos or {}).items() for a in accs],
    })
    assert resp.status_code in (302, 200)
    rol.refresh_from_db()
    assert rol.nombre == "Socio"
    assert rol.clave == "dueno"           # clave intacta
    socio.refresh_from_db()
    assert es_admin(socio) is True         # permisos intactos
    assert "dueno" in roles_efectivos(socio)


def test_borrar_super_admin_bloqueado(client, usuario_factory):
    sa = usuario_factory(rol="super_admin", email="sa2@lc.mx")
    client.force_login(sa)
    rol = _rol("super_admin")
    client.post(f"/directorio/roles/{rol.pk}/borrar")
    from cuentas.models.rol import Rol
    assert Rol.objects.filter(clave="super_admin").exists()  # sigue existiendo


def test_crear_rol_genera_clave(client, usuario_factory):
    sa = usuario_factory(rol="super_admin", email="sa3@lc.mx")
    client.force_login(sa)
    client.post("/directorio/roles/nuevo", {
        "nombre": "Supervisor de Producción", "descripcion": "", "permisos": ["pizarron.ver"],
    })
    from cuentas.models.rol import Rol
    rol = Rol.objects.get(nombre="Supervisor de Producción")
    assert rol.clave == "supervisor-de-produccion"
    assert rol.sistema is False
    assert not rol.protegido
