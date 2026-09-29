"""Entrar a La Recepción: el enlace de un solo uso, el correo que no delata a
nadie, el rate-limit, revocar a media sesión y Google sólo con acceso."""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone

from tests.recepcion.conftest import token_del_correo

pytestmark = pytest.mark.django_db


@pytest.fixture
def uno(armar_cliente, acceso_de):
    d = armar_cliente("AAA", "ana@a.mx")
    d["acceso"] = acceso_de(d)
    return d


# ── Pedir el enlace ─────────────────────────────────────────────────────────


def test_un_correo_con_acceso_recibe_su_enlace(client, uno, correos):
    r = client.post("/entrar/", {"email": "  Ana@A.mx "})
    assert r.status_code == 200
    assert [c[0] for c in correos] == ["ana@a.mx"]
    assert "https://recepcion.ejemplo.mx/entrar/" in correos[0][2]
    assert "NoKo Devs" in correos[0][2] and "https://devs.noko.mx" in correos[0][2]


def test_un_correo_sin_acceso_recibe_la_MISMA_respuesta_y_nada_sale(client, uno, correos):
    """No se puede preguntarle al portal quién es cliente."""
    bueno = client.post("/entrar/", {"email": "ana@a.mx"})
    malo = client.post("/entrar/", {"email": "nadie@x.mx"})
    assert bueno.status_code == malo.status_code == 200
    quitar = [b"ana@a.mx", b"nadie@x.mx", b"ana%40a.mx", b"nadie%40x.mx"]
    cuerpo_b, cuerpo_m = bueno.content, malo.content
    for q in quitar:
        cuerpo_b, cuerpo_m = cuerpo_b.replace(q, b""), cuerpo_m.replace(q, b"")
    # Fuera del correo que se escribió (y el token CSRF), el HTML es idéntico.
    import re
    csrf = re.compile(rb'name="csrfmiddlewaretoken" value="[^"]+"')
    assert csrf.sub(b"", cuerpo_b) == csrf.sub(b"", cuerpo_m)
    assert len(correos) == 1


def test_un_acceso_revocado_o_de_cliente_archivado_no_recibe_nada(client, uno, correos):
    from portal import servicios

    servicios.revocar(uno["acceso"], None)
    client.post("/entrar/", {"email": "ana@a.mx"})
    assert correos == []

    from portal.models import AccesoCliente
    otro = AccesoCliente.objects.create(cliente=uno["cliente"], email="otro@a.mx")
    uno["cliente"].activo = False
    uno["cliente"].save()
    client.post("/entrar/", {"email": otro.email})
    assert correos == []


def test_en_la_base_solo_queda_el_hash_del_token(client, uno, correos):
    from portal.models import EnlaceAcceso

    client.post("/entrar/", {"email": "ana@a.mx"})
    token = token_del_correo(correos[0][2])
    e = EnlaceAcceso.objects.get()
    assert e.token_hash != token and token not in e.token_hash
    assert len(e.token_hash) == 64


# ── Canjear ─────────────────────────────────────────────────────────────────


def test_abrir_el_enlace_no_lo_gasta_y_el_post_si(client, uno, correos):
    """Los filtros de correo abren los enlaces: el GET sólo enseña el botón."""
    from portal.models import EnlaceAcceso

    client.post("/entrar/", {"email": "ana@a.mx"})
    token = token_del_correo(correos[0][2])
    r = client.get(f"/entrar/{token}/")
    assert r.status_code == 200 and b"Entrar al portal" in r.content
    assert EnlaceAcceso.objects.get().usado_en is None
    assert client.get("/").status_code == 302  # todavía sin sesión

    r = client.post(f"/entrar/{token}/")
    assert r.status_code == 302 and r["Location"] == "/"
    assert client.get("/").status_code == 200
    uno["acceso"].refresh_from_db()
    assert uno["acceso"].ultima_entrada_en is not None


def test_el_enlace_sirve_una_sola_vez(client, uno, correos):
    from django.test import Client

    client.post("/entrar/", {"email": "ana@a.mx"})
    token = token_del_correo(correos[0][2])
    assert client.post(f"/entrar/{token}/").status_code == 302
    intruso = Client()
    r = intruso.post(f"/entrar/{token}/")
    assert r.status_code == 410
    assert intruso.get("/").status_code == 302
    assert intruso.get(f"/entrar/{token}/").status_code == 410


def test_el_enlace_vencido_no_abre(client, uno, correos):
    from portal.models import EnlaceAcceso

    client.post("/entrar/", {"email": "ana@a.mx"})
    token = token_del_correo(correos[0][2])
    EnlaceAcceso.objects.update(expira_en=timezone.now() - dt.timedelta(seconds=1))
    assert client.post(f"/entrar/{token}/").status_code == 410
    assert client.get("/").status_code == 302


def test_el_enlace_de_entrada_vence_en_minutos(client, uno, correos):
    from portal.models import EnlaceAcceso

    client.post("/entrar/", {"email": "ana@a.mx"})
    e = EnlaceAcceso.objects.get()
    assert dt.timedelta(minutes=15) <= e.expira_en - e.creado_en <= dt.timedelta(minutes=30)


def test_solo_el_ultimo_enlace_sirve(client, uno, correos):
    client.post("/entrar/", {"email": "ana@a.mx"})
    client.post("/entrar/", {"email": "ana@a.mx"})
    viejo, nuevo = token_del_correo(correos[0][2]), token_del_correo(correos[1][2])
    assert client.post(f"/entrar/{viejo}/").status_code == 410
    assert client.post(f"/entrar/{nuevo}/").status_code == 302


def test_un_token_inventado_no_abre(client, uno):
    assert client.post("/entrar/no-existe-este-token/").status_code == 410
    assert client.get("/entrar/no-existe-este-token/").status_code == 404
    assert client.get("/").status_code == 302


def test_la_sesion_es_nueva_al_entrar(client, uno, entrar_como):
    """Llave de sesión nueva al canjear: nada de fijación de sesión."""
    client.get("/entrar/")
    client.session.save()
    antes = client.session.session_key
    entrar_como(uno["acceso"])
    assert client.session.session_key != antes


# ── Revocar cierra la sesión viva ───────────────────────────────────────────


def test_revocar_cierra_la_sesion_que_estaba_abierta(client, uno, entrar_como, correos):
    from portal import servicios

    entrar_como(uno["acceso"])
    assert client.get("/proyectos/").status_code == 200
    servicios.revocar(uno["acceso"], None)
    r = client.get("/proyectos/")
    assert r.status_code == 302 and r["Location"].startswith("/entrar/")
    # Y la sesión se limpió: aunque se reactive, esa cookie ya no sirve.
    servicios.invitar(uno["cliente"], "ana@a.mx", None)
    assert client.get("/proyectos/").status_code == 302


def test_revocar_vence_los_enlaces_pendientes(client, uno, correos):
    from portal import servicios

    client.post("/entrar/", {"email": "ana@a.mx"})
    token = token_del_correo(correos[0][2])
    servicios.revocar(uno["acceso"], None)
    assert client.post(f"/entrar/{token}/").status_code == 410


def test_archivar_al_cliente_tambien_cierra_la_sesion(client, uno, entrar_como):
    entrar_como(uno["acceso"])
    uno["cliente"].activo = False
    uno["cliente"].save()
    assert client.get("/").status_code == 302


def test_salir_cierra_la_sesion(client, uno, entrar_como):
    entrar_como(uno["acceso"])
    r = client.post("/salir/")
    assert r.status_code == 302 and r["Location"] == "/entrar/"
    assert client.get("/").status_code == 302


# ── Rate-limit ──────────────────────────────────────────────────────────────


@pytest.fixture
def limite_real(monkeypatch):
    """`intentar` con la misma regla que `lib.ratelimit`, en memoria."""
    from lib.errors import RateLimitExcedido

    cuentas: dict = {}

    def _intentar(scope, identidad, *, limite, ventana_seg):
        cuentas[(scope, identidad)] = cuentas.get((scope, identidad), 0) + 1
        if cuentas[(scope, identidad)] > limite:
            raise RateLimitExcedido("Demasiados")
        return cuentas[(scope, identidad)]

    monkeypatch.setattr("apps.portal_cliente.views.intentar", _intentar)
    return cuentas


def test_mas_de_5_pedidos_por_correo_en_15_min_se_frenan(client, uno, correos, limite_real):
    for _ in range(5):
        assert client.post("/entrar/", {"email": "ana@a.mx"}).status_code == 200
    r = client.post("/entrar/", {"email": "ana@a.mx"})
    assert r.status_code == 429
    assert len(correos) == 5


def test_el_freno_por_direccion_alcanza_a_quien_prueba_muchos_correos(client, uno, correos, limite_real):
    from apps.portal_cliente.views import LIMITE_POR_IP

    for i in range(LIMITE_POR_IP):
        client.post("/entrar/", {"email": f"prueba{i}@x.mx"})
    assert client.post("/entrar/", {"email": "ana@a.mx"}).status_code == 429
    assert correos == []


def test_sin_redis_el_portal_se_niega_en_vez_de_quedar_sin_freno(client, uno, correos, monkeypatch):
    def _roto(*a, **k):
        raise ConnectionError("redis caído")

    monkeypatch.setattr("apps.portal_cliente.views.intentar", _roto)
    assert client.post("/entrar/", {"email": "ana@a.mx"}).status_code == 429
    assert correos == []


def test_el_canje_tambien_tiene_freno(client, uno, limite_real):
    from apps.portal_cliente.views import LIMITE_POR_IP

    for _ in range(LIMITE_POR_IP):
        client.post("/entrar/token-falso/")
    assert client.post("/entrar/token-falso/").status_code == 429


# ── Google (§4 #7: sólo con acceso, nunca auto-registro) ────────────────────


def _perfil(email, verificado=True):
    from lib.google_oauth import PerfilGoogle

    return PerfilGoogle(sub="123", email=email, email_verified=verificado, nombre="X",
                        apellido="Y", foto_url=None, locale=None)


def _callback(client, monkeypatch, perfil):
    monkeypatch.setattr("lib.google_oauth.intercambiar_codigo_por_perfil", lambda code, uri: perfil)
    s = client.session
    s["_portal_google_state"] = "estado"
    s.save()
    return client.get("/auth/google/callback", {"code": "c", "state": "estado"})


def test_google_con_el_correo_invitado_entra(client, uno, monkeypatch):
    r = _callback(client, monkeypatch, _perfil("ANA@a.mx"))
    assert r.status_code == 302
    assert client.get("/").status_code == 200


def test_google_con_otro_correo_no_entra_ni_crea_acceso(client, uno, monkeypatch):
    from portal.models import AccesoCliente

    r = _callback(client, monkeypatch, _perfil("desconocido@gmail.com"))
    assert r.status_code == 403
    assert b"no tiene acceso al portal" in r.content
    assert AccesoCliente.objects.count() == 1
    assert client.get("/").status_code == 302


def test_google_sin_correo_verificado_no_entra(client, uno, monkeypatch):
    r = _callback(client, monkeypatch, _perfil("ana@a.mx", verificado=False))
    assert r.status_code == 403
    assert client.get("/").status_code == 302


def test_google_con_state_falso_no_entra(client, uno, monkeypatch):
    monkeypatch.setattr("lib.google_oauth.intercambiar_codigo_por_perfil",
                        lambda code, uri: _perfil("ana@a.mx"))
    r = client.get("/auth/google/callback", {"code": "c", "state": "otro"})
    assert r.status_code == 400
    assert client.get("/").status_code == 302


def test_el_boton_de_google_sale_solo_si_esta_configurado(client, monkeypatch):
    monkeypatch.setattr("apps.portal_cliente.views._google_disponible", lambda: False)
    assert b"Entrar con Google" not in client.get("/entrar/").content
    monkeypatch.setattr("apps.portal_cliente.views._google_disponible", lambda: True)
    assert b"Entrar con Google" in client.get("/entrar/").content


def test_next_no_manda_a_otro_sitio(client, uno, entrar_como, monkeypatch):
    r = client.get("/entrar/", {"next": "https://malo.example/robar"})
    assert b"malo.example" not in r.content


def test_una_sesion_de_antes_de_revocar_no_revive_al_reinvitar(client, uno, entrar_como, correos):
    """Revocar y volver a invitar SIN que la sesión vieja haga un clic en medio:
    la cookie vieja trae la generación anterior y ya no abre nada."""
    from portal import servicios

    entrar_como(uno["acceso"])
    servicios.revocar(uno["acceso"], None)
    servicios.invitar(uno["cliente"], "ana@a.mx", None)
    r = client.get("/proyectos/")
    assert r.status_code == 302 and r["Location"].startswith("/entrar/")


def test_revocar_deja_vencidos_en_la_base_los_enlaces_pendientes(uno):
    """Defensa en profundidad: aunque el acceso inactivo ya no deja canjear, el
    enlace pendiente queda vencido en la base (un respaldo restaurado o un
    acceso reactivado a mano no lo revive)."""
    from portal import servicios
    from portal.models import EnlaceAcceso

    servicios._crear_enlace(uno["acceso"], "entrada")
    servicios.revocar(uno["acceso"], None)
    e = EnlaceAcceso.objects.get()
    assert e.expira_en <= timezone.now() and e.usado_en is None
