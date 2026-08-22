"""Plantillas propias, remitente por alias y reglas evento → correo.

Lo que estos tests cuidan, en orden de qué duele más si se rompe:

1. Que una plantilla propia se pueda crear y mandar (era el pedido).
2. Que el alias de remitente viaje hasta El Cartero — si se pierde, el correo
   sale desde la dirección de siempre y NADIE se entera.
3. Que una regla no le escriba dos veces al mismo cliente por el mismo hecho.
4. Que las reglas nazcan apagadas: encender un correo automático es una
   decisión, no un efecto secundario de crear la fila.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def plantilla_propia(db):
    from ajustes.models import PlantillaCorreo

    def _crear(**kwargs):
        datos = {
            "slug": "aviso-entrega", "nombre": "Aviso de entrega",
            "asunto": "Tu pedido está listo, {{ cliente }}",
            "cuerpo_html": "<p>Hola {{ cliente }}, tu proyecto {{ proyecto }} ya está.</p>",
            "activa": True, "sistema": False, "origen": "manual",
        }
        datos.update(kwargs)
        return PlantillaCorreo.objects.create(**datos)

    return _crear


@pytest.fixture
def cartero_espia(monkeypatch):
    """Intercepta los envíos para poder mirarlos, sin tocar la red."""
    enviados: list[dict] = []

    def _fake(*, destinatario, asunto, html, texto="", adjuntos=None, remitente=""):
        from lib.cartero import ResultadoCorreo
        enviados.append({
            "destinatario": destinatario, "asunto": asunto,
            "html": html, "remitente": remitente,
        })
        return ResultadoCorreo(ok=True, proveedor="smtp", detalle="ok")

    monkeypatch.setattr("lib.cartero.enviar", _fake)
    return enviados


# ── El modelo ────────────────────────────────────────────────────────────────


def test_una_plantilla_propia_no_es_de_sistema(plantilla_propia):
    pl = plantilla_propia()
    assert pl.sistema is False
    assert pl in type(pl).enviables()


def test_las_de_sistema_se_reconocen_por_su_slug():
    from ajustes.models import PlantillaCorreo

    assert PlantillaCorreo.obtener("cotizacion").sistema is True
    assert PlantillaCorreo.obtener("inventada-hoy").sistema is False


def test_generico_no_se_ofrece_para_enviar():
    """Es el molde del texto libre, no una plantilla que se elija."""
    from ajustes.models import PlantillaCorreo

    PlantillaCorreo.obtener("generico")
    assert not PlantillaCorreo.enviables().filter(slug="generico").exists()


def test_una_plantilla_apagada_no_se_puede_elegir(plantilla_propia):
    from ajustes.models import PlantillaCorreo

    pl = plantilla_propia(activa=False)
    assert pl not in PlantillaCorreo.enviables()


def test_borrador_del_chalan_se_distingue_de_una_apagada_a_mano(plantilla_propia):
    borrador = plantilla_propia(slug="b1", activa=False, origen="chalan")
    apagada = plantilla_propia(slug="b2", activa=False, origen="manual")
    assert borrador.es_borrador is True
    assert apagada.es_borrador is False


# ── El alias del remitente ───────────────────────────────────────────────────


def test_el_alias_arma_nombre_y_correo(plantilla_propia):
    pl = plantilla_propia(
        remitente_email="cobranza@learningcenter.mx",
        remitente_nombre="Cobranza Learning Center",
    )
    assert pl.remitente_efectivo() == "Cobranza Learning Center <cobranza@learningcenter.mx>"


def test_sin_alias_el_remitente_queda_vacio_para_que_mande_el_global(plantilla_propia):
    assert plantilla_propia().remitente_efectivo() == ""


def test_el_alias_pisa_al_remitente_global(monkeypatch):
    """El caso que importa: si esto se rompe, el correo sale desde la dirección
    de siempre y no hay error que lo delate."""
    from lib import cartero

    monkeypatch.setattr(cartero, "_cred", lambda c: {
        "smtp_from_email": "hola@learningcenter.mx",
    }.get(c, ""))
    assert cartero._remitente("Cobranza <cobranza@learningcenter.mx>") == (
        "Cobranza <cobranza@learningcenter.mx>"
    )
    assert "hola@learningcenter.mx" in cartero._remitente()


# ── El contexto de variables ─────────────────────────────────────────────────


def test_una_variable_nunca_falta_aunque_no_aplique():
    from ajustes.plantillas_correo_default import VARIABLES_LIBRES
    from lib import correo_contexto

    ctx = correo_contexto.armar()
    for var in VARIABLES_LIBRES:
        assert var in ctx, f"falta {var}"


def test_el_contexto_toma_los_datos_del_proyecto(proyecto_factory):
    from lib import correo_contexto

    proyecto = proyecto_factory(nombre="Playeras Dry Fit")
    ctx = correo_contexto.armar(proyecto=proyecto)
    assert ctx["proyecto"] == "Playeras Dry Fit"
    assert ctx["empresa"] == proyecto.cliente.razon_social


def test_lo_que_se_pasa_a_mano_gana_sobre_lo_derivado(proyecto_factory):
    from lib import correo_contexto

    proyecto = proyecto_factory(nombre="Original")
    ctx = correo_contexto.armar(proyecto=proyecto, extra={"proyecto": "Corregido"})
    assert ctx["proyecto"] == "Corregido"


# ── Las reglas ───────────────────────────────────────────────────────────────


def test_una_regla_nace_apagada(plantilla_propia):
    from ajustes.models import ReglaCorreo

    regla = ReglaCorreo.objects.create(
        evento="cotizacion_aprobada", plantilla=plantilla_propia(),
    )
    assert regla.activa is False
    assert regla not in ReglaCorreo.activas_de("cotizacion_aprobada")


def test_una_regla_sin_su_filtro_no_esta_completa(plantilla_propia):
    from ajustes.models import ReglaCorreo

    regla = ReglaCorreo.objects.create(
        evento="proyecto_estado", plantilla=plantilla_propia(), activa=True,
    )
    assert regla.esta_completa is False


def test_la_regla_manda_el_correo_al_cliente(
    plantilla_propia, cliente_factory, proyecto_factory, cartero_espia,
):
    from ajustes.models import ReglaCorreo
    from lib import reglas_correo

    cliente = cliente_factory(email_contacto="cliente@ejemplo.com")
    proyecto = proyecto_factory(cliente=cliente, nombre="Gorras MAU")
    ReglaCorreo.objects.create(
        evento="cotizacion_aprobada", plantilla=plantilla_propia(), activa=True,
    )

    enviados = reglas_correo.disparar(
        "cotizacion_aprobada", referencia="cotizacion:1", proyecto=proyecto,
    )
    assert enviados == 1
    assert cartero_espia[0]["destinatario"] == "cliente@ejemplo.com"
    assert "Gorras MAU" in cartero_espia[0]["html"]


def test_el_alias_de_la_plantilla_llega_hasta_el_envio(
    plantilla_propia, cliente_factory, proyecto_factory, cartero_espia,
):
    from ajustes.models import ReglaCorreo
    from lib import reglas_correo

    cliente = cliente_factory(email_contacto="cliente@ejemplo.com")
    proyecto = proyecto_factory(cliente=cliente)
    ReglaCorreo.objects.create(
        evento="cotizacion_aprobada", activa=True,
        plantilla=plantilla_propia(
            remitente_email="cobranza@learningcenter.mx",
            remitente_nombre="Cobranza",
        ),
    )
    reglas_correo.disparar("cotizacion_aprobada", referencia="c:1", proyecto=proyecto)
    assert cartero_espia[0]["remitente"] == "Cobranza <cobranza@learningcenter.mx>"


def test_el_mismo_hecho_no_se_avisa_dos_veces(
    plantilla_propia, cliente_factory, proyecto_factory, cartero_espia,
):
    """Un proyecto que va y vuelve de estado no debe bombardear al cliente."""
    from ajustes.models import ReglaCorreo
    from lib import reglas_correo

    cliente = cliente_factory(email_contacto="cliente@ejemplo.com")
    proyecto = proyecto_factory(cliente=cliente)
    ReglaCorreo.objects.create(
        evento="cotizacion_aprobada", plantilla=plantilla_propia(), activa=True,
    )
    for _ in range(3):
        reglas_correo.disparar(
            "cotizacion_aprobada", referencia="cotizacion:7", proyecto=proyecto,
        )
    assert len(cartero_espia) == 1


def test_hechos_distintos_si_se_avisan_por_separado(
    plantilla_propia, cliente_factory, proyecto_factory, cartero_espia,
):
    from ajustes.models import ReglaCorreo
    from lib import reglas_correo

    cliente = cliente_factory(email_contacto="cliente@ejemplo.com")
    proyecto = proyecto_factory(cliente=cliente)
    ReglaCorreo.objects.create(
        evento="cotizacion_aprobada", plantilla=plantilla_propia(), activa=True,
    )
    reglas_correo.disparar("cotizacion_aprobada", referencia="cotizacion:1", proyecto=proyecto)
    reglas_correo.disparar("cotizacion_aprobada", referencia="cotizacion:2", proyecto=proyecto)
    assert len(cartero_espia) == 2


def test_un_cliente_sin_correo_no_rompe_nada(
    plantilla_propia, cliente_factory, proyecto_factory, cartero_espia,
):
    from ajustes.models import ReglaCorreo
    from lib import reglas_correo

    cliente = cliente_factory(email_contacto="")
    proyecto = proyecto_factory(cliente=cliente)
    ReglaCorreo.objects.create(
        evento="cotizacion_aprobada", plantilla=plantilla_propia(), activa=True,
    )
    assert reglas_correo.disparar(
        "cotizacion_aprobada", referencia="c:1", proyecto=proyecto,
    ) == 0
    assert cartero_espia == []


def test_si_el_correo_falla_la_operacion_no_se_cae(
    plantilla_propia, cliente_factory, proyecto_factory, monkeypatch,
):
    """El principio de todo el módulo: entregar un proyecto no puede fallar
    porque el servidor de correo esté caído."""
    from ajustes.models import ReglaCorreo
    from lib import reglas_correo

    def _explota(**kwargs):
        raise RuntimeError("servidor caído")

    monkeypatch.setattr("lib.cartero.enviar", _explota)
    cliente = cliente_factory(email_contacto="cliente@ejemplo.com")
    proyecto = proyecto_factory(cliente=cliente)
    ReglaCorreo.objects.create(
        evento="cotizacion_aprobada", plantilla=plantilla_propia(), activa=True,
    )
    assert reglas_correo.disparar(
        "cotizacion_aprobada", referencia="c:1", proyecto=proyecto,
    ) == 0


def test_la_regla_de_estado_solo_dispara_con_su_estado(
    plantilla_propia, cliente_factory, proyecto_factory, cartero_espia,
):
    from ajustes.models import ReglaCorreo
    from lib import reglas_correo

    cliente = cliente_factory(email_contacto="cliente@ejemplo.com")
    proyecto = proyecto_factory(cliente=cliente)
    ReglaCorreo.objects.create(
        evento="proyecto_estado", plantilla=plantilla_propia(),
        activa=True, estado_slug="entregado",
    )
    reglas_correo.proyecto_cambio_estado(proyecto, "en_proceso_diseno")
    assert cartero_espia == []
    reglas_correo.proyecto_cambio_estado(proyecto, "entregado")
    assert len(cartero_espia) == 1
