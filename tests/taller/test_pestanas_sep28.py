"""Las pestañas de El Taller (S-Pendientes-Sep28, camino B: marcos aislados).

Lo que fijan estas pruebas, en orden de importancia:

1. **El Taller se deja incrustar sólo por sí mismo** (SAMEORIGIN). Con DENY no
   se pinta ninguna pestaña; con nada, cualquier sitio podría incrustarlo.
   La Gerencia sigue en DENY: no lleva pestañas.
2. **Dentro de una pestaña la página no pinta menú, encabezado ni pie.** Lo sabe
   por `Sec-Fetch-Dest: iframe` o —cuando pasa por el service worker de la PWA,
   que pierde esa cabecera al volver a pedir la página— por `X-Despacho-Marco`.
   Se verificó en Chrome: con el SW, la navegación del marco llega «empty».
3. **Las decisiones de Oscar** están en el guion: tope de 6, sólo escritorio,
   el clic de en medio no se toca, entrar y salir de la sesión no van en pestaña.

La conducta en el navegador (Ctrl+clic, contenedor, «+», cerrar, móvil) se
verificó con Playwright sobre Chrome real; ver BITACORA.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
JS = (RAIZ / "el-taller/static/js/pestanas.js").read_text()


def test_el_taller_se_deja_incrustar_solo_por_si_mismo():
    taller = (RAIZ / "el-taller/el_taller/settings.py").read_text()
    gerencia = (RAIZ / "la-gerencia/la_gerencia/settings.py").read_text()
    assert 'X_FRAME_OPTIONS = "SAMEORIGIN"' in taller
    assert "django.middleware.clickjacking.XFrameOptionsMiddleware" in taller
    assert 'X_FRAME_OPTIONS = "DENY"' in gerencia


@pytest.mark.django_db
class TestModoIncrustado:
    def test_fuera_de_una_pestana_la_pagina_trae_su_menu_y_la_barra(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        html = client.get("/cartera/").content.decode()
        assert "data-ta-sidebar" in html
        assert 'id="barra-pestanas"' in html
        assert "NoKo Devs" in html

    @pytest.mark.parametrize("cabecera", [
        {"HTTP_SEC_FETCH_DEST": "iframe"},
        {"HTTP_X_DESPACHO_MARCO": "1"},
    ])
    def test_dentro_de_una_pestana_no_hay_menu_ni_encabezado_ni_pie(self, client, usuario_factory, cabecera):
        client.force_login(usuario_factory(rol="super_admin"))
        r = client.get("/cartera/", **cabecera)
        assert r.status_code == 200
        html = r.content.decode()
        assert "data-ta-sidebar" not in html
        assert 'id="barra-pestanas"' not in html
        assert 'id="banner-deploy"' not in html
        assert "<footer" not in html
        # El contenido sí: es la pantalla, sin marco alrededor.
        assert "Clientes" in html

    def test_una_navegacion_normal_con_otra_cabecera_no_se_confunde(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        html = client.get("/cartera/", HTTP_SEC_FETCH_DEST="document").content.decode()
        assert "data-ta-sidebar" in html


@pytest.mark.django_db
class TestElContenedor:
    def test_pide_sesion(self, client):
        r = client.get("/pestanas/")
        assert r.status_code == 302
        assert "sign-in" in r["Location"]

    def test_pinta_el_area_de_marcos(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="super_admin"))
        html = client.get("/pestanas/").content.decode()
        assert "data-pestanas-shell" in html
        assert "data-pestanas-area" in html
        assert "js/pestanas.js" in html

    def test_un_contenedor_dentro_de_una_pestana_se_va_al_dashboard(self, client, usuario_factory):
        """Sería una pestaña con pestañas adentro."""
        client.force_login(usuario_factory(rol="super_admin"))
        r = client.get("/pestanas/", HTTP_SEC_FETCH_DEST="iframe")
        assert r.status_code == 302
        assert r["Location"] == "/"


def test_el_service_worker_repone_la_senal_de_marco():
    """Sin esto, con la PWA instalada cada pestaña saldría con su propio menú."""
    sw = (RAIZ / "interfono/sw_js.py").read_text()
    assert "req.destination === 'iframe'" in sw
    assert "'X-Despacho-Marco': '1'" in sw
    assert "redirect: 'manual'" in sw


def test_el_login_se_sale_del_marco():
    """Si la sesión caduca dentro de una pestaña, el login toma la ventana."""
    login = (RAIZ / "el-taller/templates/auth/sign_in.html").read_text()
    assert "window.top.location.href = location.href" in login


class TestLasDecisionesDeOscarEstanEnElGuion:
    def test_tope_de_seis(self):
        assert "var TOPE = 6;" in JS

    def test_solo_escritorio(self):
        assert "(min-width: 1024px) and (pointer: fine)" in JS

    def test_se_recuerdan_en_el_navegador(self):
        assert "localStorage" in JS and "var CLAVE = 'despacho-pestanas';" in JS

    def test_el_clic_de_en_medio_sigue_siendo_del_navegador(self):
        """Sólo se intercepta el clic principal con Ctrl/⌘; el auxclick sólo se
        escucha sobre la barra (cerrar una pestaña, como en el navegador)."""
        assert "ev.button !== 0 || !(ev.metaKey || ev.ctrlKey)" in JS
        assert JS.count("auxclick") == 1 and "this.el.addEventListener('auxclick'" in JS

    def test_sesion_fuera_de_las_pestanas(self):
        assert "sign-in|sign-out|auth" in JS

    def test_no_se_descarga_una_pestana_con_cambios(self):
        assert 'form[data-cambios-sin-guardar="1"]' in JS
        assert "marcoSucio(f)) return;" in JS

    def test_el_mas_siempre_abre_una_nueva(self):
        assert "abrir('/', true, true)" in JS and "self.abrir('/', true, true)" in JS


def test_la_gerencia_no_lleva_pestanas():
    base = (RAIZ / "la-gerencia/templates/base.html").read_text()
    assert "pestanas.js" not in base
