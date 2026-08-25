"""La pantalla de ajustes del papeleo, en La Gerencia.

Todo lo configurable vive en un GUI (regla del proyecto), así que lo que se
cuida es: que la pantalla cargue, que la llave **no se filtre entera** a la
página, que no se sobreescriba con las viñetas de la máscara, y que el gate sea
el permiso de Ajustes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def jefe(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    return u


def test_la_pantalla_carga(client, jefe):  # noqa: ARG001
    assert client.get("/ajustes/papeleo/").status_code == 200


def test_sin_permiso_no_se_entra(client, usuario_factory):
    client.force_login(usuario_factory(rol="miembro"))
    assert client.get("/ajustes/papeleo/").status_code in (302, 403)


def test_guardar_persiste_lo_configurable(client, jefe):  # noqa: ARG001
    from ajustes.models import ConfiguracionPapeleo

    client.post("/ajustes/papeleo/", {
        "url_publica": "http://10.0.0.9:8204",
        "ligar_automatico": "1",
        "minimo_caracteres_nombre": "8",
        "etiqueta_entrada": "Del Despacho",
    })
    cfg = ConfiguracionPapeleo.obtener()
    assert cfg.url_publica == "http://10.0.0.9:8204"
    assert cfg.ligar_automatico is True
    assert cfg.minimo_caracteres_nombre == 8
    assert cfg.etiqueta_entrada == "Del Despacho"
    # Un checkbox que no viaja en el POST es un apagado, no un «no lo toques».
    assert cfg.avisar_al_entrar is False


def test_un_minimo_absurdo_se_acota(client, jefe):  # noqa: ARG001
    """Con menos de tres letras cualquier nombre pega por casualidad."""
    from ajustes.models import ConfiguracionPapeleo

    client.post("/ajustes/papeleo/", {"minimo_caracteres_nombre": "0"})
    assert ConfiguracionPapeleo.obtener().minimo_caracteres_nombre == 3


def test_la_llave_no_se_manda_entera_a_la_pantalla(client, jefe):  # noqa: ARG001
    from ajustes.models.credencial import Credencial

    Credencial.guardar("paperless_token", "abcdefghijklmnopqrstuvwxyz")
    cuerpo = client.get("/ajustes/papeleo/").content.decode()
    assert "abcdefghijklmnopqrstuvwxyz" not in cuerpo
    assert "abcd" in cuerpo  # se ve que hay una, no cuál es


def test_devolver_la_mascara_no_borra_la_llave(client, jefe):  # noqa: ARG001
    """La pantalla muestra la llave enmascarada; si al guardar se tomara ese
    texto como valor nuevo, la credencial quedaría hecha de viñetas."""
    from ajustes.models.credencial import Credencial
    from lib import paperless

    Credencial.guardar("paperless_token", "llave-de-verdad-1234")
    client.post("/ajustes/papeleo/", {"token": f"llav{chr(8226) * 12}1234"})
    assert paperless.llave() == "llave-de-verdad-1234"


def test_pegar_una_llave_nueva_la_guarda(client, jefe):  # noqa: ARG001
    from lib import paperless

    client.post("/ajustes/papeleo/", {"token": "una-llave-nueva"})
    assert paperless.llave() == "una-llave-nueva"


def test_usuario_y_contrasena_se_canjean_por_el_token(client, jefe, monkeypatch):  # noqa: ARG001
    """Para no mandar a nadie a buscar su token a otra app. La contraseña no se
    guarda: lo que queda es el token."""
    from ajustes.models.credencial import Credencial
    from lib import paperless

    monkeypatch.setattr(paperless, "canjear_token", lambda u, c: "token-canjeado")
    client.post("/ajustes/papeleo/", {"usuario": "admin", "contrasena": "secreta"})
    assert paperless.llave() == "token-canjeado"
    # Y la contraseña no acabó guardada en ningún slot.
    assert Credencial.obtener("papeleo_contrasena") in (None, "")


def test_si_el_canje_falla_la_llave_no_se_pierde(client, jefe, monkeypatch):  # noqa: ARG001
    from ajustes.models.credencial import Credencial
    from lib import paperless

    Credencial.guardar("paperless_token", "la-que-ya-estaba")
    monkeypatch.setattr(paperless, "canjear_token", lambda u, c: None)
    client.post("/ajustes/papeleo/", {"usuario": "admin", "contrasena": "mala"})
    assert paperless.llave() == "la-que-ya-estaba"


def test_el_menu_ofrece_el_renglon_de_papeleo(client, jefe):  # noqa: ARG001
    """Y el de «Los Ajustes» no queda activo a la vez: dos renglones marcados se
    leen como un error de la pantalla."""
    from pathlib import Path

    from django.template import engines

    raiz = Path(__file__).resolve().parent.parent.parent
    tpl = (raiz / "la-gerencia/templates/_componentes_tailadmin/sidebar.html").read_text()
    assert "'ajustes-papeleo'" in tpl
    assert "/ajustes/papeleo" in tpl
    # El renglón de Los Ajustes lo excluye explícitamente.
    linea = next(ln for ln in tpl.splitlines() if 'href="/ajustes/"' in ln)
    assert "/ajustes/papeleo" in linea
    assert engines  # el import se usa para dejar claro que esto lee el archivo
