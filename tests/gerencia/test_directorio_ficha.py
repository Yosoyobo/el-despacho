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


def _datos_base(empleado, **extra):
    datos = {
        "email": empleado.email, "nombre_completo": "Empleado Ficha", "is_active": "on",
        "modalidad": "presencial",
    }
    datos.update(extra)
    return datos


def test_form_guarda_el_checador_por_actividad(client, usuario_factory):
    """Oscar 2026-10-01: los dos interruptores viven en la ficha de El Directorio."""
    admin = usuario_factory(rol="super_admin")
    empleado = usuario_factory(rol="disenador")
    client.force_login(admin)
    client.post(f"/directorio/{empleado.pk}/panel/datos", data=_datos_base(
        empleado, checador_por_actividad="on", checador_descontar_pausas="on",
        checador_pausa_min="45",
    ))
    empleado.refresh_from_db()
    assert empleado.checador_por_actividad and empleado.checador_descontar_pausas
    assert empleado.checador_pausa_min == 45

    # Apagarlo es desmarcar la casilla.
    client.post(f"/directorio/{empleado.pk}/panel/datos", data=_datos_base(empleado))
    empleado.refresh_from_db()
    assert not empleado.checador_por_actividad
    assert empleado.checador_pausa_min == 45  # vacío hereda, no se resetea


def test_form_rechaza_una_pausa_absurda(client, usuario_factory):
    from apps.el_directorio.forms import UsuarioForm
    empleado = usuario_factory(rol="disenador")
    form = UsuarioForm(data=_datos_base(empleado, checador_pausa_min="2"), instance=empleado)
    assert not form.is_valid()
    assert "checador_pausa_min" in form.errors
