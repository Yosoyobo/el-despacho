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
    client.post("/buzon/nuevo", {"tipo": "problema", "asunto": "Bug", "cuerpo": cuerpo})
    msg = MensajeBuzon.objects.get(autor=u)
    assert "/opt/el-despacho/.env" not in msg.cuerpo
    assert "sk-ant-test-" not in msg.cuerpo
    assert "REDACTED" in msg.cuerpo


def test_mios_solo_ve_los_propios(client, usuario_factory):
    from buzon.models import MensajeBuzon
    u1 = usuario_factory(rol="disenador")
    u2 = usuario_factory(rol="disenador")
    MensajeBuzon.objects.create(autor=u1, tipo="otro", asunto="A1", cuerpo="x"*20)
    MensajeBuzon.objects.create(autor=u2, tipo="otro", asunto="A2", cuerpo="y"*20)
    client.force_login(u1)
    resp = client.get("/buzon/mios/")
    assert resp.status_code == 200
    assert b"A1" in resp.content
    assert b"A2" not in resp.content


def test_detalle_ajeno_404(client, usuario_factory):
    from buzon.models import MensajeBuzon
    u1 = usuario_factory(rol="disenador")
    u2 = usuario_factory(rol="disenador")
    m = MensajeBuzon.objects.create(autor=u2, tipo="otro", asunto="A", cuerpo="z"*20)
    client.force_login(u1)
    resp = client.get(f"/buzon/mios/{m.pk}/")
    assert resp.status_code == 404
