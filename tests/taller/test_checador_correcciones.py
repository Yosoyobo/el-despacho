"""S-Checador E5 — correcciones (solicitar + bandeja de aprobación en Taller)."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

LUNES = datetime.date(2026, 6, 8)


def _dt(h, m, fecha=LUNES):
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(h, m)))


def _jornada(u, hora=9, minuto=40):
    from apps.checador import services
    return services.checar_entrada(u, registrado_en=_dt(hora, minuto))


def test_correccion_modal_propia_jornada(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    j = _jornada(u)
    client.force_login(u)
    resp = client.get(f"/checador/correccion/nueva?jornada={j.pk}")
    assert resp.status_code == 200
    assert b"Solicitar correcci" in resp.content


def test_correccion_modal_jornada_ajena_403(client, usuario_factory):
    dueno = usuario_factory(rol="disenador")
    j = _jornada(dueno)
    otro = usuario_factory(rol="disenador")
    client.force_login(otro)
    resp = client.get(f"/checador/correccion/nueva?jornada={j.pk}")
    assert resp.status_code == 403


def test_solicitar_correccion_crea_pendiente(client, usuario_factory):
    from apps.checador.models import SolicitudCorreccion
    u = usuario_factory(rol="disenador")
    j = _jornada(u)
    client.force_login(u)
    resp = client.post("/checador/correccion", {
        "jornada": str(j.pk), "tipo": "entrada",
        "valor_propuesto": "2026-06-08T09:05", "motivo": "Marqué tarde por el tráfico",
    })
    assert resp.status_code == 302
    sol = SolicitudCorreccion.objects.get(usuario=u)
    assert sol.estado == "pendiente"
    assert sol.tipo == "entrada"


def test_bandeja_requiere_aprobar(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert client.get("/checador/correcciones/").status_code == 403


def test_bandeja_admin_ve_pendientes(client, usuario_factory):
    from apps.checador import services
    empleado = usuario_factory(rol="disenador")
    j = _jornada(empleado)
    services.solicitar_correccion(empleado, tipo="entrada", valor_propuesto=_dt(9, 5), motivo="x", jornada=j)
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/checador/correcciones/")
    assert resp.status_code == 200
    assert b"Pendientes" in resp.content


def test_resolver_aprobar_aplica_y_redirige(client, usuario_factory):
    from apps.checador import services
    from apps.checador.models import Jornada
    empleado = usuario_factory(rol="disenador")
    j = _jornada(empleado)  # retardo 25
    sol = services.solicitar_correccion(empleado, tipo="entrada", valor_propuesto=_dt(9, 5), motivo="x", jornada=j)
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(
        f"/checador/correcciones/{sol.pk}/resolver",
        {"decision": "aprobar", "comentario": "ok"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == "/checador/correcciones/"
    j2 = Jornada.objects.get(pk=j.pk)
    assert j2.retardo_min == 0
    sol.refresh_from_db()
    assert sol.estado == "aprobada"


def test_resolver_requiere_aprobar(client, usuario_factory):
    from apps.checador import services
    empleado = usuario_factory(rol="disenador")
    j = _jornada(empleado)
    sol = services.solicitar_correccion(empleado, tipo="entrada", valor_propuesto=_dt(9, 5), motivo="x", jornada=j)
    client.force_login(empleado)
    assert client.post(f"/checador/correcciones/{sol.pk}/resolver", {"decision": "aprobar"}).status_code == 403
