"""El Buzón — vista admin (La Gerencia)."""

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


@pytest.fixture
def mensaje(db, usuario_factory):
    from buzon.models import MensajeBuzon
    autor = usuario_factory(rol="disenador")
    return MensajeBuzon.objects.create(
        autor=autor, tipo="sugerencia", asunto="Test asunto",
        cuerpo="cuerpo del mensaje" * 5,
    )


def test_disenador_sin_acceso(client, usuario_factory):
    client.force_login(usuario_factory(rol="disenador"))
    resp = client.get("/buzon/")
    assert resp.status_code == 403


def test_contador_sin_acceso(client, usuario_factory):
    client.force_login(usuario_factory(rol="contador"))
    resp = client.get("/buzon/")
    assert resp.status_code == 403


def test_admin_ve_lista(client, usuario_factory, mensaje):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/buzon/")
    assert resp.status_code == 200
    assert b"Test asunto" in resp.content


def test_filtrar_por_estado(client, usuario_factory, mensaje):
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.get("/buzon/?estado=archivado")
    assert resp.status_code == 200
    assert b"Test asunto" not in resp.content


def test_get_marca_como_leido(client, usuario_factory, mensaje):
    from buzon.models import MensajeBuzon
    assert mensaje.estado == "nuevo"
    client.force_login(usuario_factory(rol="super_admin"))
    client.get(f"/buzon/{mensaje.pk}/")
    mensaje.refresh_from_db()
    assert mensaje.estado == "leido"
    # Segundo GET no debería revertir el estado.
    client.get(f"/buzon/{mensaje.pk}/")
    mensaje = MensajeBuzon.objects.get(pk=mensaje.pk)
    assert mensaje.estado == "leido"


def test_admin_responde(client, usuario_factory, mensaje):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(f"/buzon/{mensaje.pk}/", {
        "estado": "respondido",
        "nota_interna": "Acepta — buena idea",
        "respuesta_publica": "Gracias por la sugerencia, lo agregamos al backlog.",
    })
    assert resp.status_code == 302
    mensaje.refresh_from_db()
    assert mensaje.estado == "respondido"
    assert mensaje.respuesta_publica.startswith("Gracias")
    assert mensaje.respondido_en is not None


def test_exportar_md(client, usuario_factory, mensaje):
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/buzon/{mensaje.pk}/exportar.md")
    assert resp.status_code == 200
    assert "text/markdown" in resp["Content-Type"]
    body = resp.content.decode()
    assert f"# Buzón #{mensaje.pk}" in body
    assert "Test asunto" in body


def test_clientes_proximamente(client, usuario_factory):
    client.force_login(usuario_factory(rol="dueno"))
    resp = client.get("/buzon/clientes/")
    assert resp.status_code == 200
    assert b"Pr\xc3\xb3ximamente" in resp.content
