"""S-LC-Feedback-V13 — cobertura de las features nuevas con lógica de servidor:
anticipo→ingreso, Jornadas todos los días, eventos genéricos multi-día,
prioridad en crear_mensaje_buzon, borrado permanente de productos/proveedores.
"""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# ── Item 10: ejecutor crear_mensaje_buzon acepta prioridad ──
def test_ejecutor_buzon_acepta_prioridad(usuario_factory):
    from apps.el_dictado.ejecutores.basicos import crear_mensaje_buzon_ejec

    from buzon.models import MensajeBuzon

    admin = usuario_factory(rol="super_admin")

    class _Accion:
        payload = {"tipo": "sugerencia", "asunto": "Urgente", "cuerpo": "x", "prioridad": 9}

    crear_mensaje_buzon_ejec(_Accion(), admin)
    msg = MensajeBuzon.objects.get(asunto="Urgente")
    assert msg.prioridad == 9


def test_ejecutor_buzon_prioridad_default_y_acotada(usuario_factory):
    from apps.el_dictado.ejecutores.basicos import crear_mensaje_buzon_ejec

    from buzon.models import MensajeBuzon

    admin = usuario_factory(rol="super_admin")

    class _Sin:
        payload = {"asunto": "Normal", "cuerpo": "x"}

    class _Alta:
        payload = {"asunto": "Tope", "cuerpo": "x", "prioridad": 99}

    crear_mensaje_buzon_ejec(_Sin(), admin)
    crear_mensaje_buzon_ejec(_Alta(), admin)
    assert MensajeBuzon.objects.get(asunto="Normal").prioridad == 5
    assert MensajeBuzon.objects.get(asunto="Tope").prioridad == 10  # acotada a 0-10


# ── Item 9: Jornadas del Checador muestran todos los días ──
def test_jornadas_por_dia_incluye_dias_sin_checada(usuario_factory):
    from apps.checador import services
    from django.utils import timezone

    user = usuario_factory(rol="disenador")
    hoy = timezone.localdate()
    desde = hoy - dt.timedelta(days=6)
    filas = services.jornadas_por_dia(user, desde, hoy)
    # Una fila por cada día del rango (7 días, más reciente arriba).
    assert len(filas) == 7
    assert filas[0]["fecha"] == hoy
    estados = {f["estado"] for f in filas}
    assert estados <= {"registrada", "pendiente", "descanso"}
    # Sin jornadas registradas, ningún día es 'registrada'.
    assert "registrada" not in estados


# ── Item 2: eventos genéricos multi-día aparecen en cada celda del rango ──
def test_evento_multidia_aparece_en_todos_los_dias(usuario_factory):
    from apps.calendario.services import eventos_por_dia
    from apps.el_pizarron.models import Evento

    admin = usuario_factory(rol="super_admin")
    ini = dt.date(2026, 7, 6)
    fin = dt.date(2026, 7, 8)
    Evento.objects.create(titulo="Vacaciones", fecha_inicio=ini, fecha_fin=fin)
    evs = eventos_por_dia(admin, ini, fin)
    for d in (ini, ini + dt.timedelta(days=1), fin):
        titulos = [e["titulo"] for e in evs.get(d, [])]
        assert "Vacaciones" in titulos
    # marca de continuación: el primer día es_inicio, el último es_fin.
    assert any(e["es_inicio"] for e in evs[ini] if e["tipo"] == "evento")
    assert any(e["es_fin"] for e in evs[fin] if e["tipo"] == "evento")


def test_evento_fecha_fin_vacia_es_mismo_dia(usuario_factory):
    from apps.el_pizarron.models import Evento

    ev = Evento(titulo="Feriado", fecha_inicio=dt.date(2026, 7, 6), fecha_fin=None)
    ev.save()
    assert ev.fecha_fin == ev.fecha_inicio
    assert ev.es_multidia is False


# ── Item 8: anticipo → registro de ingreso ligado al proyecto ──
def test_registrar_anticipo_crea_ingreso_ligado_al_proyecto(client, usuario_factory, proyecto_factory):
    from apps.tesoreria.models import Ingreso

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="esperando_respuesta")
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/cotizacion/anticipo",
        data={"monto": "5000.00", "fecha": "2026-07-06", "metodo": "transferencia", "banco_o_caja": "banco"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code in (200, 204)
    ing = Ingreso.objects.filter(proyecto=p).first()
    assert ing is not None
    assert str(ing.monto) == "5000.00"
    assert "Anticipo" in ing.descripcion


def test_estado_anticipo_seedeado_en_tracker():
    from apps.cotizaciones.models import EstadoCotizacion
    assert EstadoCotizacion.objects.filter(slug="anticipo").exists()


# ── Item 3: borrado permanente de productos/proveedores ──
def _crear_servicio(nombre="Producto X"):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat = CategoriaServicio.objects.filter(activa=True).first() or CategoriaServicio.objects.create(
        nombre="Cat", color="#465fff", orden=1)
    return Servicio.objects.create(
        nombre=nombre, categoria=cat, precio_base=100, costo=50, unidad="pieza", activo=True)


def test_eliminar_producto_sin_uso(client, usuario_factory):
    from apps.el_catalogo.models import Servicio

    admin = usuario_factory(rol="super_admin")
    srv = _crear_servicio()
    client.force_login(admin)
    resp = client.post(f"/catalogo/{srv.pk}/eliminar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert not Servicio.objects.filter(pk=srv.pk).exists()


def test_no_se_elimina_producto_en_uso(client, usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    srv = _crear_servicio("En uso")
    p = proyecto_factory()
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=1)
    client.force_login(admin)
    resp = client.post(f"/catalogo/{srv.pk}/eliminar", HTTP_HX_REQUEST="true")
    # Se reinyecta el modal con el error; el producto NO se borra.
    assert resp.status_code == 200
    assert Servicio.objects.filter(pk=srv.pk).exists()


def test_eliminar_proveedor(client, usuario_factory):
    from apps.el_catalogo.models import Proveedor

    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social="Prov X", activo=True)
    client.force_login(admin)
    resp = client.post(f"/catalogo/proveedores/{prov.pk}/eliminar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert not Proveedor.objects.filter(pk=prov.pk).exists()
