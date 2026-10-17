"""Oscar 2026-10-14: «Nuevo ingreso» ofrece registrar lo que falta del proyecto y
ligar el cobro a una factura (con 1–2 sugeridas según el monto).

El ligado reutiliza las reglas del cobro de la factura (`validar_cobro`): el
monto no puede exceder el saldo y la factura debe estar emitida/parcial.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

D = Decimal


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    return u


def _factura(proyecto, total, *, estado="emitida", dias_atras=0, autor=None):
    """Factura sin impuestos (régimen iva sin tasas) → total == base."""
    from apps.facturacion.models import Factura, FacturaItem
    fac = Factura.objects.create(
        cliente=proyecto.cliente, proyecto=proyecto, titulo="F", concepto="Lonas",
        regimen_fiscal="iva", creado_por=autor, estado=estado,
        fecha_emision=date.today() - timedelta(days=dias_atras))
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="Servicio", cantidad=D("1"), unidad="pieza",
        precio_unitario=D(str(total)), descuento_porcentaje=D("0"))
    return fac


def _post(client, proyecto, **extra):
    datos = {"fecha": date.today().isoformat(), "metodo": "transferencia",
             "descripcion": "Cobro", "proyecto": str(proyecto.pk),
             "regimen_fiscal": "exento"}
    datos.update(extra)
    return client.post("/tesoreria/ingresos/nuevo/", datos, HTTP_HX_REQUEST="true")


# ── Sugerencias (servicio) ───────────────────────────────────────────────────

def test_sugeridas_prefiere_saldo_exacto_luego_total_luego_mitad(proyecto_factory):
    from apps.facturacion import services
    p = proyecto_factory()
    exacta = _factura(p, "500.00", dias_atras=1)
    grande = _factura(p, "1000.00", dias_atras=5)
    s = services.facturas_sugeridas(proyecto=p, monto="500.00")
    assert [x["factura"].pk for x in s] == [exacta.pk, grande.pk]
    assert s[0]["razon"] == "Cubre justo lo que falta"
    assert s[1]["razon"] == "Es el 50% de la factura"
    # el total exacto va antes que «cabe en su saldo»
    s2 = services.facturas_sugeridas(proyecto=p, monto="1000.00")
    assert [x["factura"].pk for x in s2] == [grande.pk]
    assert s2[0]["razon"] == "Cubre justo lo que falta"


def test_sugeridas_excluye_las_que_no_aceptan_el_monto(proyecto_factory):
    from apps.facturacion import services
    p = proyecto_factory()
    chica = _factura(p, "100.00")
    _factura(p, "900.00", estado="borrador")
    _factura(p, "900.00", estado="cancelada")
    _factura(p, "900.00", estado="cobrada_total")
    s = services.facturas_sugeridas(proyecto=p, monto="300.00")
    assert s == []  # la única cobrable (100) no alcanza para 300
    assert [x["factura"].pk for x in services.facturas_sugeridas(proyecto=p, monto="100.00")] == [chica.pk]


def test_sugeridas_sin_monto_son_las_dos_mas_antiguas_y_max_dos(proyecto_factory):
    from apps.facturacion import services
    p = proyecto_factory()
    viejas = [_factura(p, "100.00", dias_atras=d) for d in (30, 20, 10)]
    s = services.facturas_sugeridas(proyecto=p)
    assert [x["factura"].pk for x in s] == [viejas[0].pk, viejas[1].pk]
    assert len(services.facturas_sugeridas(proyecto=p, monto="100")) == 2


def test_sugeridas_respeta_el_saldo_tras_cobros_parciales(proyecto_factory, usuario_factory):
    from apps.facturacion import services
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    fac = _factura(p, "1000.00", autor=u)
    services.registrar_cobro(fac, monto=D("400"), fecha=date.today(), metodo="transferencia", actor=u)
    s = services.facturas_sugeridas(proyecto=p, monto="600.00")
    assert s[0]["razon"] == "Cubre justo lo que falta" and s[0]["saldo"] == D("600.00")


# ── API ──────────────────────────────────────────────────────────────────────

def test_api_facturas_sugeridas(client, admin, proyecto_factory):
    p = proyecto_factory()
    f = _factura(p, "500.00")
    d = client.get("/tesoreria/api/facturas-sugeridas/", {"proyecto": p.pk, "monto": "500"}).json()
    assert [o["id"] for o in d["opciones"]] == [f.pk]
    assert d["sugeridas"][0]["id"] == f.pk and d["sugeridas"][0]["razon"]


def test_api_facturas_exige_permiso_de_cobrar(client, usuario_factory, proyecto_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    u = usuario_factory(rol="dueno")
    PermisoUsuario.objects.update_or_create(
        usuario=u, modulo="facturacion", permiso="cobrar", defaults={"activo": False})
    client.force_login(u)
    p = proyecto_factory()
    assert client.get("/tesoreria/api/facturas-sugeridas/", {"proyecto": p.pk}).status_code == 403


# ── Guardado ─────────────────────────────────────────────────────────────────

def test_ingreso_ligado_a_factura_descuenta_su_saldo_y_cambia_estado(client, admin, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory()
    fac = _factura(p, "1000.00")
    assert _post(client, p, subtotal="400.00", factura=str(fac.pk)).status_code == 204
    i = Ingreso.objects.get()
    fac.refresh_from_db()
    assert i.factura_id == fac.pk
    assert (fac.monto_cobrado, fac.estado) == (D("400.00"), "cobrada_parcial")
    _post(client, p, subtotal="600.00", factura=str(fac.pk))
    fac.refresh_from_db()
    assert (fac.monto_cobrado, fac.estado) == (D("1000.00"), "cobrada_total")


def test_ingreso_ligado_usa_cxc_como_contracuenta(client, admin, proyecto_factory):
    from apps.contaduria.models import Asiento
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory()
    fac = _factura(p, "1000.00")
    _post(client, p, subtotal="400.00", factura=str(fac.pk))
    i = Ingreso.objects.get()
    a = Asiento.vigentes.get(referencia_externa=f"tesoreria.ingreso:{i.pk}", origen="auto_ingreso")
    assert a.partidas.filter(abono__gt=0).first().cuenta.slot == "cxc"


def test_monto_mayor_al_saldo_se_rechaza_y_no_guarda_nada(client, admin, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory()
    fac = _factura(p, "300.00")
    resp = _post(client, p, subtotal="301.00", factura=str(fac.pk))
    assert resp.status_code == 200  # re-render del modal con el error
    assert "excede el saldo" in resp.content.decode()
    assert Ingreso.objects.count() == 0
    fac.refresh_from_db()
    assert fac.monto_cobrado == D("0.00")


def test_factura_de_otro_proyecto_se_rechaza(client, admin, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    p1, p2 = proyecto_factory(), proyecto_factory()
    fac = _factura(p2, "300.00")
    resp = _post(client, p1, subtotal="100.00", factura=str(fac.pk))
    assert resp.status_code == 200 and "otro proyecto" in resp.content.decode()
    assert Ingreso.objects.count() == 0


def test_factura_no_cobrable_se_rechaza(client, admin, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory()
    fac = _factura(p, "300.00", estado="borrador")
    assert _post(client, p, subtotal="100.00", factura=str(fac.pk)).status_code == 200
    assert Ingreso.objects.count() == 0


def test_sin_permiso_de_cobrar_no_hay_campo_y_se_ignora_la_factura(client, usuario_factory, proyecto_factory):
    from apps.tesoreria.models import Ingreso

    from cuentas.models.permiso_usuario import PermisoUsuario
    u = usuario_factory(rol="dueno")
    PermisoUsuario.objects.update_or_create(
        usuario=u, modulo="facturacion", permiso="cobrar", defaults={"activo": False})
    client.force_login(u)
    p = proyecto_factory()
    fac = _factura(p, "300.00")
    html = client.get(f"/tesoreria/ingresos/nuevo/?proyecto={p.pk}&desde=proyecto",
                      HTTP_HX_REQUEST="true").content.decode()
    assert "data-ligar-factura" not in html
    _post(client, p, subtotal="100.00", factura=str(fac.pk))
    assert Ingreso.objects.get().factura_id is None
    fac.refresh_from_db()
    assert fac.monto_cobrado == D("0.00")


def test_cobro_normal_de_la_factura_sigue_igual(proyecto_factory, usuario_factory):
    """El refactor de `registrar_cobro` no cambia su comportamiento."""
    from apps.facturacion import services
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    fac = _factura(p, "1000.00", autor=u)
    services.registrar_cobro(fac, monto=D("1000"), fecha=date.today(), metodo="transferencia", actor=u)
    fac.refresh_from_db()
    assert fac.estado == "cobrada_total"
    with pytest.raises(ValueError):
        services.registrar_cobro(fac, monto=D("1"), fecha=date.today(), metodo="transferencia", actor=u)


# ── «Registrar lo que falta» ─────────────────────────────────────────────────

def test_modal_muestra_registrar_lo_que_falta_solo_con_ingresos_previos(client, admin, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory(iva_exento=True)
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    cat = CategoriaServicio.objects.create(nombre="Cat F", color="#465fff", orden=1)
    serv = Servicio.objects.create(nombre="X", categoria=cat, precio_base=1000, costo=1,
                                   unidad="pieza", activo=True)
    ProyectoProducto.objects.create(proyecto=p, servicio=serv, cantidad=1,
                                    precio_unitario=D("1000"), incluir_en_calculo=True)
    url = f"/tesoreria/ingresos/nuevo/?proyecto={p.pk}&desde=proyecto"
    html = client.get(url, HTTP_HX_REQUEST="true").content.decode()
    assert "data-mr-falta" in html            # el botón existe en el markup (lo oculta JS)
    assert 'data-cobrado=""' in html          # sin ingresos previos → sin «ya cobrado»
    Ingreso.objects.create(proyecto=p, cliente=p.cliente, monto=D("400"), subtotal=D("400"),
                           fecha=date.today(), descripcion="Anticipo")
    html = client.get(url, HTTP_HX_REQUEST="true").content.decode()
    assert 'data-cobrado="400.00"' in html and 'data-saldo="600.00"' in html
    # la API también lo expone para cuando se elige el proyecto en el dropdown
    d = client.get(f"/tesoreria/api/proyecto/{p.pk}/datos/").json()
    assert d["total_cobrado"] == "400.00" and d["saldo_por_cobrar"] == "600.00"
