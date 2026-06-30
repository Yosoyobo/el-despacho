"""S-Directorio-V1: directorio read-only en El Taller + campos de ficha."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _set(u, **kw):
    for k, v in kw.items():
        setattr(u, k, v)
    u.save()
    return u


def test_lista_visible_para_disenador(client, usuario_factory):
    """Render LC 2026-06-30: la lista de Equipo es simple (nombre + puesto +
    badge de rol). El detalle (oficina/correo/horario) ya solo vive en la ficha."""
    u = usuario_factory(rol="disenador")
    otro = _set(usuario_factory(rol="contador"),
                nombre_completo="Caro Campos", puesto="Contadora", oficina="Santa Fe")
    client.force_login(u)
    resp = client.get("/directorio/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Caro Campos" in body       # nombre
    assert "Contadora" in body         # puesto (subtítulo)
    # Cada renglón enlaza a la ficha (donde sí se ve oficina/correo/horario).
    assert f"/directorio/{otro.pk}" in body


def test_busqueda_filtra(client, usuario_factory):
    # El buscador es un tercero (su nombre sale en el sidebar; no lo buscamos).
    buscador = usuario_factory(rol="super_admin")
    _set(usuario_factory(rol="disenador"), nombre_completo="Ana Lopez")
    _set(usuario_factory(rol="disenador"), nombre_completo="Beto Ruiz")
    client.force_login(buscador)
    resp = client.get("/directorio/?q=Beto")
    assert b"Beto Ruiz" in resp.content
    assert b"Ana Lopez" not in resp.content


def test_inactivos_solo_con_toggle(client, usuario_factory):
    u = _set(usuario_factory(rol="disenador"), nombre_completo="Activo Uno")
    _set(usuario_factory(rol="disenador"), nombre_completo="Baja Dos", is_active=False)
    client.force_login(u)
    assert b"Baja Dos" not in client.get("/directorio/").content
    assert b"Baja Dos" in client.get("/directorio/?inactivos=1").content


def test_requiere_login(client):
    resp = client.get("/directorio/")
    assert resp.status_code in (301, 302)
