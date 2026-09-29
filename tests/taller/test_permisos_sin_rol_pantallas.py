"""S-Deuda-Permisos en pantalla: lo que cambió de rol a permiso se ve igual.

El candado de fondo (`tests/test_permisos_sin_rol_literal.py`) compara los
helpers; aquí se miran las pantallas que cambiaron de condición: la casilla
«Interno» de los comentarios y el botón «Eliminar» del Buzón.
"""

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _rol(clave):
    from cuentas.models.rol import Rol

    return Rol.objects.get(clave=clave)


@pytest.fixture
def proyecto_con_tarea(usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea

    sa = usuario_factory(rol="super_admin")
    p = proyecto_factory(creado_por=sa)
    t = Tarea.objects.create(proyecto=p, titulo="T", creado_por=sa)
    return p, t


def _asignar(p, u):
    from apps.los_proyectos.models import ProyectoAsignacion

    ProyectoAsignacion.objects.create(proyecto=p, usuario=u, rol_en_proyecto="disenador")


# (etiqueta, rol primario, roles asignados, ¿ve la casilla «Interno»?)
CASOS_CASILLA = [
    ("dueño de rol primario", "dueno", (), True),
    ("Director asignado sobre miembro", "miembro", ("dueno",), True),
    ("contador de rol primario", "contador", (), True),
    # Antes la casilla SÍ salía (la plantilla miraba los roles asignados), pero
    # la vista la ignoraba (miraba el rol primario): nunca guardó un interno.
    ("contador asignado sobre miembro", "miembro", ("contador",), False),
    ("diseñador asignado al proyecto", "disenador", (), False),
]


@pytest.mark.parametrize("etiqueta,primario,extra,ve", CASOS_CASILLA)
def test_la_casilla_interno_sale_a_quien_puede_marcarla(
    client, usuario_factory, proyecto_con_tarea, etiqueta, primario, extra, ve,
):
    p, t = proyecto_con_tarea
    u = usuario_factory(rol=primario)
    if extra:
        u.roles_extra.add(*(_rol(c) for c in extra))
    _asignar(p, u)
    client.force_login(u)
    for url in (f"/proyectos/{p.pk}/", f"/tareas/{t.pk}/"):
        resp = client.get(url)
        assert resp.status_code == 200, (etiqueta, url, resp.status_code)
        assert ('name="es_interno"' in resp.content.decode()) is ve, (etiqueta, url)


@pytest.mark.parametrize("etiqueta,primario,extra,queda_interno", [
    ("Director asignado sobre miembro", "miembro", ("dueno",), True),
    ("contador de rol primario", "contador", (), True),
    ("contador asignado sobre miembro", "miembro", ("contador",), False),
    ("diseñador", "disenador", (), False),
])
def test_marcar_interno_se_guarda_como_antes(
    client, usuario_factory, proyecto_con_tarea, etiqueta, primario, extra, queda_interno,
):
    from apps.el_pizarron.models import Comentario

    p, t = proyecto_con_tarea
    u = usuario_factory(rol=primario)
    if extra:
        u.roles_extra.add(*(_rol(c) for c in extra))
    _asignar(p, u)
    client.force_login(u)
    client.post(f"/tareas/{t.pk}/comentar", {"cuerpo": "hola", "es_interno": "on"})
    c = Comentario.objects.get(tarea=t, autor=u)
    assert c.es_interno is queda_interno, etiqueta


def test_el_boton_eliminar_del_buzon_sigue_el_permiso(client, usuario_factory):
    from buzon.models import MensajeBuzon
    from cuentas.models.permiso_usuario import PermisoUsuario

    autor = usuario_factory(rol="disenador")
    MensajeBuzon.objects.create(autor=autor, tipo="otro", asunto="X", cuerpo="x" * 20)

    sa = usuario_factory(rol="super_admin")
    client.force_login(sa)
    assert 'value="eliminar"' in client.get("/buzon/").content.decode()

    # Quien entra a la bandeja (`ver_todos`) pero no puede borrar, no ve el botón.
    soporte = usuario_factory(rol="miembro")
    PermisoUsuario.objects.create(usuario=soporte, modulo="buzon", permiso="ver_todos", activo=True)
    client.force_login(soporte)
    resp = client.get("/buzon/")
    assert resp.status_code == 200
    assert 'value="eliminar"' not in resp.content.decode()
