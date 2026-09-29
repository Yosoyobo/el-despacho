"""La Gerencia → Los Ajustes → Portal de clientes: la casilla de Google."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def test_la_pantalla_explica_que_registrar_antes_y_nace_apagada(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.get("/ajustes/portal/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "https://recepcion.learningcenter.mx/auth/google/callback" in html
    assert "Google Cloud Console" in html
    assert 'name="google_activo"' in html and "checked" not in html.split('name="google_activo"')[1][:40]


def test_prender_y_apagar(client, usuario_factory):
    from portal.models import ConfiguracionPortal

    client.force_login(usuario_factory(rol="super_admin"))
    client.post("/ajustes/portal/", {"google_activo": "1"})
    assert ConfiguracionPortal.obtener().google_activo is True
    client.post("/ajustes/portal/", {})
    assert ConfiguracionPortal.obtener().google_activo is False


def test_sin_permiso_de_ajustes_no_entra(client, usuario_factory):
    from cuentas.models import PermisoUsuario
    from portal.models import ConfiguracionPortal

    u = usuario_factory(rol="dueno")
    PermisoUsuario.objects.update_or_create(usuario=u, modulo="gerencia", permiso="acceder",
                                            defaults={"activo": True})
    PermisoUsuario.objects.filter(usuario=u, modulo="ajustes").delete()
    client.force_login(u)
    r = client.post("/ajustes/portal/", {"google_activo": "1"})
    assert r.status_code in (302, 403)
    assert ConfiguracionPortal.obtener().google_activo is False


def test_esta_en_el_menu_de_ajustes():
    """En las pruebas las plantillas de El Taller van primero en DIRS, así que el
    menú de La Gerencia se revisa en su archivo."""
    from pathlib import Path

    menu = (Path(__file__).resolve().parents[2]
            / "la-gerencia/templates/_componentes_tailadmin/sidebar.html").read_text(encoding="utf-8")
    assert "{% url 'ajustes-portal' %}" in menu and "Portal de clientes" in menu
