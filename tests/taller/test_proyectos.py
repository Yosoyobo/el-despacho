"""Tests de vistas de Los Proyectos."""

import pytest

from lib.slug import _normalizar as _normalizar_para_test  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_anonimo_redirigido(client):
    resp = client.get("/proyectos/")
    assert resp.status_code in (301, 302)


def test_codigo_correlativo_lc(proyecto_factory):
    """S-LC-Feedback-V2: códigos correlativos LC-NNNN, no PRY-aleatorio."""
    p1 = proyecto_factory()
    p2 = proyecto_factory()
    p3 = proyecto_factory()
    assert p1.codigo == "LC-0001"
    assert p2.codigo == "LC-0002"
    assert p3.codigo == "LC-0003"
    # Slug basado en el nombre del proyecto (S-LC-Feedback-V5 c9).
    assert p1.slug == _normalizar_para_test(p1.nombre)


def test_admin_ve_todos(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    proyecto_factory()
    proyecto_factory()
    client.force_login(admin)
    resp = client.get("/proyectos/")
    assert resp.status_code == 200


def test_disenador_ve_solo_asignados(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoAsignacion

    d = usuario_factory(rol="disenador")
    p1 = proyecto_factory(nombre="Asignado")
    proyecto_factory(nombre="No-asignado")
    ProyectoAsignacion.objects.create(proyecto=p1, usuario=d, rol_en_proyecto="disenador")
    client.force_login(d)
    resp = client.get("/proyectos/")
    assert resp.status_code == 200
    contenido = resp.content.decode()
    assert "Asignado" in contenido
    assert "No-asignado" not in contenido


def test_contador_ve_todos(client, usuario_factory, proyecto_factory):
    c = usuario_factory(rol="contador")
    proyecto_factory(nombre="Proyecto X")
    client.force_login(c)
    resp = client.get("/proyectos/")
    assert resp.status_code == 200
    assert "Proyecto X" in resp.content.decode()


def test_disenador_no_crea_proyecto(client, usuario_factory):
    d = usuario_factory(rol="disenador")
    client.force_login(d)
    assert client.get("/proyectos/nuevo").status_code == 403


def test_admin_crea_proyecto(client, usuario_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    client.force_login(admin)
    resp = client.post(
        "/proyectos/nuevo",
        {"nombre": "Catálogo 2026", "cliente": cli.pk, "descripcion": "",
         "estado": "por_cotizar", "fecha_inicio": "", "fecha_compromiso": "", "monto_estimado": ""},
        follow=True,
    )
    assert resp.status_code == 200
    from apps.los_proyectos.models import Proyecto
    assert Proyecto.objects.filter(nombre="Catálogo 2026").exists()


def test_crea_proyecto_fecha_hora_default_mediodia(client, usuario_factory, cliente_factory):
    """C6 S-LC-Feedback-V6: si se da el día sin hora, default 12:00 PM local."""
    from apps.los_proyectos.models import Proyecto
    from django.utils import timezone
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    client.force_login(admin)
    client.post(
        "/proyectos/nuevo",
        {"nombre": "ConFecha", "cliente": cli.pk, "descripcion": "", "estado": "por_cotizar",
         "fecha_compromiso_dia": "2026-06-15", "fecha_compromiso_hora": "",
         "monto_estimado": ""},
        follow=True,
    )
    p = Proyecto.objects.get(nombre="ConFecha")
    local = timezone.localtime(p.fecha_compromiso)
    assert (local.year, local.month, local.day) == (2026, 6, 15)
    assert (local.hour, local.minute) == (12, 0)


def test_crea_proyecto_fecha_hora_explicita(client, usuario_factory, cliente_factory):
    """C6: respeta la hora explícita capturada."""
    from apps.los_proyectos.models import Proyecto
    from django.utils import timezone
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    client.force_login(admin)
    client.post(
        "/proyectos/nuevo",
        {"nombre": "ConHora", "cliente": cli.pk, "descripcion": "", "estado": "por_cotizar",
         "fecha_compromiso_dia": "2026-06-15", "fecha_compromiso_hora": "09:30",
         "monto_estimado": ""},
        follow=True,
    )
    p = Proyecto.objects.get(nombre="ConHora")
    local = timezone.localtime(p.fecha_compromiso)
    assert (local.hour, local.minute) == (9, 30)


def test_cambiar_estado_emite_evento(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="dueno")
    p = proyecto_factory(estado="esperando_respuesta")
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/cambiar-estado",
        {"estado": "en_proceso_diseno"},
        follow=True,
    )
    assert resp.status_code == 200
    p.refresh_from_db()
    assert p.estado == "en_proceso_diseno"


def test_detalle_403_para_disenador_no_asignado(client, usuario_factory, proyecto_factory):
    d = usuario_factory(rol="disenador")
    p = proyecto_factory()
    client.force_login(d)
    assert client.get(f"/proyectos/{p.pk}/").status_code == 403


def test_asignar_y_quitar(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    d = usuario_factory(rol="disenador")
    p = proyecto_factory()
    client.force_login(admin)
    client.post(f"/proyectos/{p.pk}/asignar", {"usuario": d.pk, "rol_en_proyecto": "disenador"})
    from apps.los_proyectos.models import ProyectoAsignacion
    asig = ProyectoAsignacion.objects.get(proyecto=p, usuario=d)
    client.post(f"/proyectos/{p.pk}/asignar", {"accion": "quitar", "asignacion_id": asig.pk})
    assert not ProyectoAsignacion.objects.filter(pk=asig.pk).exists()


def test_kanban_view(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    proyecto_factory(estado="por_cotizar")
    proyecto_factory(estado="en_proceso_diseno")
    client.force_login(admin)
    resp = client.get("/proyectos/kanban/")
    assert resp.status_code == 200
    contenido = resp.content.decode()
    assert "Por cotizar" in contenido
    assert "En proceso de diseño" in contenido


def test_cliente_inline_modal_get(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/proyectos/cliente-nuevo/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "Nuevo cliente" in resp.content.decode()


def test_cliente_inline_modal_post_crea(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(
        "/proyectos/cliente-nuevo/",
        {"razon_social": "ACME Nuevo", "rfc": "", "nombre_contacto": "X", "email_contacto": "", "telefono": ""},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    from apps.la_cartera.models import Cliente
    assert Cliente.objects.filter(razon_social="ACME Nuevo").exists()


def test_proyecto_con_productos(client, usuario_factory, proyecto_factory):
    """Crear/editar un proyecto con líneas de productos asocia ProyectoProducto."""
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Diseño", defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Playera promo", precio_base="100", categoria=cat)
    p = proyecto_factory()
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=50, nota="azul")
    client.force_login(admin)
    resp = client.get(f"/proyectos/{p.pk}/")
    assert resp.status_code == 200
    assert "Playera promo" in resp.content.decode()


def test_producto_precio_costo_merma_calculos(proyecto_factory):
    """C4 S-LC-Feedback-V6: subtotal usa precio×cantidad; costo incluye merma."""
    from decimal import Decimal

    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Lanyard", precio_base="65", costo="20", categoria=cat)
    p = proyecto_factory()
    # Sin override: hereda precio 65 / costo 20 del catálogo. cantidad 10, merma 2.
    pp = ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=10, merma=2)
    assert pp.precio_efectivo == Decimal("65")
    assert pp.costo_efectivo == Decimal("20")
    assert pp.subtotal == Decimal("650")            # 65 × 10 (merma NO se cobra)
    assert pp.costo_total_linea == Decimal("240")   # 20 × (10 + 2)
    assert pp.merma_costo == Decimal("40")


def test_producto_override_precio_costo(proyecto_factory):
    """C4: precio/costo por proyecto pisan al catálogo."""
    from decimal import Decimal

    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Taza", precio_base="50", costo="15", categoria=cat)
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=srv, cantidad=4, precio_unitario="80", costo_unitario="25",
    )
    assert pp.subtotal == Decimal("320")            # 80 × 4 (override)
    assert pp.costo_total_linea == Decimal("100")   # 25 × 4


def test_monto_estimado_se_autollena_de_productos(client, usuario_factory, cliente_factory):
    """C4: al guardar productos, monto_estimado = suma de subtotales."""
    from decimal import Decimal

    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import Proyecto
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Gorra", precio_base="120", costo="40", categoria=cat)
    client.force_login(admin)
    client.post(
        "/proyectos/nuevo",
        {
            "nombre": "ConProductos", "cliente": cli.pk, "descripcion": "", "estado": "por_cotizar",
            "monto_estimado": "",
            "productos-TOTAL_FORMS": "1", "productos-INITIAL_FORMS": "0",
            "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "1000",
            "productos-0-servicio": srv.pk, "productos-0-cantidad": "3",
            "productos-0-merma": "1", "productos-0-precio_unitario": "", "productos-0-costo_unitario": "",
            "productos-0-incluir_en_calculo": "on", "productos-0-nota": "",
        },
        follow=True,
    )
    p = Proyecto.objects.get(nombre="ConProductos")
    assert p.monto_estimado == Decimal("360")       # 120 × 3
    assert p.merma_total == 1


def test_iva_y_monto_calculado_solo_incluidos(proyecto_factory):
    """C7: monto calculado/IVA/total usan solo las líneas incluidas."""
    from decimal import Decimal

    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Pin", precio_base="100", costo="30", categoria=cat)
    p = proyecto_factory()
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=2, incluir_en_calculo=True)   # 200
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=5, incluir_en_calculo=False)  # excluida
    assert p.monto_calculado == Decimal("200")
    assert p.iva_monto == Decimal("32.00")              # 16%
    assert p.monto_a_facturar == Decimal("232.00")
    p.iva_exento = True
    p.save(update_fields=["iva_exento"])
    assert p.iva_monto == Decimal("0.00")
    assert p.monto_a_facturar == Decimal("200")


def test_detalle_editable_guarda_inline(client, usuario_factory, proyecto_factory):
    """C7: la página del Proyecto guarda datos + equipo desde el detalle."""
    from apps.los_proyectos.models import ProyectoAsignacion
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Nombre viejo")
    client.force_login(admin)
    # GET muestra el form editable.
    body = client.get(f"/proyectos/{p.pk}/").content.decode()
    assert 'id="form-proyecto"' in body
    # POST inline: cambia nombre + asigna al admin como líder.
    client.post(f"/proyectos/{p.pk}/", {
        "nombre": "Nombre nuevo", "cliente": p.cliente_id, "estado": "por_cotizar", "descripcion": "",
        "productos-TOTAL_FORMS": "0", "productos-INITIAL_FORMS": "0",
        "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "1000",
        f"equipo_{admin.pk}": "on", f"rol_{admin.pk}": "lider",
    }, follow=True)
    p.refresh_from_db()
    assert p.nombre == "Nombre nuevo"
    asig = ProyectoAsignacion.objects.get(proyecto=p, usuario=admin)
    assert asig.rol_en_proyecto == "lider"
    # Desmarcar lo quita.
    client.post(f"/proyectos/{p.pk}/", {
        "nombre": "Nombre nuevo", "cliente": p.cliente_id, "estado": "por_cotizar", "descripcion": "",
        "productos-TOTAL_FORMS": "0", "productos-INITIAL_FORMS": "0",
        "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "1000",
    }, follow=True)
    assert not ProyectoAsignacion.objects.filter(proyecto=p, usuario=admin).exists()


def test_modal_agregar_producto_trae_quickcreate(client, usuario_factory, proyecto_factory):
    """C4 follow-up: el modal 'Agregar producto' permite crear producto nuevo."""
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    client.force_login(admin)
    body = client.get(f"/proyectos/{p.pk}/agregar-producto", HTTP_HX_REQUEST="true").content.decode()
    assert "Crear producto nuevo en el catálogo" in body
    assert 'id="qcp-crear"' in body


def test_agregar_y_quitar_proveedor_proyecto(client, usuario_factory, proyecto_factory):
    """C5 S-LC-Feedback-V6: asignar proveedor con compromiso fecha+hora y quitarlo."""
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.models import ProyectoProveedor
    from django.utils import timezone
    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social="Maquilas SA")
    p = proyecto_factory()
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/agregar-proveedor",
        {
            "proveedor": prov.pk, "tipo": "recogemos_nosotros",
            "compromiso_dia": "2026-06-20", "compromiso_hora": "",
            "contacto": "Juan 555", "ubicacion": "Bodega 3", "nota": "",
        },
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204
    pv = ProyectoProveedor.objects.get(proyecto=p, proveedor=prov)
    local = timezone.localtime(pv.compromiso)
    assert (local.hour, local.minute) == (12, 0)     # default mediodía
    assert pv.ubicacion == "Bodega 3"
    # Aparece en el detalle.
    detalle = client.get(f"/proyectos/{p.pk}/").content.decode()
    assert "Maquilas SA" in detalle
    # Quitar.
    client.post(f"/proyectos/{p.pk}/quitar-proveedor/{pv.pk}")
    assert not ProyectoProveedor.objects.filter(pk=pv.pk).exists()
