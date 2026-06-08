"""S-Estados-Color-HEX: color HEX en categorías + gate de permiso del Chalán."""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── Color HEX en Categorías ───────────────────────────────────────────────────

def test_categoria_crear_con_color(client, usuario_factory):
    from apps.el_catalogo.models import CategoriaServicio
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(reverse("catalogo-categoria-nueva"), data={
        "nombre": "Serigrafía",
        "color": "#12b76a",
        "orden": 50,
        "activa": "on",
    })
    assert resp.status_code in (301, 302)
    cat = CategoriaServicio.objects.get(nombre="Serigrafía")
    assert cat.color == "#12b76a"


def test_categoria_color_invalido_rechazado(client, usuario_factory):
    from apps.el_catalogo.models import CategoriaServicio
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(reverse("catalogo-categoria-nueva"), data={
        "nombre": "Mala",
        "color": "verde",  # no es #RRGGBB
        "orden": 51,
        "activa": "on",
    })
    assert resp.status_code == 200
    assert not CategoriaServicio.objects.filter(nombre="Mala").exists()


def test_categoria_color_default(client, usuario_factory):
    """Sin color explícito, el form pre-llena el default gris desde el partial,
    pero a nivel modelo el default es #667085."""
    from apps.el_catalogo.models import CategoriaServicio
    cat = CategoriaServicio.objects.create(nombre="Sin color")
    assert cat.color == "#667085"


# ── Gate de permiso del chat de El Chalán ──────────────────────────────────────

def test_chalan_chat_visible_con_permiso(client, usuario_factory):
    # super_admin recibe (chalan, usar) por defaults del rol (signal de seed).
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get(reverse("chalan-chat"))
    assert resp.status_code == 200


def test_chalan_chat_403_sin_permiso(client, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    admin = usuario_factory(rol="super_admin")
    # Revoca el permiso (override individual gana).
    PermisoUsuario.objects.update_or_create(
        usuario=admin, modulo="chalan", permiso="usar",
        defaults={"activo": False},
    )
    client.force_login(admin)
    assert client.get(reverse("chalan-chat")).status_code == 403
    # El POST de "nuevo chat" del Dashboard también queda bloqueado.
    assert client.post(reverse("chalan-nuevo"), data={"mensaje": "hola"}).status_code == 403


def test_sidebar_oculta_chalan_sin_permiso(client, usuario_factory):
    """El item 'El Chalán' del sidebar desaparece si no hay permiso."""
    from cuentas.models.permiso_usuario import PermisoUsuario
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    # Con permiso: el link al chat aparece en el home.
    assert reverse("chalan-chat").encode() in client.get("/").content
    # Sin permiso: desaparece.
    PermisoUsuario.objects.update_or_create(
        usuario=admin, modulo="chalan", permiso="usar",
        defaults={"activo": False},
    )
    assert reverse("chalan-chat").encode() not in client.get("/").content
