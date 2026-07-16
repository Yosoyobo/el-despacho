"""Contrato de seguridad y lectura del servidor MCP."""

import pytest

from mcp_despacho.herramientas import (
    ENV_USUARIO,
    ErrorAccesoMCP,
    buscar_clientes,
    buscar_proyectos,
    identidad_actual,
    listar_tareas,
    obtener_proyecto,
)


def _conceder(usuario, modulo, permiso):
    from cuentas.models import PermisoUsuario

    permiso_usuario, _ = PermisoUsuario.objects.update_or_create(
        usuario=usuario,
        modulo=modulo,
        permiso=permiso,
        defaults={"activo": True},
    )
    return permiso_usuario


def test_permiso_mcp_esta_en_catalogo_y_default_super_admin():
    from lib.permisos_defaults import catalogo_permisos, defaults_de

    assert catalogo_permisos()["mcp"] == ["usar"]
    assert defaults_de("super_admin")["mcp"] == ["usar"]
    assert "mcp" not in defaults_de("disenador")


@pytest.mark.django_db
def test_identidad_falla_cerrada_sin_usuario(monkeypatch):
    monkeypatch.delenv(ENV_USUARIO, raising=False)

    with pytest.raises(ErrorAccesoMCP, match=ENV_USUARIO):
        identidad_actual()


@pytest.mark.django_db
def test_identidad_exige_permiso_mcp(monkeypatch, usuario_factory):
    usuario = usuario_factory(rol="disenador", email="sin-mcp@example.com")
    monkeypatch.setenv(ENV_USUARIO, usuario.email)

    with pytest.raises(ErrorAccesoMCP, match=r"mcp\.usar"):
        identidad_actual()


@pytest.mark.django_db
def test_super_admin_puede_consultar_lecturas(
    monkeypatch, usuario_factory, cliente_factory, proyecto_factory
):
    from apps.el_pizarron.models import Tarea

    admin = usuario_factory(rol="super_admin", email="admin-mcp@example.com")
    cliente = cliente_factory(creado_por=admin, razon_social="Museo del Diseño")
    proyecto = proyecto_factory(
        cliente=cliente,
        creado_por=admin,
        nombre="Exhibición anual",
        monto_facturado="1200.00",
    )
    Tarea.objects.create(proyecto=proyecto, titulo="Preparar renders", asignada_a=admin)
    monkeypatch.setenv(ENV_USUARIO, admin.email)

    assert identidad_actual()["modo"] == "solo_lectura"
    assert buscar_clientes("Museo")["resultados"][0]["razon_social"] == "Museo del Diseño"
    assert buscar_proyectos("Exhibición")["resultados"][0]["codigo"] == proyecto.codigo
    detalle = obtener_proyecto(proyecto.codigo)
    assert detalle["finanzas"]["monto_facturado"] == "1200.00"
    assert listar_tareas(proyecto=proyecto.codigo)["resultados"][0]["titulo"] == "Preparar renders"


@pytest.mark.django_db
def test_usuario_limitado_solo_ve_proyectos_y_tareas_asignados(
    monkeypatch, usuario_factory, cliente_factory, proyecto_factory
):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models import ProyectoAsignacion

    usuario = usuario_factory(rol="disenador", email="diseno-mcp@example.com")
    creador = usuario_factory(rol="super_admin")
    cliente = cliente_factory(creado_por=creador)
    visible = proyecto_factory(cliente=cliente, creado_por=creador, nombre="Proyecto visible")
    oculto = proyecto_factory(cliente=cliente, creado_por=creador, nombre="Proyecto secreto")
    ProyectoAsignacion.objects.create(proyecto=visible, usuario=usuario)
    Tarea.objects.create(proyecto=visible, titulo="Tarea visible")
    Tarea.objects.create(proyecto=oculto, titulo="Tarea secreta")
    for modulo, permiso in (("mcp", "usar"), ("proyectos", "ver"), ("pizarron", "ver")):
        _conceder(usuario, modulo, permiso)
    monkeypatch.setenv(ENV_USUARIO, usuario.email)

    proyectos = buscar_proyectos(limite=100)["resultados"]
    tareas = listar_tareas(limite=100)["resultados"]

    assert [fila["nombre"] for fila in proyectos] == ["Proyecto visible"]
    assert [fila["titulo"] for fila in tareas] == ["Tarea visible"]
    assert "finanzas" not in obtener_proyecto(visible.codigo)
    with pytest.raises(ErrorAccesoMCP, match="no visible"):
        obtener_proyecto(oculto.codigo)


@pytest.mark.django_db
def test_herramienta_exige_permiso_del_modulo(monkeypatch, usuario_factory):
    usuario = usuario_factory(rol="disenador", email="solo-mcp@example.com")
    _conceder(usuario, "mcp", "usar")
    monkeypatch.setenv(ENV_USUARIO, usuario.email)

    with pytest.raises(ErrorAccesoMCP, match=r"cartera\.ver"):
        buscar_clientes()
