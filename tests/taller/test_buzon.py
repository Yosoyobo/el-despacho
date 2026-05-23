"""El Buzón — vista del empleado (El Taller)."""

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_anonimo_redirigido(client):
    resp = client.get("/buzon/nuevo")
    assert resp.status_code in (302, 403)


def test_empleado_envia_mensaje(client, usuario_factory):
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.post("/buzon/nuevo", {
        "tipo": "sugerencia",
        "asunto": "Mejorar el filtro de Proyectos",
        "cuerpo": "Sería útil filtrar por cliente y por estado al mismo tiempo.",
        "prioridad": "5",
    })
    assert resp.status_code == 302
    msg = MensajeBuzon.objects.get(autor=u)
    assert msg.asunto.startswith("Mejorar")
    assert msg.tipo == "sugerencia"
    assert msg.estado == "nuevo"


def test_problema_se_pasa_por_el_colador(client, usuario_factory):
    """Reportes de tipo 'problema' tienen el cuerpo saneado por El Colador
    (paths absolutos, API keys, etc., quedan redactados)."""
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="contador")
    client.force_login(u)
    cuerpo = "Error en /opt/el-despacho/.env con key sk-ant-test-abcdefghijklmnopqrstuvwxyz01234567"
    client.post("/buzon/nuevo", {"tipo": "problema", "asunto": "Bug", "cuerpo": cuerpo, "prioridad": "7"})
    msg = MensajeBuzon.objects.get(autor=u)
    assert "/opt/el-despacho/.env" not in msg.cuerpo
    assert "sk-ant-test-" not in msg.cuerpo
    assert "REDACTED" in msg.cuerpo


def test_mios_solo_ve_los_propios(client, usuario_factory):
    """Pre-S2b.2: URL unificada es /buzon/. Legacy /buzon/mios/ redirige."""
    from buzon.models import MensajeBuzon
    u1 = usuario_factory(rol="disenador")
    u2 = usuario_factory(rol="disenador")
    MensajeBuzon.objects.create(autor=u1, tipo="otro", asunto="A1", cuerpo="x"*20)
    MensajeBuzon.objects.create(autor=u2, tipo="otro", asunto="A2", cuerpo="y"*20)
    client.force_login(u1)
    resp = client.get("/buzon/")
    assert resp.status_code == 200
    assert b"A1" in resp.content
    assert b"A2" not in resp.content
    # URL vieja redirige a la nueva.
    resp_legacy = client.get("/buzon/mios/")
    assert resp_legacy.status_code == 302


def test_detalle_ajeno_404(client, usuario_factory):
    """Pre-S2b.2: detalle unificado en /buzon/<id>/."""
    from buzon.models import MensajeBuzon
    u1 = usuario_factory(rol="disenador")
    u2 = usuario_factory(rol="disenador")
    m = MensajeBuzon.objects.create(autor=u2, tipo="otro", asunto="A", cuerpo="z"*20)
    client.force_login(u1)
    resp = client.get(f"/buzon/{m.pk}/")
    assert resp.status_code == 404


def test_prioridad_orden_descendente(client, usuario_factory):
    """Lista del buzón ordena por prioridad descendente y luego fecha desc."""
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="super_admin")
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="baja", cuerpo="x"*20, prioridad=1)
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="urgente", cuerpo="y"*20, prioridad=9)
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="media", cuerpo="z"*20, prioridad=5)
    client.force_login(u)
    resp = client.get("/buzon/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # urgente (9) debe aparecer antes que media (5) antes que baja (1).
    assert body.index("urgente") < body.index("media") < body.index("baja")


def test_orden_fecha_invierte_prioridad(client, usuario_factory):
    """S-LC-Feedback-V2: ?orden=fecha ordena cronológico descendente (más reciente arriba)
    independientemente de la prioridad."""
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="super_admin")
    # Creo en orden cronológico inverso al de prioridad.
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="urgente", cuerpo="y"*20, prioridad=9)
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="media", cuerpo="z"*20, prioridad=5)
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="baja", cuerpo="x"*20, prioridad=1)
    client.force_login(u)
    resp = client.get("/buzon/?orden=fecha")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Más reciente (baja, creada al final) debe estar arriba.
    assert body.index("baja") < body.index("media") < body.index("urgente")
    # El segmented control debe marcar "Por fecha" activo.
    assert "Por fecha" in body
