"""Una cotización rechazada (o anulada) se lee como perdida aunque el catálogo de
estados no tenga uno de esa fase.

El hallazgo (S5, 2026-09-29): `marcar_rechazada` cae al slug literal
«rechazada» cuando el despacho no tiene un estado activo de fase «perdida», y
ese slug —sin fila en el catálogo— se leía como «armada»; con su sello de envío,
`fase_efectiva` la devolvía a «enviada». Una rechazada contaba como viva en el
embudo y se podía aprobar después. Igual con «anulada», que se escribe siempre
literal. El arreglo lee esos slugs del sistema con su fase SIN tocar datos: las
cotizaciones que ya están guardadas así se leen bien desde hoy.
"""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def enviada(cliente_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion

    def _crear(**kw):
        return Cotizacion.objects.create(
            cliente=cliente_factory(), titulo="Propuesta", estado="enviada",
            enviada_en=dt.datetime.now(dt.UTC), creado_por=usuario_factory(rol="super_admin"), **kw)
    return _crear


def _sin_estado_perdido():
    """El catálogo de las pruebas no trae ninguno de fase perdida; se asegura."""
    from apps.cotizaciones.models import EstadoCotizacion
    from apps.cotizaciones.models.estado_cotizacion import invalidar_cache_estados_cot

    EstadoCotizacion.objects.filter(fase="perdida").delete()
    EstadoCotizacion.objects.filter(slug__in=["rechazada", "anulada"]).delete()
    invalidar_cache_estados_cot()


def test_rechazar_sin_estado_de_fase_perdida_deja_la_cotizacion_perdida(enviada):
    from apps.cotizaciones import services
    from apps.cotizaciones.embudo import fase_efectiva

    _sin_estado_perdido()
    cot = services.marcar_rechazada(enviada(), None, "Muy caro")
    assert cot.estado == "rechazada"
    assert fase_efectiva(cot) == "perdida"
    with pytest.raises(ValueError):
        services.marcar_aprobada(cot, None, nombre="Alguien")


def test_las_que_ya_estaban_guardadas_asi_se_leen_bien_sin_tocar_datos(enviada):
    from apps.cotizaciones.embudo import embudo, fase_efectiva
    from apps.cotizaciones.models import Cotizacion
    from apps.cotizaciones.models.estado_cotizacion import slugs_de_fase

    _sin_estado_perdido()
    rechazada, anulada, viva = enviada(), enviada(), enviada()
    Cotizacion.objects.filter(pk=rechazada.pk).update(estado="rechazada")
    Cotizacion.objects.filter(pk=anulada.pk).update(estado="anulada")
    rechazada.refresh_from_db()
    anulada.refresh_from_db()
    assert fase_efectiva(rechazada) == fase_efectiva(anulada) == "perdida"
    assert fase_efectiva(viva) == "enviada"
    perdidas = set(slugs_de_fase("perdida"))
    assert {"rechazada", "anulada"} <= perdidas
    assert set(Cotizacion.objects.filter(estado__in=perdidas).values_list("pk", flat=True)) == {
        rechazada.pk, anulada.pk}
    e = embudo()
    assert e["perdidas"] == 2 and e["enviadas"] == 1


def test_el_catalogo_manda_sobre_el_literal(enviada):
    """Si el despacho creó su propio estado «rechazada» con otra fase, se respeta."""
    from apps.cotizaciones.embudo import fase_efectiva
    from apps.cotizaciones.models import Cotizacion, EstadoCotizacion
    from apps.cotizaciones.models.estado_cotizacion import (
        invalidar_cache_estados_cot,
        slugs_de_fase,
    )

    EstadoCotizacion.objects.update_or_create(
        slug="rechazada", defaults={"label": "En renegociación", "fase": "enviada", "activo": True})
    invalidar_cache_estados_cot()
    cot = enviada()
    Cotizacion.objects.filter(pk=cot.pk).update(estado="rechazada")
    cot.refresh_from_db()
    assert fase_efectiva(cot) == "enviada"
    assert "rechazada" not in slugs_de_fase("perdida")
    assert slugs_de_fase("enviada").count("rechazada") == 1


def test_un_slug_desconocido_sigue_siendo_armada():
    from apps.cotizaciones.models.estado_cotizacion import fase_de

    assert fase_de("algo-que-nadie-conoce") == "armada"
    assert fase_de("aprobada") == "ganada"
