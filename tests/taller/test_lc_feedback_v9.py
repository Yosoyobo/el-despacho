"""S-LC-Feedback-V9 — balance del mes con horario propio, privacidad de horas
trabajadas (jefe directo), horario semanal, roles legibles y carpetas del menú."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _aware(y, m, d, h, mi=0):
    return timezone.make_aware(datetime.datetime(y, m, d, h, mi))


def _horario(usuario, dia, ent=(17, 0), sal=(19, 0)):
    from apps.checador.models import HorarioLaboral
    HorarioLaboral.objects.update_or_create(
        usuario=usuario, dia_semana=dia,
        defaults={"hora_entrada": datetime.time(*ent), "hora_salida": datetime.time(*sal),
                  "tolerancia_min": 5, "activo": True},
    )


# ── "No cuadran las horas": horario propio = días declarados, sin fallback global ──

def test_horario_vigente_dia_libre_sin_fallback_global(usuario_factory):
    from apps.checador import services
    from apps.checador.models import HorarioLaboral
    u = usuario_factory(rol="miembro")
    _horario(u, 3)  # Jueves
    _horario(u, 4)  # Viernes
    # Global L-V 9-18 que NO debe heredarse en los días libres del usuario.
    for dia in range(5):
        HorarioLaboral.objects.update_or_create(
            usuario=None, dia_semana=dia,
            defaults={"hora_entrada": datetime.time(9, 0), "hora_salida": datetime.time(18, 0),
                      "tolerancia_min": 15, "activo": True},
        )
    # Lunes 2026-06-08 (weekday 0): el usuario NO trabaja → None (no hereda global).
    assert services.horario_vigente(u, datetime.date(2026, 6, 8)) is None
    # Jueves 2026-06-11: su override.
    h = services.horario_vigente(u, datetime.date(2026, 6, 11))
    assert h is not None and h.hora_entrada == datetime.time(17, 0)


def test_balance_mensual_solo_dias_declarados(usuario_factory):
    from apps.checador import services
    from apps.checador.models import HorarioLaboral
    u = usuario_factory(rol="miembro")
    _horario(u, 3)  # Jueves 17-19 = 2h
    _horario(u, 4)  # Viernes 17-19 = 2h
    for dia in range(5):  # global L-V 9h que NO debe contar
        HorarioLaboral.objects.update_or_create(
            usuario=None, dia_semana=dia,
            defaults={"hora_entrada": datetime.time(9, 0), "hora_salida": datetime.time(18, 0),
                      "tolerancia_min": 15, "activo": True},
        )
    bal = services.balance_mensual(u, ahora=_aware(2026, 6, 12, 23, 0))
    # Jun ≤12: Jue 4,11 + Vie 5,12 = 4 días × 2h = 8h. NO 60h.
    assert bal["esperadas_horas"] == 8.0


def test_horario_semanal_flags(usuario_factory):
    from apps.checador import services
    u = usuario_factory(rol="miembro")
    _horario(u, 3)
    _horario(u, 4)
    semana = services.horario_semanal(u)
    por_dia = {f["dia"]: f["trabaja"] for f in semana}
    assert por_dia[3] is True and por_dia[4] is True
    assert por_dia[0] is False and por_dia[5] is False
    assert len(semana) == 7


# ── Privacidad: solo jefe directo / super_admin / uno mismo ve horas ──

def test_puede_ver_horas_trabajadas_de(usuario_factory):
    from lib.permisos import puede_ver_horas_trabajadas_de
    jefe = usuario_factory(rol="miembro")
    empleado = usuario_factory(rol="miembro")
    empleado.jefe_directo = jefe
    empleado.save()
    otro = usuario_factory(rol="miembro")
    sa = usuario_factory(rol="super_admin")
    assert puede_ver_horas_trabajadas_de(empleado, empleado) is True   # uno mismo
    assert puede_ver_horas_trabajadas_de(jefe, empleado) is True       # jefe directo
    assert puede_ver_horas_trabajadas_de(sa, empleado) is True         # super_admin
    assert puede_ver_horas_trabajadas_de(otro, empleado) is False      # ajeno


def test_ficha_oculta_horas_a_ajeno_pero_muestra_horario(client, usuario_factory):
    u_otro = usuario_factory(rol="miembro")
    empleado = usuario_factory(rol="miembro")
    empleado.nombre_completo = "Empleado Uno"
    empleado.save()
    _horario(empleado, 3)
    client.force_login(u_otro)
    resp = client.get(f"/directorio/{empleado.pk}/")
    assert resp.status_code == 200
    # Ve el horario de la semana, no el bloque de horas trabajadas.
    assert b"Horario de la semana" in resp.content
    assert b"Asistencia (horas trabajadas)" not in resp.content


# ── Roles legibles (primario + roles_extra) ──

def test_equipo_persona_superadmin_ve_horas_y_horario(client, usuario_factory):
    sa = usuario_factory(rol="super_admin")
    empleado = usuario_factory(rol="miembro")
    _horario(empleado, 3)
    client.force_login(sa)
    resp = client.get(f"/checador/equipo/{empleado.pk}/")
    assert resp.status_code == 200
    assert b"Horario declarado de la semana" in resp.content
    assert b"Jornadas" in resp.content  # super_admin sí ve horas


def test_roles_display_incluye_extra(usuario_factory):
    from cuentas.models.rol import Rol
    from lib.permisos import roles_display
    u = usuario_factory(rol="miembro")
    rol = Rol.objects.create(nombre="Cobranza")
    u.roles_extra.add(rol)
    nombres = roles_display(u)
    assert "Miembro" in nombres
    assert "Cobranza" in nombres


# ── Carpetas personalizadas del sidebar ──

def test_sidebar_guardar_persiste_grupo(client, usuario_factory):
    from cuentas.models.sidebar_orden import SidebarOrdenUsuario
    u = usuario_factory(rol="miembro")
    client.force_login(u)
    resp = client.post("/perfil/sidebar/guardar", {
        "orden__clientes": "20", "grupo__clientes": "Ventas",
        "orden__proyectos": "30", "grupo__proyectos": "Ventas",
    })
    assert resp.status_code in (302, 200)
    fila = SidebarOrdenUsuario.objects.get(usuario=u, slug="clientes")
    assert fila.grupo == "Ventas"
