"""El cliente del proyecto va junto al título, con liga a su ficha (ticket Oscar
14-oct-2026: «en la página de un proyecto no viene el nombre del cliente con link
a su perfil»). La liga respeta el permiso `cartera.ver`: sin él se ve el nombre,
sin enlace a una pantalla que daría 403.
"""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _bloque_cliente(html: str) -> str:
    m = re.search(r"<p[^>]*data-proyecto-cliente.*?</p>", html, re.S)
    assert m, "el encabezado no trae el bloque del cliente"
    return m.group(0)


def _asignado(usuario, proyecto):
    from apps.los_proyectos.models import ProyectoAsignacion

    ProyectoAsignacion.objects.create(proyecto=proyecto, usuario=usuario, rol_en_proyecto="disenador")


def test_el_cliente_aparece_con_liga_a_su_ficha(client, usuario_factory, proyecto_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, razon_social="Heladería Polar S.A.")
    p = proyecto_factory(cliente=cli, creado_por=admin)
    client.force_login(admin)
    bloque = _bloque_cliente(client.get(f"/proyectos/{p.pk}/").content.decode())
    assert "Heladería Polar S.A." in bloque
    assert f'href="{reverse("cartera-detalle", args=[cli.pk])}"' in bloque


def test_sin_permiso_de_clientes_se_ve_el_nombre_sin_liga(client, usuario_factory, proyecto_factory,
                                                          cliente_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario

    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, razon_social="Heladería Polar S.A.")
    p = proyecto_factory(cliente=cli, creado_por=admin)
    d = usuario_factory(rol="disenador")
    _asignado(d, p)
    PermisoUsuario.objects.update_or_create(
        usuario=d, modulo="cartera", permiso="ver", defaults={"activo": False})
    client.force_login(d)
    r = client.get(f"/proyectos/{p.pk}/")
    assert r.status_code == 200
    bloque = _bloque_cliente(r.content.decode())
    assert "Heladería Polar S.A." in bloque
    assert "<a " not in bloque


def test_con_permiso_de_clientes_hay_liga(client, usuario_factory, proyecto_factory, cliente_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario

    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    p = proyecto_factory(cliente=cli, creado_por=admin)
    d = usuario_factory(rol="disenador")
    _asignado(d, p)
    PermisoUsuario.objects.update_or_create(
        usuario=d, modulo="cartera", permiso="ver", defaults={"activo": True})
    client.force_login(d)
    bloque = _bloque_cliente(client.get(f"/proyectos/{p.pk}/").content.decode())
    assert reverse("cartera-detalle", args=[cli.pk]) in bloque
