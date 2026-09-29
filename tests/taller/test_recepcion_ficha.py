"""La Recepción vista desde El Taller: invitar y revocar desde la ficha del
cliente, el permiso `recepcion.*`, y lo que El Chalán puede consultar y proponer."""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def correos(monkeypatch):
    from lib import cartero

    enviados = []

    def _falso(*, destinatario, asunto, html, **kw):
        enviados.append((destinatario, asunto, html))
        return cartero.ResultadoCorreo(ok=True, proveedor="pruebas")

    monkeypatch.setattr(cartero, "enviar", _falso)
    return enviados


@pytest.fixture
def cliente_con_contactos(cliente_factory):
    from apps.la_cartera.models import ClienteContacto

    c = cliente_factory(razon_social="HELADERIA LA NIEVE", email_contacto="compras@nieve.mx",
                        nombre_contacto="Compras")
    ClienteContacto.objects.create(cliente=c, nombre="Ana López", email="Ana@Nieve.mx", principal=True)
    ClienteContacto.objects.create(cliente=c, nombre="Sin correo")
    return c


def _entrar(client, usuario):
    client.force_login(usuario)
    return client


# ── Catálogo de permisos (§4 #20) ───────────────────────────────────────────


def test_el_modulo_recepcion_esta_en_el_catalogo_y_se_puede_delegar():
    from cuentas.context_processors import MODULOS_VISIBLES
    from lib.permisos_defaults import CATALOGO_PERMISOS, DEFAULTS_POR_ROL

    assert CATALOGO_PERMISOS["recepcion"] == ["ver", "invitar", "revocar", "documentos"]
    assert set(DEFAULTS_POR_ROL["super_admin"]["recepcion"]) == {"ver", "invitar", "revocar", "documentos"}
    # «Como hoy»: lo trae quien edita la cartera.
    for rol, mods in DEFAULTS_POR_ROL.items():
        edita_cartera = "editar" in mods.get("cartera", [])
        assert ("invitar" in mods.get("recepcion", [])) == edita_cartera, rol
    assert "recepcion" in MODULOS_VISIBLES


def test_la_siembra_da_el_permiso_a_quien_edita_la_cartera(usuario_factory):
    """La migración `portal/0002`, sobre personas: fila propia, rol extra, fila
    apagada que se respeta, y el super_admin siempre."""
    import importlib

    from django.apps import apps as django_apps

    from cuentas.models import PermisoUsuario, Rol

    mig = importlib.import_module("portal.migrations.0002_seed_permisos_recepcion")
    sa = usuario_factory(rol="super_admin")
    con_fila = usuario_factory(rol="miembro")
    PermisoUsuario.objects.update_or_create(usuario=con_fila, modulo="cartera", permiso="editar",
                                            defaults={"activo": True})
    por_rol = usuario_factory(rol="miembro")
    rol = Rol.objects.create(nombre="Ventas", permisos={"cartera": ["ver", "editar"]})
    por_rol.roles_extra.add(rol)
    apagado = usuario_factory(rol="miembro")
    apagado.roles_extra.add(rol)
    PermisoUsuario.objects.update_or_create(usuario=apagado, modulo="cartera", permiso="editar",
                                            defaults={"activo": False})
    nada = usuario_factory(rol="disenador")
    PermisoUsuario.objects.filter(modulo="recepcion").delete()

    mig.sembrar(django_apps, None)

    def tiene(u):
        return PermisoUsuario.objects.filter(usuario=u, modulo="recepcion", permiso="invitar",
                                             activo=True).exists()

    assert tiene(sa) and tiene(con_fila) and tiene(por_rol)
    assert not tiene(apagado) and not tiene(nada)
    rol.refresh_from_db()
    assert set(rol.permisos["recepcion"]) == {"ver", "invitar", "revocar"}


# ── La ficha del cliente ────────────────────────────────────────────────────


def test_la_ficha_muestra_el_recuadro_y_quien_tiene_acceso(client, usuario_factory, cliente_con_contactos):
    from portal.models import AccesoCliente

    AccesoCliente.objects.create(cliente=cliente_con_contactos, email="ana@nieve.mx", nombre="Ana López")
    admin = usuario_factory(rol="super_admin")
    html = _entrar(client, admin).get(f"/cartera/{cliente_con_contactos.pk}/").content.decode()
    assert 'id="portal-recuadro"' in html
    assert "Con acceso" in html and "Todavía no entra" in html
    assert "Invitar al portal" in html          # compras@ (el correo de siempre) no tiene
    assert "Revocar acceso" in html
    assert "Sin correo" not in html.split('id="portal-recuadro"')[1].split("</section>")[0]


def test_sin_permiso_no_hay_recuadro(client, usuario_factory, cliente_con_contactos):
    from cuentas.models import PermisoUsuario

    u = usuario_factory(rol="contador")        # ve la cartera, no la edita
    PermisoUsuario.objects.filter(usuario=u, modulo="recepcion").delete()
    html = _entrar(client, u).get(f"/cartera/{cliente_con_contactos.pk}/").content.decode()
    assert 'id="portal-recuadro"' not in html


def test_invitar_crea_el_acceso_y_manda_el_correo(client, usuario_factory, cliente_con_contactos, correos):
    from portal.models import AccesoCliente, EnlaceAcceso

    admin = usuario_factory(rol="super_admin")
    r = _entrar(client, admin).post(f"/recepcion/cliente/{cliente_con_contactos.pk}/invitar/",
                                    {"email": "ana@nieve.mx"})
    assert r.status_code == 200 and b"le mandamos a ana@nieve.mx" in r.content
    acceso = AccesoCliente.objects.get()
    assert acceso.activo and acceso.invitado_por == admin and acceso.contacto.nombre == "Ana López"
    assert [c[0] for c in correos] == ["ana@nieve.mx"]
    html = correos[0][2]
    assert "Te invitamos" in correos[0][1] or "portal" in correos[0][1]
    token = re.search(r"/entrar/([A-Za-z0-9_\-]+)/", html).group(1)
    enlace = EnlaceAcceso.objects.get()
    assert enlace.motivo == "invitacion" and token not in enlace.token_hash
    assert "NoKo Devs" in html


def test_no_se_invita_un_correo_que_no_esta_en_la_ficha(client, usuario_factory, cliente_con_contactos, correos):
    from portal.models import AccesoCliente

    admin = usuario_factory(rol="super_admin")
    r = _entrar(client, admin).post(f"/recepcion/cliente/{cliente_con_contactos.pk}/invitar/",
                                    {"email": "intruso@x.mx"})
    assert r.status_code == 200 and "no es de ningún contacto".encode() in r.content
    assert AccesoCliente.objects.count() == 0 and correos == []


def test_un_correo_solo_abre_un_cliente(client, usuario_factory, cliente_factory, cliente_con_contactos, correos):
    from apps.la_cartera.models import ClienteContacto

    from portal.models import AccesoCliente

    otro = cliente_factory(razon_social="CAFETERIA OTRA")
    ClienteContacto.objects.create(cliente=otro, nombre="Ana López", email="ana@nieve.mx")
    AccesoCliente.objects.create(cliente=otro, email="ana@nieve.mx")
    admin = usuario_factory(rol="super_admin")
    r = _entrar(client, admin).post(f"/recepcion/cliente/{cliente_con_contactos.pk}/invitar/",
                                    {"email": "ana@nieve.mx"})
    assert "ya entra al portal de «CAFETERIA OTRA»".encode() in r.content
    assert AccesoCliente.objects.filter(cliente=cliente_con_contactos).count() == 0


def test_invitar_y_revocar_exigen_su_permiso(client, usuario_factory, cliente_con_contactos, correos):
    from cuentas.models import PermisoUsuario
    from portal.models import AccesoCliente

    u = usuario_factory(rol="contador")
    PermisoUsuario.objects.filter(usuario=u, modulo="recepcion").delete()
    _entrar(client, u)
    r = client.post(f"/recepcion/cliente/{cliente_con_contactos.pk}/invitar/", {"email": "ana@nieve.mx"})
    assert r.status_code in (302, 403)
    assert AccesoCliente.objects.count() == 0
    acceso = AccesoCliente.objects.create(cliente=cliente_con_contactos, email="ana@nieve.mx")
    r = client.post(f"/recepcion/acceso/{acceso.pk}/revocar/")
    assert r.status_code in (302, 403)
    acceso.refresh_from_db()
    assert acceso.activo
    # Con el permiso delegado, sí.
    PermisoUsuario.objects.create(usuario=u, modulo="recepcion", permiso="revocar")
    client.post(f"/recepcion/acceso/{acceso.pk}/revocar/")
    acceso.refresh_from_db()
    assert not acceso.activo and acceso.revocado_por == u


def test_revocar_y_volver_a_invitar_sube_la_generacion(client, usuario_factory, cliente_con_contactos, correos):
    from portal.models import AccesoCliente

    admin = usuario_factory(rol="super_admin")
    _entrar(client, admin)
    client.post(f"/recepcion/cliente/{cliente_con_contactos.pk}/invitar/", {"email": "ana@nieve.mx"})
    acceso = AccesoCliente.objects.get()
    g0 = acceso.generacion
    r = client.post(f"/recepcion/acceso/{acceso.pk}/revocar/")
    assert b"ya no puede entrar" in r.content
    client.post(f"/recepcion/cliente/{cliente_con_contactos.pk}/invitar/", {"email": "ana@nieve.mx"})
    acceso.refresh_from_db()
    assert acceso.activo and acceso.generacion == g0 + 2
    assert AccesoCliente.objects.count() == 1


def test_si_el_correo_no_sale_se_dice(client, usuario_factory, cliente_con_contactos, monkeypatch):
    from lib import cartero

    monkeypatch.setattr(cartero, "enviar",
                        lambda **kw: cartero.ResultadoCorreo(ok=False, error="SMTP caído"))
    admin = usuario_factory(rol="super_admin")
    r = _entrar(client, admin).post(f"/recepcion/cliente/{cliente_con_contactos.pk}/invitar/",
                                    {"email": "ana@nieve.mx"})
    assert b"SMTP ca" in r.content and b"Reenviar" in r.content


# ── El Chalán ───────────────────────────────────────────────────────────────


def test_el_chalan_consulta_quien_tiene_acceso(usuario_factory, cliente_con_contactos):
    import capacidades.lecturas  # noqa: F401 — registra
    from capacidades.gating import gate_ok
    from capacidades.registro import CAPACIDADES
    from cuentas.models import PermisoUsuario
    from portal.models import AccesoCliente

    AccesoCliente.objects.create(cliente=cliente_con_contactos, email="ana@nieve.mx", nombre="Ana López")
    cap = CAPACIDADES["accesos_portal"]
    admin = usuario_factory(rol="super_admin")
    datos = cap.fn({"cliente": "heladeria la nieve"}, admin)
    assert [p["email"] for p in datos["con_acceso"]] == ["ana@nieve.mx"]
    assert {p["email"] for p in datos["sin_acceso"]} == {"compras@nieve.mx"}
    # Gating por el permiso nuevo.
    sin = usuario_factory(rol="disenador")
    PermisoUsuario.objects.filter(usuario=sin, modulo="recepcion").delete()
    assert gate_ok(cap.gating, admin) and not gate_ok(cap.gating, sin)


def test_el_chalan_propone_invitar_y_al_confirmar_se_invita(usuario_factory, cliente_con_contactos, correos):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.el_dictado.models import DictadoAccion

    import capacidades.propuestas  # noqa: F401
    from capacidades.gating import gate_ok
    from capacidades.registro import CAPACIDADES
    from lib.dictado_catalogo import comandos_para
    from portal.models import AccesoCliente

    admin = usuario_factory(rol="super_admin")
    assert "invitar_portal" in {c["tipo"] for c in comandos_para(admin)}
    assert CAPACIDADES["invitar_portal"].modo == "propuesta"
    assert gate_ok("recepcion_invitar", admin, modo="propuesta")

    acc = DictadoAccion(tipo="invitar_portal", orden=0,
                        payload={"cliente_slug": cliente_con_contactos.slug, "contacto": "Ana"})
    EJECUTORES["invitar_portal"](acc, admin, {})
    assert AccesoCliente.objects.get().email == "ana@nieve.mx"
    assert acc.entidad_tipo == "cliente" and acc.entidad_id == cliente_con_contactos.pk
    assert [c[0] for c in correos] == ["ana@nieve.mx"]


def test_el_ejecutor_no_inventa_correos_ni_se_salta_el_permiso(usuario_factory, cliente_con_contactos, correos):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.el_dictado.models import DictadoAccion

    from cuentas.models import PermisoUsuario

    admin = usuario_factory(rol="super_admin")
    for contacto in ("nadie@x.mx", "Pedro"):
        acc = DictadoAccion(tipo="invitar_portal", orden=0,
                            payload={"cliente_slug": cliente_con_contactos.slug, "contacto": contacto})
        with pytest.raises(ValueError):
            EJECUTORES["invitar_portal"](acc, admin, {})
    u = usuario_factory(rol="disenador")
    PermisoUsuario.objects.filter(usuario=u, modulo="recepcion").delete()
    acc = DictadoAccion(tipo="invitar_portal", orden=0,
                        payload={"cliente_slug": cliente_con_contactos.slug, "contacto": "Ana"})
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["invitar_portal"](acc, u, {})
    assert correos == []


def test_el_catalogo_documenta_el_portal_para_el_chalan():
    from lib.dictado_catalogo import COMANDOS_DICTADO, CONSULTAS_CHAT

    assert any(c["tipo"] == "invitar_portal" for c in COMANDOS_DICTADO)
    assert any("accesos_portal" in c["nombre"] for c in CONSULTAS_CHAT)
    from pathlib import Path
    prompt = Path("el-taller/apps/el_dictado/prompt.py").read_text(encoding="utf-8")
    assert "invitar_portal" in prompt


def test_la_categoria_de_push_del_portal_se_puede_silenciar():
    from apps.perfil_notificaciones.views import CATEGORIAS

    from portal.avisos import CATEGORIA, PERMISO

    fila = next(c for c in CATEGORIAS if c[0] == CATEGORIA)
    assert fila[3] == PERMISO
