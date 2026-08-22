"""Crear, borrar y probar plantillas desde La Gerencia + la pantalla de reglas."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_crear_plantilla_abre_su_editor(client, usuario_factory):
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/plantillas/nueva", {
        "nombre": "Aviso de entrega", "descripcion": "Cuando el pedido está listo",
    })
    pl = PlantillaCorreo.objects.get(nombre="Aviso de entrega")
    assert pl.sistema is False
    assert pl.activa is True
    assert resp.status_code == 302
    assert pl.slug in resp["Location"]


def test_dos_plantillas_con_el_mismo_nombre_no_chocan(client, usuario_factory):
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    for _ in range(2):
        client.post("/ajustes/cartero/plantillas/nueva", {"nombre": "Aviso"})
    assert PlantillaCorreo.objects.filter(nombre="Aviso").count() == 2


def test_una_plantilla_sin_nombre_no_se_crea(client, usuario_factory):
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    client.post("/ajustes/cartero/plantillas/nueva", {"nombre": "   "})
    assert not PlantillaCorreo.objects.filter(sistema=False).exists()


def test_borrar_una_propia(client, usuario_factory):
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    PlantillaCorreo.objects.create(slug="mia", nombre="Mía", activa=True)
    client.post("/ajustes/cartero/plantillas/mia/borrar")
    assert not PlantillaCorreo.objects.filter(slug="mia").exists()


def test_una_de_sistema_no_se_puede_borrar(client, usuario_factory):
    """Si desaparece, el correo que la usa se queda sin cuerpo."""
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    PlantillaCorreo.obtener("cotizacion")
    client.post("/ajustes/cartero/plantillas/cotizacion/borrar")
    assert PlantillaCorreo.objects.filter(slug="cotizacion").exists()


def test_una_plantilla_con_regla_no_se_borra_sin_avisar(client, usuario_factory):
    from ajustes.models import PlantillaCorreo, ReglaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    pl = PlantillaCorreo.objects.create(slug="mia", nombre="Mía", activa=True)
    ReglaCorreo.objects.create(evento="cotizacion_aprobada", plantilla=pl)
    client.post("/ajustes/cartero/plantillas/mia/borrar")
    assert PlantillaCorreo.objects.filter(slug="mia").exists()


def test_guardar_el_alias_del_remitente(client, usuario_factory):
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    PlantillaCorreo.objects.create(slug="mia", nombre="Mía", activa=True)
    client.post("/ajustes/cartero/plantillas/mia/", {
        "asunto": "Hola", "cuerpo_html": "<p>x</p>", "activa": "1",
        "remitente_email": "cobranza@learningcenter.mx",
        "remitente_nombre": "Cobranza Learning Center",
    })
    pl = PlantillaCorreo.objects.get(slug="mia")
    assert pl.remitente_efectivo() == "Cobranza Learning Center <cobranza@learningcenter.mx>"


def test_activar_un_borrador_del_chalan_lo_da_por_revisado(client, usuario_factory):
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    PlantillaCorreo.objects.create(
        slug="propuesta", nombre="Propuesta", activa=False, origen="chalan",
    )
    client.post("/ajustes/cartero/plantillas/propuesta/", {
        "asunto": "Hola", "cuerpo_html": "<p>x</p>", "activa": "1",
    })
    pl = PlantillaCorreo.objects.get(slug="propuesta")
    assert pl.activa is True
    assert pl.es_borrador is False


def test_la_lista_separa_las_propias_de_las_de_sistema(client, usuario_factory):
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    PlantillaCorreo.objects.create(slug="mia", nombre="Plantilla Mía", activa=True)
    resp = client.get("/ajustes/cartero/plantillas/")
    assert resp.status_code == 200
    assert "Plantilla Mía" in resp.content.decode()
    assert {p.slug for p in resp.context["propias"]} == {"mia"}
    assert "cotizacion" in {p.slug for p in resp.context["de_sistema"]}


def test_probar_manda_con_el_alias_de_la_plantilla(client, usuario_factory, monkeypatch):
    from ajustes.models import PlantillaCorreo

    capturado = {}

    def _fake(*, destinatario, asunto, html, texto="", adjuntos=None, remitente=""):
        from lib.cartero import ResultadoCorreo
        capturado.update({"destinatario": destinatario, "remitente": remitente})
        return ResultadoCorreo(ok=True, proveedor="smtp")

    monkeypatch.setattr("lib.cartero.enviar", _fake)
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    PlantillaCorreo.objects.create(
        slug="mia", nombre="Mía", asunto="Hola {{ cliente }}",
        cuerpo_html="<p>{{ cliente }}</p>", activa=True,
        remitente_email="cobranza@learningcenter.mx", remitente_nombre="Cobranza",
    )
    client.post("/ajustes/cartero/plantillas/mia/probar", {"destino": "yo@ejemplo.com"})
    assert capturado["destinatario"] == "yo@ejemplo.com"
    assert capturado["remitente"] == "Cobranza <cobranza@learningcenter.mx>"


# ── Reglas ───────────────────────────────────────────────────────────────────


def test_la_pantalla_de_reglas_carga(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/ajustes/cartero/reglas/")
    assert resp.status_code == 200


def test_crear_una_regla_la_deja_apagada(client, usuario_factory):
    from ajustes.models import PlantillaCorreo, ReglaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    pl = PlantillaCorreo.objects.create(slug="mia", nombre="Mía", activa=True)
    client.post("/ajustes/cartero/reglas/guardar", {
        "evento": "cotizacion_aprobada", "plantilla": pl.pk,
    })
    regla = ReglaCorreo.objects.get(evento="cotizacion_aprobada")
    assert regla.activa is False


def test_no_se_duplica_una_regla_del_mismo_evento(client, usuario_factory):
    from ajustes.models import PlantillaCorreo, ReglaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    pl = PlantillaCorreo.objects.create(slug="mia", nombre="Mía", activa=True)
    for _ in range(2):
        client.post("/ajustes/cartero/reglas/guardar", {
            "evento": "cotizacion_aprobada", "plantilla": pl.pk,
        })
    assert ReglaCorreo.objects.filter(evento="cotizacion_aprobada").count() == 1


def test_un_evento_inventado_se_rechaza(client, usuario_factory):
    from ajustes.models import PlantillaCorreo, ReglaCorreo

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    pl = PlantillaCorreo.objects.create(slug="mia", nombre="Mía", activa=True)
    client.post("/ajustes/cartero/reglas/guardar", {
        "evento": "lo_que_sea", "plantilla": pl.pk,
    })
    assert not ReglaCorreo.objects.exists()


def test_un_disenador_no_entra(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/ajustes/cartero/plantillas/")
    assert resp.status_code in (302, 403)


def test_una_plantilla_malformada_no_tumba_la_pantalla(client, usuario_factory):
    """Un pk no numérico daba 500 (ValueError) en vez de 404."""
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/ajustes/cartero/reglas/guardar", {
        "evento": "cotizacion_aprobada", "plantilla": "no-soy-un-numero",
    })
    assert resp.status_code == 404
