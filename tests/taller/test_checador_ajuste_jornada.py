"""S-Checador-V1.3 — ajustar jornada completa (solicitud + admin directo),
quién aprobó visible, y no auto-aprobar la propia solicitud."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _aware(y, m, d, h, mi=0):
    return timezone.make_aware(datetime.datetime(y, m, d, h, mi))


# ── Solicitud de jornada completa ─────────────────────────────────────────

def test_solicitar_ajuste_jornada_crea_solicitud(usuario_factory):
    from apps.checador import services
    from apps.checador.models import SolicitudCorreccion
    usuario_factory(rol="super_admin")  # un aprobador
    req = usuario_factory(rol="disenador")
    sol = services.solicitar_ajuste_jornada(
        req, fecha=datetime.date(2026, 6, 9),
        valor_entrada=_aware(2026, 6, 9, 9, 0), valor_salida=_aware(2026, 6, 9, 18, 0),
        motivo="olvidé checar",
    )
    assert sol.tipo == "jornada"
    assert sol.fecha == datetime.date(2026, 6, 9)
    assert SolicitudCorreccion.objects.filter(pk=sol.pk, estado="pendiente").exists()


def test_aprobar_jornada_crea_dia_faltante(usuario_factory):
    from apps.checador import services
    from apps.checador.models import Jornada
    admin = usuario_factory(rol="super_admin")
    req = usuario_factory(rol="disenador")
    # No hay jornada ese día (olvido total).
    sol = services.solicitar_ajuste_jornada(
        req, fecha=datetime.date(2026, 6, 9),
        valor_entrada=_aware(2026, 6, 9, 9, 0), valor_salida=_aware(2026, 6, 9, 17, 0),
        motivo="olvido total",
    )
    services.resolver_correccion(sol, admin=admin, aprobar=True)
    j = Jornada.objects.get(usuario=req, fecha=datetime.date(2026, 6, 9))
    assert j.entrada_en == _aware(2026, 6, 9, 9, 0)
    assert j.salida_en == _aware(2026, 6, 9, 17, 0)
    assert j.estado == "cerrada"
    assert j.ajustado_por_id == admin.pk


def test_super_admin_si_aprueba_propia_solicitud(usuario_factory):
    """Oscar (super_admin) SÍ puede aprobar su propia corrección de horario —
    es el failsafe duro del despacho y no tiene a quién pedírselo."""
    from apps.checador import services
    from apps.checador.models import Jornada
    admin = usuario_factory(rol="super_admin")
    sol = services.solicitar_ajuste_jornada(
        admin, fecha=datetime.date(2026, 6, 9),
        valor_entrada=_aware(2026, 6, 9, 9, 0), valor_salida=_aware(2026, 6, 9, 17, 0),
        motivo="olvidé checar",
    )
    services.resolver_correccion(sol, admin=admin, aprobar=True)
    sol.refresh_from_db()
    assert sol.estado == "aprobada"
    assert Jornada.objects.filter(usuario=admin, fecha=datetime.date(2026, 6, 9)).exists()


def test_no_super_admin_no_autoaprueba_propia(usuario_factory):
    """Un jefe/aprobador que NO es super_admin sigue sin poder aprobar lo suyo."""
    from apps.checador import services
    usuario_factory(rol="super_admin")  # aprobador disponible en el sistema
    jefe = usuario_factory(rol="contador")
    sol = services.solicitar_ajuste_jornada(
        jefe, fecha=datetime.date(2026, 6, 9),
        valor_entrada=_aware(2026, 6, 9, 9, 0), valor_salida=None, motivo="x",
    )
    with pytest.raises(ValueError, match="propia"):
        services.resolver_correccion(sol, admin=jefe, aprobar=True)


# ── Admin edita directo ───────────────────────────────────────────────────

def test_editar_jornada_directo(usuario_factory):
    from apps.checador import services
    from apps.checador.models import Jornada
    admin = usuario_factory(rol="super_admin")
    persona = usuario_factory(rol="disenador")
    j = services.editar_jornada_directo(
        usuario=persona, fecha=datetime.date(2026, 6, 9),
        valor_entrada=_aware(2026, 6, 9, 9, 0), valor_salida=_aware(2026, 6, 9, 18, 0), admin=admin,
    )
    assert isinstance(j, Jornada)
    assert j.ajustado_por_id == admin.pk and j.ajustado_en is not None
    assert j.salida_en == _aware(2026, 6, 9, 18, 0)


def test_jornada_admin_modal_gating(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    empleado = usuario_factory(rol="disenador")
    # diseñador no puede ajustar jornadas de otros
    client.force_login(empleado)
    assert client.get(f"/checador/equipo/{empleado.pk}/jornada/editar/modal").status_code in (302, 403)
    # admin sí
    client.force_login(admin)
    assert client.get(f"/checador/equipo/{empleado.pk}/jornada/editar/modal").status_code == 200


def test_ajuste_jornada_view_empleado(client, usuario_factory):
    from apps.checador.models import SolicitudCorreccion
    usuario_factory(rol="super_admin")
    req = usuario_factory(rol="disenador")
    client.force_login(req)
    resp = client.post("/checador/jornada/ajuste", {
        "fecha": "2026-06-09", "entrada": "09:00", "salida": "18:00", "motivo": "olvidé checar salida",
    })
    assert resp.status_code in (302, 200)
    assert SolicitudCorreccion.objects.filter(usuario=req, tipo="jornada").exists()
