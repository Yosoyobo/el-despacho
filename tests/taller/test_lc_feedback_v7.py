"""S-LC-Feedback-V7 — pruebas del sprint:
- Kanban: cambiar-estado por POST sin slash final (bug del 404).
- Responsables agrupados por rol con varias personas por rol.
- Sidebar por usuario (override del global).
- jefe directo: ruteo de aprobación del Checador.
- Equipo: perfil consolidado carga.
- Geocerca: helper dentro_de_geocerca + bandera no bloqueante en check-in.
"""

import pytest

pytestmark = pytest.mark.django_db


# ───────────────────────── Kanban ─────────────────────────

def test_cambiar_estado_post_sin_slash(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="por_cotizar")
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/cambiar-estado",
        {"estado": "en_proceso_diseno", "hx_kanban": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200  # devuelve la barra de status inline
    p.refresh_from_db()
    assert p.estado == "en_proceso_diseno"


# ───────────────────── Responsables por rol ─────────────────────

def test_equipo_varias_personas_mismo_rol(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models import ProyectoAsignacion
    admin = usuario_factory(rol="super_admin")
    a = usuario_factory()
    b = usuario_factory()
    p = proyecto_factory()
    client.force_login(admin)
    client.post(f"/proyectos/{p.pk}/", {
        "nombre": p.nombre, "cliente": p.cliente_id, "estado": "por_cotizar", "descripcion": "",
        "productos-TOTAL_FORMS": "0", "productos-INITIAL_FORMS": "0",
        "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "1000",
        "equipo__disenador": [str(a.pk), str(b.pk)],
    }, follow=True)
    roles = {x.usuario_id: x.rol_en_proyecto for x in ProyectoAsignacion.objects.filter(proyecto=p)}
    assert roles == {a.pk: "disenador", b.pk: "disenador"}


# ───────────────────── Sidebar por usuario ─────────────────────

def test_sidebar_usuario_pisa_global(usuario_factory):
    from django.test import RequestFactory

    from cuentas.context_processors import sidebar_orden
    from cuentas.models.sidebar_orden import SidebarOrden, SidebarOrdenUsuario

    u = usuario_factory()
    SidebarOrden.objects.update_or_create(slug="clientes", defaults={"orden": 20, "oculto": False})
    SidebarOrdenUsuario.objects.create(usuario=u, slug="clientes", orden=5, oculto=True)
    req = RequestFactory().get("/")
    req.user = u
    mapa = sidebar_orden(req)["sidebar_orden"]
    # V9: el mapa ahora incluye `grupo` (carpeta). El override del usuario gana.
    assert mapa["clientes"] == {"orden": 5, "oculto": True, "grupo": ""}


def test_sidebar_usuario_guardar_y_restablecer(client, usuario_factory):
    from cuentas.models.sidebar_orden import SidebarOrdenUsuario
    u = usuario_factory()
    client.force_login(u)
    client.post("/perfil/sidebar/guardar", {"orden__clientes": "5", "oculto__clientes": "1"})
    fila = SidebarOrdenUsuario.objects.get(usuario=u, slug="clientes")
    assert fila.orden == 5 and fila.oculto is True
    client.post("/perfil/sidebar/restablecer", {})
    assert not SidebarOrdenUsuario.objects.filter(usuario=u).exists()


# ───────────────────── jefe directo / aprobación ─────────────────────

def test_solo_jefe_directo_o_superadmin_aprueba(usuario_factory):

    from apps.checador import services
    from django.utils import timezone

    from lib.permisos import puede_aprobar_correccion_de

    jefe = usuario_factory(rol="super_admin")  # super_admin como failsafe + permiso
    otro = usuario_factory(rol="super_admin")
    empleado = usuario_factory()
    empleado.jefe_directo = jefe
    empleado.save()

    # El jefe directo sí puede; un super_admin ajeno también (failsafe duro).
    assert puede_aprobar_correccion_de(jefe, empleado) is True
    assert puede_aprobar_correccion_de(otro, empleado) is True

    # Un miembro sin ser jefe ni super_admin no puede.
    pelado = usuario_factory(rol="miembro")
    assert puede_aprobar_correccion_de(pelado, empleado) is False

    # Crear una solicitud y resolverla con el jefe funciona.
    sol = services.solicitar_correccion(
        empleado, tipo="entrada",
        valor_propuesto=timezone.now(), motivo="me equivoqué")
    services.resolver_correccion(sol, admin=jefe, aprobar=True, comentario="ok")
    sol.refresh_from_db()
    assert sol.estado == "aprobada"


def test_no_jefe_no_resuelve(usuario_factory):
    from apps.checador import services
    from django.utils import timezone

    jefe = usuario_factory(rol="super_admin")
    empleado = usuario_factory()
    empleado.jefe_directo = jefe
    empleado.save()
    intruso = usuario_factory(rol="miembro")
    # darle el permiso granular de aprobar al intruso, pero NO es el jefe
    from cuentas.models.permiso_usuario import PermisoUsuario
    PermisoUsuario.objects.create(usuario=intruso, modulo="checador", permiso="aprobar_correcciones", activo=True)

    sol = services.solicitar_correccion(
        empleado, tipo="entrada", valor_propuesto=timezone.now(), motivo="x")
    with pytest.raises(ValueError):
        services.resolver_correccion(sol, admin=intruso, aprobar=True)


# ───────────────────── Equipo: perfil ─────────────────────

def test_perfil_equipo_carga(client, usuario_factory):
    jefe = usuario_factory(rol="super_admin")
    empleado = usuario_factory()
    empleado.jefe_directo = jefe
    empleado.puesto = "Diseñador"
    empleado.geo_lat = 19.4326
    empleado.geo_lng = -99.1332
    empleado.geocerca_activa = True
    empleado.save()
    client.force_login(jefe)
    resp = client.get(f"/directorio/{empleado.pk}/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Diseñador" in body
    assert "geocerca" in body.lower()


# ───────────────────── Geocerca: helper + check-in ─────────────────────

def test_dentro_de_geocerca_helper(usuario_factory):
    u = usuario_factory()
    u.geo_lat = 19.432600
    u.geo_lng = -99.133200
    u.geocerca_radio_m = 150
    u.save()
    # mismo punto → dentro
    assert u.dentro_de_geocerca(19.432600, -99.133200) is True
    # ~2 km al norte → fuera
    assert u.dentro_de_geocerca(19.450000, -99.133200) is False
    # sin pin → None
    u.geo_lat = None
    assert u.dentro_de_geocerca(19.4, -99.1) is None


def test_checada_fuera_geocerca_no_bloquea(usuario_factory):
    from apps.checador import services
    u = usuario_factory()
    u.geo_lat = 19.432600
    u.geo_lng = -99.133200
    u.geocerca_radio_m = 100
    u.geocerca_activa = True
    u.save()
    # check-in lejos: NO debe lanzar, y debe anotar la jornada.
    jornada = services.checar_entrada(u, geo={"lat": 19.50, "lng": -99.20, "precision": 10})
    assert jornada.entrada_en is not None  # la checada se registró
    assert "geocerca" in (jornada.notas or "").lower()
