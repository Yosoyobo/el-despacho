"""Ajustes LC del 2026-07-25 (8 puntos de Oscar).

- Buscador de productos encuentra por nombre de PROVEEDOR (lista + combobox).
- Ficha del producto: proveedores con dropdown-buscador + pastillas.
- Crear producto abre SU página (no la lista).
- Pagos pendientes sin registrar: cantidades como «× 35 pz» (sin «30 + 5 merma»).
- «Proyectos» (breadcrumbs/navegación) siempre lleva al Kanban.
- Lista de proyectos: orden alfabético por cliente.
- Eliminar proyecto: solo bloquean movimientos VIGENTES y se enlistan.
- Producto con impresión + procesos adicionales como plantilla → se copian al
  proyecto.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def categoria(db):
    from apps.el_catalogo.models import CategoriaServicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat Jul25", defaults={"orden": 90})
    return cat


def _servicio(categoria, nombre="Playera", **kw):
    from apps.el_catalogo.models import Servicio
    return Servicio.objects.create(
        nombre=nombre, categoria=categoria,
        precio_base=kw.pop("precio_base", Decimal("200.00")),
        costo=kw.pop("costo", Decimal("80.00")), activo=True, **kw,
    )


def _proveedor(razon="Simil Cuero Plymouth"):
    from apps.el_catalogo.models import Proveedor
    return Proveedor.objects.create(razon_social=razon, activo=True)


# ── #1 buscador de productos por proveedor ───────────────────────────────


def test_buscador_productos_encuentra_por_proveedor(client, usuario_factory, categoria):
    srv = _servicio(categoria, nombre="Cartera de piel")
    srv.proveedores.add(_proveedor("Plymouth Pieles"))
    _servicio(categoria, nombre="Taza cerámica")  # sin ese proveedor
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/catalogo/", {"q": "Plymouth"})
    assert resp.status_code == 200
    assert b"Cartera de piel" in resp.content
    assert b"Taza cer" not in resp.content


def test_producto_sin_match_de_proveedor_no_sale(client, usuario_factory, categoria):
    _servicio(categoria, nombre="Taza cerámica")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/catalogo/", {"q": "Plymouth"})
    assert b"Taza cer" not in resp.content


def test_combobox_de_cotizacion_marca_proveedor_para_busqueda(categoria):
    """El `<option>` del Producto lleva `data-buscar` con sus proveedores, que es
    lo que el combobox canónico matchea además del texto visible."""
    from apps.cotizaciones.forms import CotizacionItemForm
    srv = _servicio(categoria, nombre="Gorra bordada")
    srv.proveedores.add(_proveedor("Bordados del Norte"))
    html = str(CotizacionItemForm()["servicio"])
    assert 'data-select-buscable' in html
    assert 'data-buscar="Bordados del Norte"' in html


# ── #2 proveedores con dropdown-buscador + pastillas ─────────────────────


def test_ficha_producto_usa_dropdown_buscable_de_proveedor(client, usuario_factory, categoria):
    srv = _servicio(categoria)
    _proveedor("Proveedor Uno")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/catalogo/{srv.pk}/editar")
    assert resp.status_code == 200
    html = resp.content.decode()
    # LC 2026-08-28 (Oscar): el desplegable que agregaba, las pastillas y el
    # selector del ★ se unificaron en UN solo control — el de palomitas con
    # buscador—, y el primero que se marca queda como principal. Lo que este
    # test cuida sigue siendo lo mismo: que la ficha tenga un buscador de
    # proveedores y no la parrilla de casillas de antes.
    assert 'data-multi-buscable="proveedor"' in html
    assert 'data-multi-orden' in html
    # Los controles viejos (los tres) ya no existen.
    assert 'id="prov-filtro"' not in html
    assert 'id="prov-picker"' not in html


# ── #3 crear producto abre su página ─────────────────────────────────────


def test_crear_producto_redirige_a_su_pagina(client, usuario_factory, categoria):
    from apps.el_catalogo.models import Servicio
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/catalogo/nuevo", {
        "nombre": "Termo 500ml", "precio_base": "250.00", "costo": "100.00",
        "categoria": categoria.pk,
    })
    srv = Servicio.objects.get(nombre="Termo 500ml")
    assert resp.status_code == 302
    assert resp["Location"] == f"/catalogo/{srv.pk}/editar"


def test_crear_producto_htmx_redirige_a_su_pagina(client, usuario_factory, categoria):
    from apps.el_catalogo.models import Servicio
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post("/catalogo/nuevo", {
        "nombre": "Libreta", "precio_base": "80.00", "costo": "30.00",
        "categoria": categoria.pk,
    }, HTTP_HX_REQUEST="true")
    srv = Servicio.objects.get(nombre="Libreta")
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == f"/catalogo/{srv.pk}/editar"


# ── #4 «× 35 pz» en pagos pendientes ─────────────────────────────────────


def test_label_gasto_producto_es_por_piezas_totales(proyecto_factory, categoria):
    from apps.los_proyectos.gastos import iter_unidades
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(categoria, nombre="Bolsa"),
        cantidad=30, merma=5, costo_unitario=Decimal("10.00"),
        incluir_en_calculo=True,
    )
    labels = [u["label"] for u in iter_unidades(p)]
    assert any("× 35 pz" in x for x in labels)
    assert not any("merma" in x for x in labels)


def test_label_gasto_sin_merma_tambien_lleva_por(proyecto_factory, categoria):
    from apps.los_proyectos.gastos import iter_unidades
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(categoria, nombre="Llavero"),
        cantidad=12, costo_unitario=Decimal("5.00"), incluir_en_calculo=True,
    )
    assert any("× 12 pz" in u["label"] for u in iter_unidades(p))


# ── #5 «Proyectos» → Kanban ──────────────────────────────────────────────


def test_breadcrumb_de_proyecto_apunta_al_kanban(client, usuario_factory, proyecto_factory):
    p = proyecto_factory()
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    migas = resp.context["breadcrumb_items"]
    assert migas[0]["label"] == "Proyectos"
    assert migas[0]["url"] == "/proyectos/kanban/"
    assert resp.context["back_url"] == "/proyectos/kanban/"


# ── #6 orden alfabético por cliente ──────────────────────────────────────


def test_lista_proyectos_ordena_por_cliente(client, usuario_factory, cliente_factory,
                                            proyecto_factory):
    zeta = cliente_factory(razon_social="Zeta Restaurantes")
    alfa = cliente_factory(razon_social="Alfa Cafeterías")
    proyecto_factory(cliente=zeta, nombre="Proy Z")
    proyecto_factory(cliente=alfa, nombre="Proy A")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/proyectos/", {"orden": "cliente"})
    assert resp.status_code == 200
    nombres = [x.cliente.razon_social for x in resp.context["proyectos"]]
    assert nombres == sorted(nombres)
    # Y la cabecera «Cliente» es ordenable.
    assert any(c.get("sort_key") == "cliente" for c in resp.context["cabeceras_proyectos"])


# ── #7 ligado eficaz para eliminar ───────────────────────────────────────


def _factura(proyecto, estado="emitida"):
    import datetime as dt

    from apps.facturacion.models import Factura
    return Factura.objects.create(
        cliente=proyecto.cliente, proyecto=proyecto, estado=estado,
        concepto="Servicios", fecha_emision=dt.date(2026, 7, 1),
        fecha_vencimiento=dt.date(2026, 7, 31),
    )


def test_factura_cancelada_no_bloquea_eliminar(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import Proyecto
    p = proyecto_factory()
    _factura(p, estado="cancelada")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(f"/proyectos/{p.pk}/eliminar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert not Proyecto.objects.filter(pk=p.pk).exists()


def test_ingreso_anulado_no_bloquea_eliminar(client, usuario_factory, proyecto_factory):
    import datetime as dt

    from apps.los_proyectos.models import Proyecto
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory()
    Ingreso.objects.create(
        codigo="ING-2026-9001", proyecto=p, cliente=p.cliente,
        monto=Decimal("100.00"), subtotal=Decimal("100.00"),
        descripcion="Cobro", fecha=dt.date(2026, 7, 1), anulado=True,
    )
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(f"/proyectos/{p.pk}/eliminar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert not Proyecto.objects.filter(pk=p.pk).exists()


def test_factura_vigente_bloquea_y_se_enlista(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import Proyecto
    p = proyecto_factory()
    fac = _factura(p, estado="emitida")
    client.force_login(usuario_factory(rol="super_admin"))
    # El modal muestra exactamente qué lo bloquea, con enlace.
    modal = client.get(f"/proyectos/{p.pk}/eliminar", HTTP_HX_REQUEST="true")
    assert modal.status_code == 200
    html = modal.content.decode()
    assert "Factura" in html and f"/facturacion/{fac.pk}/" in html
    # Y el POST no borra.
    resp = client.post(f"/proyectos/{p.pk}/eliminar", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204  # 204 + HX-Redirect al detalle, con mensaje de error
    assert Proyecto.objects.filter(pk=p.pk).exists()


# ── #8 impresión + procesos adicionales del producto ─────────────────────


def test_producto_guarda_impresion_y_procesos(client, usuario_factory, categoria):
    from apps.el_catalogo.models import Servicio
    prov = _proveedor("Serigrafía MX")
    srv = _servicio(categoria, nombre="Playera lisa")
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(f"/catalogo/{srv.pk}/editar", {
        "nombre": "Playera lisa", "precio_base": "200.00", "costo": "80.00",
        "categoria": categoria.pk,
        "procesos_default_json": json.dumps([
            {"tipo": "impresion", "proveedor_id": prov.pk, "costo": "12.50", "por_pieza": True},
            {"tipo": "operativo", "descripcion": "Embalaje", "costo": "30.00", "por_pieza": False},
        ]),
    })
    assert resp.status_code == 302
    srv = Servicio.objects.get(pk=srv.pk)
    assert len(srv.procesos_default) == 2
    imp = srv.procesos_default[0]
    assert imp["tipo"] == "impresion" and imp["proveedor_id"] == prov.pk
    assert imp["costo"] == "12.50" and imp["por_pieza"] is True
    op = srv.procesos_default[1]
    assert op["descripcion"] == "Embalaje" and op["por_pieza"] is False
    # El costo del producto NO se infla con los procesos (el proyecto los cuenta
    # aparte; sumarlos aquí duplicaría el gasto).
    assert srv.costo == Decimal("80.00")


def test_procesos_default_descarta_basura(categoria):
    """JSON inválido, proveedor inexistente, montos negativos ⇒ se descartan."""
    from apps.el_catalogo import procesos as pd
    assert pd.parsear({"procesos_default_json": "no-es-json"}) == []
    assert pd.parsear({}) == []
    # Impresión sin proveedor válido no se guarda (el gasto se le adeuda a alguien).
    fuera = pd.parsear({"procesos_default_json": json.dumps([
        {"tipo": "impresion", "proveedor_id": 999999, "costo": "10.00"},
        {"tipo": "operativo", "descripcion": "", "costo": "0"},
        {"tipo": "operativo", "descripcion": "Flete", "costo": "-50"},
    ])})
    assert len(fuera) == 1
    assert fuera[0]["descripcion"] == "Flete" and fuera[0]["costo"] == "0.00"


def test_procesos_del_producto_viajan_al_form_de_proyecto(categoria):
    """El JSON que consume el JS del proyecto expone los procesos del catálogo,
    para que la tarjeta se pre-llene al elegir el producto."""
    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.views import _servicios_datos_json
    prov = _proveedor("Serigrafía MX")
    srv = _servicio(categoria, nombre="Sudadera")
    srv.procesos_default = [
        {"tipo": "impresion", "proveedor_id": prov.pk, "costo": "20.00", "por_pieza": True},
    ]
    srv.save(update_fields=["procesos_default"])
    datos = json.loads(_servicios_datos_json())
    assert datos[str(Servicio.objects.get(pk=srv.pk).pk)]["procesos"][0]["proveedor_id"] == prov.pk


def test_costo_extra_suma_por_pieza_y_fijo(categoria):
    from apps.el_catalogo import procesos as pd
    srv = _servicio(categoria, nombre="Gorra")
    srv.procesos_default = [
        {"tipo": "impresion", "proveedor_id": None, "costo": "10.00", "por_pieza": True},
        {"tipo": "operativo", "descripcion": "Setup", "costo": "100.00", "por_pieza": False},
    ]
    assert pd.costo_extra(srv, piezas=1) == Decimal("110.00")
    assert pd.costo_extra(srv, piezas=10) == Decimal("200.00")
