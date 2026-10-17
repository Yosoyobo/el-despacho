"""Las notificaciones nunca mandan al dominio viejo (*.ninomeando.com).

Causa raíz (ticket «al picar en notificaciones me lleva a taller.ninomeando.com»):
las suscripciones push registradas estando en el dominio viejo tienen su service
worker ahí, y `clients.openWindow('/ruta')` abre la ruta relativa en SU origen.
Arreglo: el payload lleva la URL absoluta canónica, el SW normaliza lo que
abra, y un comando corrige lo guardado.
"""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings

from lib.urls_canonicas import (
    host_canonico,
    normalizar_url_heredada,
    url_absoluta_taller,
)

pytestmark = pytest.mark.django_db


class TestHelper:
    def test_host_heredado_se_cambia(self):
        assert host_canonico("taller.ninomeando.com") == "taller.learningcenter.mx"
        assert host_canonico("gerencia.learningcenter.mx") == "gerencia.learningcenter.mx"

    def test_normaliza_absoluta_vieja_conservando_ruta_query_y_ancla(self):
        assert (
            normalizar_url_heredada("https://taller.ninomeando.com/recados/4/?a=1#x")
            == "https://taller.learningcenter.mx/recados/4/?a=1#x"
        )

    def test_no_toca_relativas_ni_otros_hosts(self):
        assert normalizar_url_heredada("/recados/4/") == "/recados/4/"
        assert normalizar_url_heredada("https://example.com/x") == "https://example.com/x"
        assert normalizar_url_heredada("https://notninomeando.com/x") == "https://notninomeando.com/x"

    @override_settings(TALLER_URL="https://taller.learningcenter.mx/")
    def test_absoluta_taller_desde_ruta_relativa(self):
        assert url_absoluta_taller("/recados/4/") == "https://taller.learningcenter.mx/recados/4/"
        assert url_absoluta_taller("recados/4/") == "https://taller.learningcenter.mx/recados/4/"

    @override_settings(TALLER_URL="https://taller.ninomeando.com/")
    def test_taller_url_heredado_en_el_env_tambien_se_corrige(self):
        assert url_absoluta_taller("/x/") == "https://taller.learningcenter.mx/x/"

    def test_absoluta_vieja_se_corrige_y_vacia_queda_vacia(self):
        assert url_absoluta_taller("https://taller.ninomeando.com/a/") == "https://taller.learningcenter.mx/a/"
        assert url_absoluta_taller("") == ""


def _vapid():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("vapid_public_key", "BNpublica-prueba")
    Credencial.guardar("vapid_private_key", "ZHByaXZhZGEtcHJ1ZWJh")
    Credencial.guardar("vapid_email", "mailto:test@ejemplo.com")


@override_settings(TALLER_URL="https://taller.learningcenter.mx/")
def test_payload_del_push_lleva_url_absoluta_canonica(usuario_factory):
    from interfono.models import InterfonoSuscripcion
    from lib.interfono import enviar_a_suscripcion

    _vapid()
    sub = InterfonoSuscripcion.objects.create(
        usuario=usuario_factory(), endpoint="https://fcm.googleapis.com/x",
        p256dh="p", auth="a",
    )
    with patch("pywebpush.webpush", return_value=None) as wp:
        assert enviar_a_suscripcion(sub, "t", "c", url="/recados/9/") == "ok"
    payload = json.loads(wp.call_args.kwargs["data"])
    assert payload["url"] == "https://taller.learningcenter.mx/recados/9/"


def test_entrega_guarda_la_ruta_y_corrige_dominio_viejo(usuario_factory):
    from interfono.models import InterfonoEntrega
    from lib.interfono import enviar_a_usuario

    u = usuario_factory()
    enviar_a_usuario(u, "t", "c", url="/tareas/1/")
    enviar_a_usuario(u, "t", "c", url="https://taller.ninomeando.com/tareas/2/")
    urls = set(InterfonoEntrega.objects.filter(usuario=u).values_list("url", flat=True))
    assert urls == {"/tareas/1/", "https://taller.learningcenter.mx/tareas/2/"}


def test_service_worker_normaliza_al_abrir(client):
    cuerpo = client.get("/sw.js").content.decode()
    assert "DESPACHO_DOMINIOS_HEREDADOS" in cuerpo
    assert '"ninomeando.com": "learningcenter.mx"' in cuerpo
    # el click pasa la URL por el normalizador antes de abrir la ventana
    assert "despachoNormalizarUrl(data.url" in cuerpo


class TestComando:
    def _datos(self, usuario_factory):
        from interfono.models import InterfonoEntrega, InterfonoEnvio

        u = usuario_factory()
        viejo = InterfonoEntrega.objects.create(
            usuario=u, titulo="a", cuerpo="b", url="https://taller.ninomeando.com/recados/1/")
        bueno = InterfonoEntrega.objects.create(usuario=u, titulo="a", cuerpo="b", url="/recados/2/")
        envio = InterfonoEnvio.objects.create(
            audiencia="todos", audiencia_label="Todos", titulo="t", cuerpo="c",
            url_destino="https://gerencia.ninomeando.com/x/")
        return viejo, bueno, envio

    def test_por_defecto_es_simulacro(self, usuario_factory):
        viejo, bueno, envio = self._datos(usuario_factory)
        out = StringIO()
        call_command("normalizar_urls_notificaciones", stdout=out)
        viejo.refresh_from_db()
        envio.refresh_from_db()
        assert viejo.url == "https://taller.ninomeando.com/recados/1/"
        assert envio.url_destino == "https://gerencia.ninomeando.com/x/"
        assert "SIMULACRO" in out.getvalue()
        assert "2 fila(s) cambiarían" in out.getvalue()

    def test_aplicar_reescribe_solo_lo_viejo(self, usuario_factory):
        viejo, bueno, envio = self._datos(usuario_factory)
        call_command("normalizar_urls_notificaciones", "--aplicar", stdout=StringIO())
        viejo.refresh_from_db()
        bueno.refresh_from_db()
        envio.refresh_from_db()
        assert viejo.url == "https://taller.learningcenter.mx/recados/1/"
        assert bueno.url == "/recados/2/"
        assert envio.url_destino == "https://gerencia.learningcenter.mx/x/"

    def test_dry_run_explicito_gana_sobre_aplicar(self, usuario_factory):
        viejo, _, _ = self._datos(usuario_factory)
        call_command("normalizar_urls_notificaciones", "--aplicar", "--dry-run", stdout=StringIO())
        viejo.refresh_from_db()
        assert "ninomeando" in viejo.url
