"""Cotizaciones versionadas POR PROYECTO (recuadro del detalle, render Oscar
2026-06-27).

Cubre:
- Service `generar_desde_proyecto`: snapshot de productos incluidos, versión
  correlativa, estado 'generada', impuestos default según IVA del proyecto.
- Service `marcar_estado_proyecto`: setter libre + timestamps + estado inválido.
- Vistas: generar (POST/HTMX), cambiar estado, permisos.
- El recuadro se pinta en el detalle y el botón Enviar apunta al placeholder.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def entorno(usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    srv1 = Servicio.objects.create(nombre="Taza", precio_base="100", costo="30", categoria=cat)
    srv2 = Servicio.objects.create(nombre="Playera", precio_base="80", costo="40", categoria=cat)
    p = proyecto_factory(nombre="Branding Optimist", creado_por=admin)
    incluido = ProyectoProducto.objects.create(
        proyecto=p, servicio=srv1, cantidad=3, incluir_en_calculo=True,
    )
    excluido = ProyectoProducto.objects.create(
        proyecto=p, servicio=srv2, cantidad=5, incluir_en_calculo=False,
    )
    return {"admin": admin, "p": p, "incluido": incluido, "excluido": excluido}


@pytest.fixture
def tasa_iva_default():
    from ajustes.models.tasa import TasaImpositiva
    return TasaImpositiva.objects.create(
        nombre="IVA 16%", porcentaje=Decimal("16.00"),
        tipo="trasladado", aplicable_default=True, activa=True, orden=10,
    )


# ── Service: generar_desde_proyecto ──────────────────────────────────────

def test_generar_v1_snapshot_solo_productos_incluidos(entorno):
    from apps.cotizaciones import services
    p = entorno["p"]
    cot = services.generar_desde_proyecto(p, entorno["admin"])
    assert cot.version == 1
    assert cot.estado == "generada"
    assert cot.cliente_id == p.cliente_id
    assert cot.proyecto_id == p.pk
    # Solo la línea incluida (3 × $100), no la excluida.
    items = list(cot.items.all())
    assert len(items) == 1
    it = items[0]
    assert it.cantidad == Decimal("3")
    assert it.precio_unitario == Decimal("100")
    assert "Taza" in it.descripcion


def test_generar_incrementa_version_y_conserva_la_previa(entorno):
    from apps.cotizaciones import services
    p = entorno["p"]
    v1 = services.generar_desde_proyecto(p, entorno["admin"])
    v2 = services.generar_desde_proyecto(p, entorno["admin"])
    assert v1.version == 1
    assert v2.version == 2
    assert v1.codigo != v2.codigo
    # v1 sigue existiendo, intacta.
    v1.refresh_from_db()
    assert v1.version == 1


def test_generar_agrega_iva_default_salvo_exento(entorno, tasa_iva_default):
    from apps.cotizaciones import services
    p = entorno["p"]
    cot = services.generar_desde_proyecto(p, entorno["admin"])
    assert cot.impuestos.count() == 1

    p.iva_exento = True
    p.save(update_fields=["iva_exento"])
    cot_exento = services.generar_desde_proyecto(p, entorno["admin"])
    assert cot_exento.impuestos.count() == 0


# ── Service: marcar_estado_proyecto ──────────────────────────────────────

def test_marcar_estado_sella_timestamp(entorno):
    from apps.cotizaciones import services
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    services.marcar_estado_proyecto(cot, "enviada", entorno["admin"])
    assert cot.estado == "enviada"
    assert cot.enviada_en is not None
    services.marcar_estado_proyecto(cot, "pagada", entorno["admin"])
    assert cot.estado == "pagada"
    assert cot.pagada_en is not None


def test_marcar_estado_invalido_lanza(entorno):
    from apps.cotizaciones import services
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    with pytest.raises(ValueError):
        services.marcar_estado_proyecto(cot, "rechazada", entorno["admin"])


# ── Vistas ───────────────────────────────────────────────────────────────

def test_vista_generar_crea_y_pinta_recuadro(client, entorno):
    client.force_login(entorno["admin"])
    resp = client.post(
        reverse("proyectos-generar-cotizacion", args=[entorno["p"].pk]),
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "v1" in cuerpo
    from apps.cotizaciones.models import Cotizacion
    assert Cotizacion.objects.filter(proyecto=entorno["p"], version=1).exists()


def test_vista_cambiar_estado(client, entorno):
    from apps.cotizaciones import services
    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    client.force_login(entorno["admin"])
    resp = client.post(
        reverse("proyectos-cotizacion-estado", args=[entorno["p"].pk, cot.pk]),
        {"estado": "aprobada"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    cot.refresh_from_db()
    assert cot.estado == "aprobada"
    assert cot.aprobada_en is not None


def test_disenador_sin_permiso_no_genera(client, usuario_factory, entorno):
    diseñador = usuario_factory(rol="disenador")
    client.force_login(diseñador)
    resp = client.post(
        reverse("proyectos-generar-cotizacion", args=[entorno["p"].pk]),
    )
    assert resp.status_code == 403


def test_detalle_pinta_recuadro_y_boton_enviar_placeholder(client, entorno):
    from apps.cotizaciones import services
    from apps.los_proyectos.views import RICKROLL_URL
    services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    client.force_login(entorno["admin"])
    resp = client.get(reverse("proyectos-detalle", args=[entorno["p"].pk]))
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "Cotizaciones" in cuerpo
    assert "v1" in cuerpo
    # El botón Enviar es placeholder → apunta al rickroll (decisión Oscar).
    assert RICKROLL_URL in cuerpo
