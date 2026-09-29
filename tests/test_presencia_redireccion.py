"""La presencia no anota una redirección (deuda Sep28).

Antes: si La Gerencia redirigía a El Taller, el `Location` era de otro host, no
se creía, y se anotaba la ruta PEDIDA en La Gerencia — una pantalla que nadie
tuvo enfrente. Ahora una 3xx no escribe nada: el navegador la sigue en el acto y
esa petición, en la app a la que caiga, anota actividad y pantalla.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

pytestmark = pytest.mark.django_db


def _recargar(usuario):
    from cuentas.models.usuario import Usuario
    return Usuario.objects.get(pk=usuario.pk)


def _poner_actividad(usuario, *, hace_s, ruta="/antes/", url_name="antes", app="taller"):
    from django.utils import timezone

    from cuentas.models.usuario import Usuario
    Usuario.objects.filter(pk=usuario.pk).update(
        actividad_en=timezone.now() - timedelta(seconds=hace_s), actividad_app=app,
        actividad_ruta=ruta, actividad_url_name=url_name, actividad_kwargs={},
        actividad_accion="ver", actividad_agente="")


def _peticion(usuario, ruta, metodo="get"):
    from django.test import RequestFactory
    r = getattr(RequestFactory(), metodo)(ruta)
    r.user = _recargar(usuario)
    return r


def test_la_redireccion_a_otra_app_no_anota_la_ruta_pedida(usuario_factory):
    from django.http import HttpResponseRedirect

    from lib import presencia
    u = usuario_factory()
    _poner_actividad(u, hace_s=600)
    resp = HttpResponseRedirect("https://taller.learningcenter.mx/proyectos/4/")
    assert presencia.registrar(_peticion(u, "/sala-de-juntas/proyecto/4/"), resp) is False
    u = _recargar(u)
    assert u.actividad_ruta == "/antes/", "se anotó una pantalla que nadie vio"


@pytest.mark.parametrize("estado", [301, 302, 303, 307, 308])
def test_ninguna_3xx_escribe(usuario_factory, estado):
    from django.http import HttpResponse

    from lib import presencia
    u = usuario_factory()
    _poner_actividad(u, hace_s=600)
    antes = _recargar(u).actividad_en
    resp = HttpResponse(status=estado, headers={"Location": "/cartera/4/"})
    assert presencia.registrar(_peticion(u, "/cartera/nuevo/", "post"), resp) is False
    assert _recargar(u).actividad_en == antes


def test_la_pantalla_la_anota_la_peticion_que_sigue(usuario_factory):
    """El formulario clásico: POST → 302 → GET. La que anota es la GET, y como la
    redirección no gastó el tope de 15 s, la anota de inmediato."""
    from django.http import HttpResponse, HttpResponseRedirect

    from lib import presencia
    u = usuario_factory()
    _poner_actividad(u, hace_s=20, ruta="/cartera/nuevo/", url_name="cartera-nuevo")
    presencia.registrar(_peticion(u, "/cartera/nuevo/", "post"),
                        HttpResponseRedirect("/cartera/4/"))
    assert presencia.registrar(_peticion(u, "/cartera/4/"), HttpResponse())
    u = _recargar(u)
    assert u.actividad_ruta == "/cartera/4/"
    assert u.actividad_accion == "ver"


def test_de_punta_a_punta_la_redireccion_no_cuenta(client, usuario_factory):
    """Con el middleware de verdad: el PDF unido que ya no está redirige al
    buscador del papeleo, y esa 302 no se anota."""
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    _poner_actividad(u, hace_s=600)
    r = client.get("/papeleo/unido/" + "a" * 64 + "/")
    assert r.status_code == 302
    assert _recargar(u).actividad_ruta == "/antes/"


def test_un_200_sigue_contando(usuario_factory):
    from django.http import HttpResponse

    from lib import presencia
    u = usuario_factory()
    _poner_actividad(u, hace_s=600)
    assert presencia.registrar(_peticion(u, "/proyectos/"), HttpResponse())
    assert _recargar(u).actividad_ruta == "/proyectos/"
