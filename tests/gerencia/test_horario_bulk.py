"""S-Checador-V1.2 — alta masiva de horarios (multi-día / multi-usuario)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_alta_masiva_por_usuario_varios_dias(client, usuario_factory):
    from apps.checador.models import HorarioLaboral
    admin = usuario_factory(rol="super_admin")
    empleado = usuario_factory(rol="disenador")
    client.force_login(admin)
    resp = client.post("/catalogos/horarios/nuevo/", {
        "usuarios": [str(empleado.pk)],
        "dias": ["0", "1", "2"],
        "hora_entrada": "09:00", "hora_salida": "18:00",
        "tolerancia_min": "15", "activo": "on",
    })
    assert resp.status_code in (302, 200)
    assert HorarioLaboral.objects.filter(usuario=empleado).count() == 3


def test_alta_masiva_global(client, usuario_factory):
    from apps.checador.models import HorarioLaboral
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    client.post("/catalogos/horarios/nuevo/", {
        "aplicar_global": "on",
        "dias": ["3"],
        "hora_entrada": "08:30", "hora_salida": "17:30",
        "tolerancia_min": "10", "activo": "on",
    })
    h = HorarioLaboral.objects.get(usuario__isnull=True, dia_semana=3)
    assert h.hora_entrada.strftime("%H:%M") == "08:30"


def test_sin_usuario_ni_global_falla(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/horarios/nuevo/", {
        "dias": ["0"],
        "hora_entrada": "09:00", "hora_salida": "18:00", "tolerancia_min": "15",
    })
    assert resp.status_code == 200  # re-render con error
    assert b"al menos un usuario" in resp.content
