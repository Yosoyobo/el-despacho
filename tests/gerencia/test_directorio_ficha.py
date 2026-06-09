"""S-Directorio-V1: el UsuarioForm de Gerencia persiste la ficha del empleado."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_form_guarda_ficha(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    empleado = usuario_factory(rol="disenador")
    empleado.nombre_completo = "Empleado Ficha"
    empleado.save()
    client.force_login(admin)
    resp = client.post(f"/directorio/{empleado.pk}/panel/datos", data={
        "email": empleado.email,
        "nombre_completo": "Empleado Ficha",
        "rol": "disenador",
        "is_active": "on",
        "puesto": "Diseñador junior",
        "telefono": "5551234567",
        "oficina": "Cuajimalpa",
        "modalidad": "hibrido",
        "horario_inicio": "09:00",
        "horario_fin": "18:00",
        "dias_trabajo": "Lunes a viernes",
    })
    assert resp.status_code in (200, 204, 302)
    empleado.refresh_from_db()
    assert empleado.puesto == "Diseñador junior"
    assert empleado.oficina == "Cuajimalpa"
    assert empleado.modalidad == "hibrido"
    assert empleado.dias_trabajo == "Lunes a viernes"
    assert empleado.horario_inicio.strftime("%H:%M") == "09:00"
