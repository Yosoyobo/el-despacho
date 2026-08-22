"""El botón «Enviar correo» de la ficha del cliente."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def cartero_espia(monkeypatch):
    enviados: list[dict] = []

    def _fake(*, destinatario, asunto, html, texto="", adjuntos=None, remitente=""):
        from lib.cartero import ResultadoCorreo
        enviados.append({"destinatario": destinatario, "asunto": asunto,
                         "html": html, "remitente": remitente})
        return ResultadoCorreo(ok=True, proveedor="smtp")

    monkeypatch.setattr("lib.cartero.enviar", _fake)
    return enviados


@pytest.fixture
def plantilla(db):
    from ajustes.models import PlantillaCorreo
    return PlantillaCorreo.objects.create(
        slug="aviso", nombre="Aviso", asunto="Hola {{ cliente }}",
        cuerpo_html="<p>Hola {{ cliente }}, de {{ empresa }}.</p>", activa=True,
    )


def test_el_modal_lista_las_plantillas(client, usuario_factory, cliente_factory, plantilla):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    resp = client.get(f"/cartera/{cliente.pk}/correo", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "Aviso" in resp.content.decode()


def test_manda_al_correo_registrado(
    client, usuario_factory, cliente_factory, plantilla, cartero_espia,
):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    cliente = cliente_factory(razon_social="Kari Kari", email_contacto="kari@ejemplo.com")
    resp = client.post(
        f"/cartera/{cliente.pk}/correo", {"plantilla": "aviso"}, HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    assert cartero_espia[0]["destinatario"] == "kari@ejemplo.com"
    assert "Kari Kari" in cartero_espia[0]["html"]


def test_un_cliente_sin_correo_lo_dice_en_vez_de_fallar(
    client, usuario_factory, cliente_factory, plantilla,
):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    cliente = cliente_factory(email_contacto="")
    resp = client.get(f"/cartera/{cliente.pk}/correo", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "no tiene correo de contacto" in resp.content.decode()


def test_una_plantilla_inventada_no_manda_nada(
    client, usuario_factory, cliente_factory, plantilla, cartero_espia,
):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    resp = client.post(
        f"/cartera/{cliente.pk}/correo", {"plantilla": "no-existe"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    assert cartero_espia == []


def test_sin_permiso_no_puede_enviar(client, usuario_factory, cliente_factory, plantilla):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    resp = client.get(f"/cartera/{cliente.pk}/correo", HTTP_HX_REQUEST="true")
    assert resp.status_code == 403


def test_si_el_envio_falla_lo_dice_sin_romperse(
    client, usuario_factory, cliente_factory, plantilla, monkeypatch,
):
    from lib.cartero import ResultadoCorreo

    monkeypatch.setattr(
        "lib.cartero.enviar",
        lambda **kw: ResultadoCorreo(ok=False, error="servidor caído"),
    )
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    resp = client.post(
        f"/cartera/{cliente.pk}/correo", {"plantilla": "aviso"}, HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    assert "servidor caído" in resp.content.decode()


# ── Elegir de quién sale ─────────────────────────────────────────────────────


def test_el_modal_ofrece_solo_lo_que_puedo_usar(
    client, usuario_factory, cliente_factory, plantilla,
):
    from ajustes.models import AliasRemitente

    jorge = usuario_factory(rol="super_admin")
    alex = usuario_factory(rol="super_admin")
    AliasRemitente.objects.filter(email="jorge@learningcenter.mx").update(usuario=jorge)
    AliasRemitente.objects.filter(email="alex@learningcenter.mx").update(usuario=alex)

    client.force_login(jorge)
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    resp = client.get(f"/cartera/{cliente.pk}/correo", HTTP_HX_REQUEST="true")
    ofrecidos = {a.email for a in resp.context["remitentes"]}
    assert "jorge@learningcenter.mx" in ofrecidos
    assert "cobranza@learningcenter.mx" in ofrecidos
    assert "alex@learningcenter.mx" not in ofrecidos


def test_manda_desde_el_alias_elegido(
    client, usuario_factory, cliente_factory, plantilla, cartero_espia,
):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    client.post(f"/cartera/{cliente.pk}/correo", {
        "plantilla": "aviso", "remitente": "cobranza@learningcenter.mx",
    }, HTTP_HX_REQUEST="true")
    assert cartero_espia[0]["remitente"] == (
        "COBRANZA | LEARNING CENTER <cobranza@learningcenter.mx>"
    )


def test_no_puedo_mandar_desde_el_alias_de_otro_aunque_lo_fuerce(
    client, usuario_factory, cliente_factory, plantilla, cartero_espia,
):
    """El `<select>` se puede manipular desde el navegador: el servidor decide."""
    from ajustes.models import AliasRemitente

    jorge = usuario_factory(rol="super_admin")
    alex = usuario_factory(rol="super_admin")
    AliasRemitente.objects.filter(email="jorge@learningcenter.mx").update(usuario=jorge)

    client.force_login(alex)
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    client.post(f"/cartera/{cliente.pk}/correo", {
        "plantilla": "aviso", "remitente": "jorge@learningcenter.mx",
    }, HTTP_HX_REQUEST="true")
    # Sale del remitente general, NUNCA firmado por Jorge.
    assert cartero_espia[0]["remitente"] == ""
