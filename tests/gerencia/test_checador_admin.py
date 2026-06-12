"""S-Checador E5c — Gerencia: CRUD de horarios + bandeja de correcciones."""

from __future__ import annotations

import datetime

import pytest
from django.test import override_settings
from django.utils import timezone

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]
GERENCIA = override_settings(ROOT_URLCONF="tests.urls_gerencia")

LUNES = datetime.date(2026, 6, 8)


def _dt(h, m, fecha=LUNES):
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(h, m)))


@GERENCIA
def test_horarios_lista_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/catalogos/horarios/")
    assert resp.status_code == 200
    assert b"Horario global" in resp.content


@GERENCIA
def test_horarios_disenador_sin_permiso(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert client.get("/catalogos/horarios/").status_code == 403


@GERENCIA
def test_horario_override_se_crea(client, usuario_factory):
    # S-Checador-V1.2: el alta es masiva (checkboxes usuarios + días).
    from apps.checador.models import HorarioLaboral
    admin = usuario_factory(rol="super_admin")
    empleado = usuario_factory(rol="disenador")
    client.force_login(admin)
    resp = client.post("/catalogos/horarios/nuevo/", {
        "usuarios": [str(empleado.pk)], "dias": ["0"],
        "hora_entrada": "10:00", "hora_salida": "19:00", "tolerancia_min": "10", "activo": "on",
    })
    assert resp.status_code == 302
    h = HorarioLaboral.objects.get(usuario=empleado, dia_semana=0)
    assert h.hora_entrada == datetime.time(10, 0)


@GERENCIA
def test_horario_global_alta_es_idempotente(client, usuario_factory):
    # S-Checador-V1.2: el alta masiva usa update_or_create — re-crear el global
    # de un día lo ACTUALIZA (no duplica, no error).
    from apps.checador.models import HorarioLaboral
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    antes = HorarioLaboral.objects.filter(usuario__isnull=True, dia_semana=0).count()
    resp = client.post("/catalogos/horarios/nuevo/", {
        "aplicar_global": "on", "dias": ["0"],
        "hora_entrada": "08:00", "hora_salida": "17:00", "tolerancia_min": "15", "activo": "on",
    })
    assert resp.status_code == 302
    assert HorarioLaboral.objects.filter(usuario__isnull=True, dia_semana=0).count() == antes
    h = HorarioLaboral.objects.get(usuario__isnull=True, dia_semana=0)
    assert h.hora_entrada == datetime.time(8, 0)


@GERENCIA
def test_horario_global_no_se_borra(client, usuario_factory):
    from apps.checador.models import HorarioLaboral
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    global_lunes = HorarioLaboral.objects.get(usuario__isnull=True, dia_semana=0)
    client.post(f"/catalogos/horarios/{global_lunes.pk}/borrar/")
    assert HorarioLaboral.objects.filter(pk=global_lunes.pk).exists()


@GERENCIA
def test_bandeja_gerencia_resuelve(client, usuario_factory):
    from apps.checador import services
    from apps.checador.models import Jornada
    empleado = usuario_factory(rol="disenador")
    j = services.checar_entrada(empleado, registrado_en=_dt(9, 40))
    sol = services.solicitar_correccion(empleado, tipo="entrada", valor_propuesto=_dt(9, 5), motivo="x", jornada=j)
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    assert client.get("/checador/correcciones/").status_code == 200
    resp = client.post(
        f"/checador/correcciones/{sol.pk}/resolver",
        {"decision": "aprobar"}, HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    sol.refresh_from_db()
    assert sol.estado == "aprobada"
    assert Jornada.objects.get(pk=j.pk).retardo_min == 0
