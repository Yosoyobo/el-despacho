"""El historial de actividad y el cruce con Peticiones en vivo (2026-09-29).

Decisiones de Oscar que este archivo defiende:

1. **Qué se guarda**: pantallas y acciones. El sondeo no cuenta; la misma
   pantalla o la misma acción repetida antes de un minuto no repite renglón.
2. **Un año** y se borra (`historial_actividad_purgar`, cada noche).
3. **Quién ve**: el suyo, cada quien; el de otro, `equipo.ver_historial` (nace
   para super_admin y dueño, se delega).
4. **Peticiones en vivo** enseña nombre Y además IP. El nombre viaja en
   `X-Despacho-Quien`: el middleware la pone, gunicorn la loguea y El Portero la
   quita antes de salir al navegador.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]

UA_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")


@pytest.fixture(autouse=True)
def _cache_limpia():
    """El último renglón de cada tipo vive en la caché (locmem en pruebas), que
    sobrevive entre pruebas. Sin limpiarla, un pk reusado heredaría el anterior."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


def _filas(usuario, tipo=None):
    from cuentas.models.registro_actividad import RegistroActividad
    qs = RegistroActividad.objects.filter(usuario=usuario).order_by("en", "pk")
    return list(qs.filter(tipo=tipo) if tipo else qs)


def _envejecer_cache(usuario, tipo, segundos):
    """Hace como si el último renglón de ese tipo se hubiera escrito hace `segundos`."""
    from django.core.cache import cache

    from lib import historial_actividad as ha
    llave = ha._LLAVE.format(uid=usuario.pk, tipo=tipo)
    clave, marca = cache.get(llave)
    cache.set(llave, (clave, marca - segundos), 600)


def _renglon(usuario, *, hace_s=0, tipo="pantalla", **campos):
    from django.utils import timezone

    from cuentas.models.registro_actividad import RegistroActividad
    return RegistroActividad.objects.create(
        usuario=usuario, tipo=tipo, en=timezone.now() - timedelta(seconds=hace_s),
        app=campos.pop("app", "taller"), **campos,
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1 · El permiso
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestElPermiso:

    def test_esta_en_el_catalogo_para_delegarlo(self):
        from lib.permisos_defaults import CATALOGO_PERMISOS
        assert "ver_historial" in CATALOGO_PERMISOS["equipo"]

    def test_nace_solo_para_super_admin_y_dueno(self):
        from lib.permisos_defaults import PERMISOS_UNIVERSALES, defaults_de
        assert "ver_historial" in defaults_de("super_admin")["equipo"]
        assert "ver_historial" in defaults_de("dueno")["equipo"]
        for rol in ("contador", "disenador", "miembro"):
            assert "ver_historial" not in defaults_de(rol).get("equipo", []), rol
        # La presencia de ahora sigue siendo de todos; el historial NO.
        assert "ver_historial" not in PERMISOS_UNIVERSALES["equipo"]

    def test_el_propio_se_ve_sin_permiso(self, usuario_factory):
        from lib.permisos import puede_ver_historial_de
        yo = usuario_factory(rol="disenador")
        otro = usuario_factory()
        assert puede_ver_historial_de(yo, yo)
        assert not puede_ver_historial_de(yo, otro)
        assert puede_ver_historial_de(usuario_factory(rol="dueno"), otro)

    def test_la_siembra_da_el_permiso_a_super_admin_y_dueno(self, usuario_factory):
        """La 0053 corre sobre los usuarios que YA existían; aquí se borra la fila
        que puso el signal y se vuelve a sembrar."""
        import importlib

        from django.apps import apps

        from cuentas.models.permiso_usuario import PermisoUsuario
        from cuentas.models.rol import Rol
        mig = importlib.import_module("cuentas.migrations.0053_seed_permiso_equipo_historial")
        admin, dueno, disenador = (usuario_factory(rol=r) for r in ("super_admin", "dueno", "disenador"))
        PermisoUsuario.objects.filter(modulo="equipo", permiso="ver_historial").delete()
        mig.sembrar(apps, None)
        con = set(PermisoUsuario.objects.filter(modulo="equipo", permiso="ver_historial", activo=True)
                  .values_list("usuario_id", flat=True))
        assert {admin.pk, dueno.pk} <= con
        assert disenador.pk not in con
        for rol in Rol.objects.filter(clave__in=("super_admin", "dueno")):
            assert "ver_historial" in rol.permisos.get("equipo", [])
        # Idempotente.
        mig.sembrar(apps, None)
        assert PermisoUsuario.objects.filter(usuario=admin, modulo="equipo",
                                             permiso="ver_historial").count() == 1


# ═════════════════════════════════════════════════════════════════════════════
# 2 · Registrar, de punta a punta
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRegistrar:

    def test_una_pantalla_deja_su_renglon(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        assert client.get("/directorio/", HTTP_USER_AGENT=UA_IPHONE,
                          HTTP_X_FORWARDED_FOR="187.189.28.130, 10.0.0.1").status_code == 200
        [r] = _filas(u, "pantalla")
        assert (r.app, r.ruta, r.url_name) == ("taller", "/directorio/", "directorio-lista")
        assert r.ip == "187.189.28.130"
        assert "iPhone" in r.agente
        assert r.metodo == "GET"

    def test_recargar_antes_del_minuto_no_repite(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        client.get("/directorio/")
        client.get("/directorio/")
        assert len(_filas(u, "pantalla")) == 1
        # Pasado el minuto, volver a la misma pantalla sí se anota.
        _envejecer_cache(u, "pantalla", 70)
        client.get("/directorio/")
        assert len(_filas(u, "pantalla")) == 2

    def test_cambiar_de_pantalla_se_anota_al_instante(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        client.get("/directorio/")
        client.get(f"/directorio/{u.pk}/")
        client.get("/directorio/")
        assert [r.url_name for r in _filas(u, "pantalla")] == [
            "directorio-lista", "directorio-perfil", "directorio-lista"]

    def test_un_fragmento_de_la_misma_pantalla_no_cuenta_nunca(self, client, usuario_factory):
        """Una pantalla que se queda abierta pidiendo pedazos (HTMX) no es alguien
        abriéndola otra vez, aunque pase el minuto."""
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        client.get("/directorio/")
        _envejecer_cache(u, "pantalla", 600)
        client.get("/directorio/", HTTP_HX_REQUEST="true",
                   HTTP_HX_CURRENT_URL="http://testserver/directorio/")
        assert len(_filas(u, "pantalla")) == 1

    def test_el_sondeo_no_deja_nada(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        client.get("/directorio/en-linea/")
        client.get("/directorio/", HTTP_X_DESPACHO_SONDEO="1")
        assert _filas(u, "pantalla") == []

    def test_un_error_no_deja_nada(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        client.get("/no-existe-esta-ruta/")
        assert _filas(u, "pantalla") == []

    def test_guardar_se_anota_aunque_redirija(self, client, usuario_factory):
        """Un formulario clásico SIEMPRE redirige al guardar: ése es justo el
        momento que importa. Se anota desde qué pantalla y a qué se mandó."""
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        r = client.post("/perfil/notificaciones/formato-hora/", {"formato_hora": "24h"},
                        HTTP_REFERER="http://testserver/perfil/notificaciones/")
        assert r.status_code == 302
        [a] = _filas(u, "accion")
        assert a.destino == "/perfil/notificaciones/formato-hora/"
        assert a.destino_url_name == "perfil-formato-hora"
        assert a.ruta == "/perfil/notificaciones/"
        assert a.metodo == "POST"
        # El GET del redirect NO se anota como pantalla (la 3xx no es pantalla,
        # el cliente de pruebas no la sigue): nada más la acción.
        assert _filas(u, "pantalla") == []

    def test_un_autoguardado_repetido_es_un_solo_renglon(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        for _ in range(4):
            client.post("/perfil/notificaciones/formato-hora/", {"formato_hora": "24h"})
        assert len(_filas(u, "accion")) == 1

    def test_entrar_y_salir(self, client, usuario_factory):
        u = usuario_factory()
        client.force_login(u)
        client.logout()
        assert [r.tipo for r in _filas(u)] == ["entrada", "salida"]

    def test_la_impersonacion_anota_al_que_esta_ahi_y_a_quien_miraba(self, usuario_factory):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from lib import historial_actividad
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        req = RequestFactory().get("/directorio/")
        req.user, req.impersonador = otro, admin
        assert historial_actividad.registrar(req, HttpResponse())
        [r] = _filas(admin)
        assert r.como_id == otro.pk
        assert _filas(otro) == []

    def test_nunca_tumba_la_peticion(self, client, usuario_factory, monkeypatch):
        from cuentas.models.registro_actividad import RegistroActividad

        def revienta(*a, **k):
            raise RuntimeError("la base se cayó a media escritura")

        monkeypatch.setattr(RegistroActividad.objects, "create", revienta)
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        assert client.get("/directorio/").status_code == 200

    def test_basura_no_lanza(self):
        from lib import historial_actividad
        assert historial_actividad.registrar(object(), object()) is False

    def test_sin_cache_pregunta_a_la_base_y_no_duplica(self, client, usuario_factory):
        """Redis caído o reiniciado: la última pantalla se lee de la tabla."""
        from django.core.cache import cache
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        client.get("/directorio/")
        cache.clear()
        client.get("/directorio/")
        assert len(_filas(u, "pantalla")) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 3 · La cabecera del cruce
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLaCabecera:

    def test_quien_trae_sesion_sale_con_su_id(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        r = client.get("/directorio/")
        assert r["X-Despacho-Quien"] == f"u:{u.pk}"

    def test_sin_sesion_no_hay_cabecera(self, client):
        r = client.get("/sign-in")
        assert "X-Despacho-Quien" not in r

    def test_ida_y_vuelta(self):
        from lib.historial_actividad import leer_quien
        assert leer_quien("u:12") == {"tipo": "u", "id": 12, "como": None}
        assert leer_quien("u:12>5") == {"tipo": "u", "id": 12, "como": 5}
        assert leer_quien("c:7") == {"tipo": "c", "id": 7, "como": None}
        for basura in ("", "-", "x:1", "u:", "u:abc", "u12"):
            assert leer_quien(basura) is None, basura

    def test_impersonando_lleva_a_los_dos(self, usuario_factory):
        from django.test import RequestFactory

        from lib.historial_actividad import cabecera_quien
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        req = RequestFactory().get("/")
        req.user, req.impersonador = otro, admin
        assert cabecera_quien(req) == f"u:{admin.pk}>{otro.pk}"

    def test_un_cliente_del_portal_sale_con_su_acceso(self):
        from django.test import RequestFactory

        from lib.historial_actividad import cabecera_quien
        req = RequestFactory().get("/")
        req.acceso = SimpleNamespace(pk=33)
        assert cabecera_quien(req) == "c:33"

    def test_los_tres_entrypoints_la_loguean_antes_de_la_duracion(self):
        """`_RE_COLA_QUIEN` ancla los microsegundos al final: el campo tiene que ir
        entre el XFF y `%(D)s`, en las tres apps."""
        for app in ("el-taller", "la-gerencia", "la-recepcion"):
            t = (RAIZ / app / "entrypoint.sh").read_text()
            assert '"%({x-despacho-quien}o)s"' in t, f"{app} no loguea quién"
            assert (t.index("x-forwarded-for") < t.index("x-despacho-quien")
                    < t.index("%(D)s")), app

    def test_el_portero_la_quita_en_los_tres_hosts(self):
        """Es un dato para el log, no para el navegador."""
        texto = (RAIZ / "Caddyfile").read_text()
        assert re.search(r"\(sin_quien\)\s*\{\s*header -X-Despacho-Quien\s*\}", texto)
        for host in ("taller.learningcenter.mx", "gerencia.learningcenter.mx",
                     "recepcion.learningcenter.mx", ":80"):
            inicio = texto.index(f"\n{host} {{")
            bloque = texto[inicio:texto.index("\n}", inicio)]
            assert "import sin_quien" in bloque, host

    def test_la_recepcion_pone_la_cabecera(self):
        t = (RAIZ / "la-recepcion/apps/portal_cliente/middleware.py").read_text()
        assert "cabecera_quien" in t


# ═════════════════════════════════════════════════════════════════════════════
# 4 · Peticiones en vivo: nombre y además IP
# ═════════════════════════════════════════════════════════════════════════════


LINEA_HOY = ('100.75.35.63 - - [29/Sep/2026:10:04:32 -0600] "GET /catalogo/ HTTP/1.1" '
             '200 150233 "-" "Mozilla/5.0 (Macintosh) Safari/605" "187.189.28.130" "{ident}" 48213')


@pytest.mark.django_db
class TestPeticionesConNombre:

    def test_el_formato_de_hoy_trae_la_identidad(self):
        from lib.site import actividad
        d = actividad._parsear_gunicorn(LINEA_HOY.format(ident="u:12"))
        assert d["ident"] == {"tipo": "u", "id": 12, "como": None}
        # Y no se confunde con el XFF ni se come la duración.
        assert d["quien"] == "187.189.28.130"
        assert d["aparato"] == "Safari"
        assert d["ms"] == 48.2

    def test_sin_sesion_el_campo_es_un_guion(self):
        from lib.site import actividad
        d = actividad._parsear_gunicorn(LINEA_HOY.format(ident="-"))
        assert d["ident"] is None
        assert d["quien"] == "187.189.28.130"

    def test_los_formatos_anteriores_se_siguen_leyendo(self):
        from lib.site import actividad
        viejo = ('100.75.35.63 - - [22/Aug/2026:01:34:32 -0600] "GET /catalogo/ HTTP/1.1" '
                 '200 150233 "-" "Mozilla/5.0 Safari/605" "187.189.28.130" 48213')
        d = actividad._parsear_gunicorn(viejo)
        assert d["quien"] == "187.189.28.130" and d["ident"] is None and d["ms"] == 48.2

    def test_se_le_pone_nombre_al_equipo_y_al_cliente(self, usuario_factory, cliente_factory):
        from lib.site import actividad
        from portal.models.acceso import AccesoCliente
        ana = usuario_factory()
        ana.nombre_completo = "Ana Pérez"
        ana.save(update_fields=["nombre_completo"])
        admin = usuario_factory(rol="super_admin")
        cli = cliente_factory(razon_social="Helados Cruz")
        acceso = AccesoCliente.objects.create(cliente=cli, email="compras@helados.mx", nombre="Lupe")
        filas = actividad.con_personas([
            {"ident": {"tipo": "u", "id": ana.pk, "como": None}},
            {"ident": {"tipo": "u", "id": admin.pk, "como": ana.pk}},
            {"ident": {"tipo": "c", "id": acceso.pk, "como": None}},
            {"ident": None},
            {"ident": {"tipo": "u", "id": 999999, "como": None}},
        ])
        assert filas[0]["persona"] == {"tipo": "equipo", "id": ana.pk, "nombre": "Ana Pérez", "detalle": ""}
        assert filas[1]["persona"]["detalle"] == "como Ana Pérez"
        assert filas[2]["persona"] == {"tipo": "cliente", "id": None, "nombre": "Lupe",
                                       "detalle": "Helados Cruz"}
        assert filas[3]["persona"] is None
        assert filas[4]["persona"] is None

    def test_poner_nombres_son_dos_consultas_aunque_haya_muchas_filas(self, usuario_factory,
                                                                        django_assert_max_num_queries):
        from lib.site import actividad
        us = [usuario_factory() for _ in range(5)]
        filas = [{"ident": {"tipo": "u", "id": u.pk, "como": None}} for u in us * 6]
        with django_assert_max_num_queries(1):
            actividad.con_personas(filas)

    def _render(self, filas, enlace=False):
        from django.template.loader import render_to_string
        return render_to_string("site/vivo/_peticiones.html", {
            "filas": filas, "resumen": {"total": len(filas)}, "error": "",
            "enlace_historial": enlace,
        })

    def _fila(self, **extra):
        from django.utils import timezone
        base = {"metodo": "GET", "ruta": "/catalogo/", "codigo": 200, "ms": 12.0,
                "quien": "187.189.28.130", "aparato": "Safari", "servicio": "Taller",
                "cuando": timezone.now(), "accion": "Productos", "persona": None}
        base.update(extra)
        return base

    def test_el_panel_pinta_nombre_y_ademas_ip(self):
        html = self._render([self._fila(persona={"tipo": "equipo", "id": 5, "nombre": "Ana Pérez",
                                                 "detalle": ""})])
        assert "Ana Pérez" in html
        assert "187.189.28.130" in html
        # En la pared no hay enlace: no hay sesión para abrir el historial.
        assert "/directorio/5/actividad" not in html

    def test_en_el_site_el_nombre_enlaza_al_historial(self, settings):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        html = self._render([self._fila(persona={"tipo": "equipo", "id": 5, "nombre": "Ana",
                                                 "detalle": ""})], enlace=True)
        assert 'href="/directorio/5/actividad"' in html

    def test_el_cliente_sale_con_su_empresa(self):
        html = self._render([self._fila(servicio="Recepción", persona={
            "tipo": "cliente", "id": None, "nombre": "Lupe", "detalle": "Helados Cruz"})])
        assert "Lupe" in html and "Helados Cruz" in html and "cliente" in html
        # La Recepción ya no se disfraza de El Mostrador.
        assert "La Recepción" in html

    def test_sin_sesion_solo_la_ip(self):
        html = self._render([self._fila()])
        assert "187.189.28.130" in html

    def test_el_site_decide_el_enlace_por_permiso(self, client, settings, usuario_factory,
                                                  monkeypatch):
        from lib.site import actividad
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        fila = self._fila(persona={"tipo": "equipo", "id": 5, "nombre": "Ana", "detalle": ""})
        monkeypatch.setattr(actividad, "peticiones", lambda limite=28: [fila])
        admin = usuario_factory(rol="super_admin")
        client.force_login(admin)
        r = client.get("/site/vivo/peticiones", HTTP_HOST="gerencia.learningcenter.mx")
        assert r.status_code == 200
        assert b'href="/directorio/5/actividad"' in r.content
        # Desde la pared: el mismo panel, sin enlace.
        client.logout()
        r = client.get("/site/vivo/peticiones", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Ana" in r.content
        assert b'href="/directorio/5/actividad"' not in r.content


# ═════════════════════════════════════════════════════════════════════════════
# 5 · Cómo se dice
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestComoSeDice:

    def test_la_pantalla_de_un_registro_se_nombra_si_quien_mira_puede_abrirlo(
            self, usuario_factory, cliente_factory):
        from lib import historial_actividad as ha
        cli = cliente_factory(razon_social="Heladería Luna")
        yo = usuario_factory()
        r = _renglon(yo, url_name="cartera-detalle", kwargs={"pk": cli.pk}, ruta=f"/cartera/{cli.pk}/")
        con = ha.describir(r, viewer=usuario_factory(rol="super_admin"), app_de_quien_mira="taller")
        assert con["texto"] == "Viendo Heladería Luna"
        assert con["url"] == f"/cartera/{cli.pk}/"
        # El diseñador no ve Clientes: sabe que miraba un cliente, no cuál.
        sin = ha.describir(r, viewer=usuario_factory(rol="disenador"), app_de_quien_mira="taller")
        assert sin["texto"] == "Viendo un cliente"
        assert sin["url"] == ""

    def test_una_accion_dice_en_que_guardo(self, usuario_factory, cliente_factory):
        from lib import historial_actividad as ha
        cli = cliente_factory(razon_social="Heladería Luna")
        yo = usuario_factory()
        r = _renglon(yo, tipo="accion", url_name="cartera-detalle", kwargs={"pk": cli.pk},
                     ruta=f"/cartera/{cli.pk}/", destino=f"/cartera/{cli.pk}/editar")
        d = ha.describir(r, viewer=usuario_factory(rol="super_admin"))
        assert d["texto"] == "Guardó cambios en Heladería Luna"
        assert d["detalle"] == "Clientes"

    def test_una_accion_sin_registro_dice_la_seccion(self, usuario_factory):
        from lib import historial_actividad as ha
        r = _renglon(usuario_factory(), tipo="accion", ruta="/perfil/notificaciones/",
                     destino="/perfil/notificaciones/formato-hora/")
        assert ha.describir(r)["texto"] == "Guardó algo en Preferencias"

    def test_entrada_salida_y_como(self, usuario_factory):
        from lib import historial_actividad as ha
        admin, otro = usuario_factory(rol="super_admin"), usuario_factory()
        assert ha.describir(_renglon(admin, tipo="entrada"))["texto"] == "Entró al sistema"
        assert ha.describir(_renglon(admin, tipo="salida"))["texto"] == "Cerró sesión"
        r = _renglon(admin, url_name="taller-home", ruta="/", como=otro)
        assert ha.describir(r)["como"] == otro.nombre_completo

    def test_tiempo_activo_topa_los_huecos_y_no_cuenta_tras_salir(self):
        from django.utils import timezone

        from lib import historial_actividad as ha
        t0 = timezone.now()

        def r(min_, tipo="pantalla"):
            return SimpleNamespace(en=t0 + timedelta(minutes=min_), tipo=tipo)

        filas = [r(0), r(2), r(3), r(60), r(61, "salida"), r(120)]
        res = ha.resumen(filas)
        # 2 + 1 + 5 (hueco de 57 topado) + 1 = 9 min; lo de después de salir no suma.
        assert res["activo_min"] == 9
        assert res["pantallas"] == 5
        assert ha.resumen([])["activo_texto"] == ""

    def test_el_dia_es_el_de_mexico(self, usuario_factory):
        """Las 23:30 de México ya son otro día en UTC: el renglón va en su día local."""
        from datetime import datetime

        from django.utils import timezone

        from lib import historial_actividad as ha
        u = usuario_factory()
        tz = timezone.get_current_timezone()
        noche = timezone.make_aware(datetime(2026, 9, 28, 23, 30), tz)
        _renglon(u, url_name="taller-home", ruta="/").__class__.objects.filter(usuario=u).update(en=noche)
        assert len(ha.del_dia(u, date(2026, 9, 28))["items"]) == 1
        assert ha.del_dia(u, date(2026, 9, 29))["items"] == []


# ═════════════════════════════════════════════════════════════════════════════
# 6 · Las pantallas
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLasPantallas:

    def test_mi_actividad_la_ve_cualquiera(self, client, usuario_factory):
        yo = usuario_factory(rol="disenador")
        _renglon(yo, url_name="taller-home", ruta="/", hace_s=30)
        client.force_login(yo)
        r = client.get("/perfil/actividad/")
        assert r.status_code == 200
        texto = r.content.decode()
        assert "Mi actividad" in texto
        assert "En el Dashboard" in texto
        assert "Desarrollado por" in texto  # §4 #21: la página nace con su footer

    def test_la_de_otro_pide_el_permiso(self, client, usuario_factory):
        yo = usuario_factory(rol="disenador")
        otro = usuario_factory()
        client.force_login(yo)
        assert client.get(f"/directorio/{otro.pk}/actividad/").status_code == 403

    def test_el_dueno_ve_la_de_otro(self, client, usuario_factory):
        dueno = usuario_factory(rol="dueno")
        otro = usuario_factory()
        _renglon(otro, url_name="taller-home", ruta="/", hace_s=30)
        client.force_login(dueno)
        r = client.get(f"/directorio/{otro.pk}/actividad/")
        assert r.status_code == 200
        assert otro.nombre_completo in r.content.decode()

    def test_un_permiso_revocado_cierra_la_puerta(self, client, usuario_factory):
        from cuentas.models.permiso_usuario import PermisoUsuario
        dueno = usuario_factory(rol="dueno")
        PermisoUsuario.objects.update_or_create(
            usuario=dueno, modulo="equipo", permiso="ver_historial", defaults={"activo": False})
        client.force_login(dueno)
        assert client.get(f"/directorio/{usuario_factory().pk}/actividad/").status_code == 403

    def test_la_gerencia_y_su_csv(self, client, settings, usuario_factory):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        _renglon(otro, url_name="taller-home", ruta="/", hace_s=30, ip="187.1.2.3")
        client.force_login(admin)
        assert client.get(f"/directorio/{otro.pk}/actividad").status_code == 200
        r = client.get(f"/directorio/{otro.pk}/actividad?csv=30")
        assert r.status_code == 200
        assert r["Content-Type"].startswith("text/csv")
        texto = r.content.decode("utf-8-sig")
        lineas = texto.strip().splitlines()
        assert lineas[0].startswith("fecha,hora,tipo")
        assert "En el Dashboard" in lineas[1] and "187.1.2.3" in lineas[1]

    def test_una_fecha_rara_cae_en_hoy(self, client, usuario_factory):
        yo = usuario_factory()
        client.force_login(yo)
        assert client.get("/perfil/actividad/?fecha=no-es-fecha").status_code == 200
        assert client.get("/perfil/actividad/?fecha=2999-01-01").status_code == 200

    def test_la_ficha_de_equipo_enlaza(self, client, usuario_factory):
        yo = usuario_factory(rol="disenador")
        otro = usuario_factory()
        client.force_login(yo)
        assert "Mi actividad" in client.get(f"/directorio/{yo.pk}/").content.decode()
        assert "Ver su actividad" not in client.get(f"/directorio/{otro.pk}/").content.decode()
        client.force_login(usuario_factory(rol="super_admin"))
        assert "Ver su actividad" in client.get(f"/directorio/{otro.pk}/").content.decode()

    def test_el_directorio_de_gerencia_enlaza(self, client, settings, usuario_factory):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        client.force_login(admin)
        assert f"/directorio/{otro.pk}/actividad" in client.get("/directorio/").content.decode()

    def test_el_partial_es_dual_copy(self):
        taller = RAIZ / "el-taller/templates/_componentes_tailadmin/_historial_actividad.html"
        gerencia = RAIZ / "la-gerencia/templates/_componentes_tailadmin/_historial_actividad.html"
        assert taller.read_text() == gerencia.read_text(), "sincronizar las dos copias (§18)"


# ═════════════════════════════════════════════════════════════════════════════
# 7 · El Chalán y el MCP
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestElChalan:

    def test_esta_registrada_y_documentada(self):
        import capacidades
        from lib.dictado_catalogo import CONSULTAS_CHAT
        cap = capacidades.CAPACIDADES["historial_de_actividad"]
        assert cap.modo == "lectura"
        assert any(c["nombre"] == "historial_de_actividad" for c in CONSULTAS_CHAT)

    def test_el_mcp_por_stdio_la_ofrece(self):
        t = (RAIZ / "mcp_despacho/servidor.py").read_text()
        assert "def historial_de_actividad(" in t
        assert "def historial_de_actividad(" in (RAIZ / "mcp_despacho/herramientas.py").read_text()

    def test_el_propio_sin_permiso(self, usuario_factory):
        import capacidades
        yo = usuario_factory(rol="disenador")
        _renglon(yo, url_name="taller-home", ruta="/", hace_s=30)
        assert "historial_de_actividad" in [c.nombre for c in capacidades.listar(yo)]
        salida = capacidades.ejecutar("historial_de_actividad", {}, yo)
        assert salida["persona"] == yo.nombre_completo
        assert salida["pantallas"] == 1
        assert salida["linea_de_tiempo"][0]["que"] == "En el Dashboard"

    def test_el_de_otro_pide_el_permiso(self, usuario_factory):
        import capacidades
        yo = usuario_factory(rol="disenador")
        otro = usuario_factory()
        otro.nombre_completo = "Jorge Ramírez"
        otro.save(update_fields=["nombre_completo"])
        salida = capacidades.ejecutar("historial_de_actividad", {"persona": "jorge"}, yo)
        assert salida["error"] == "sin_permiso"
        admin = usuario_factory(rol="super_admin")
        salida = capacidades.ejecutar("historial_de_actividad",
                                      {"persona": "jorge", "fecha": "ayer"}, admin)
        assert salida["persona"] == "Jorge Ramírez"
        from django.utils import timezone
        assert salida["fecha"] == (timezone.localdate() - timedelta(days=1)).isoformat()

    def test_fechas_invalidas_y_ambiguas(self, usuario_factory):
        import capacidades
        admin = usuario_factory(rol="super_admin")
        usuario_factory(), usuario_factory()
        assert capacidades.ejecutar("historial_de_actividad",
                                    {"fecha": "pasado"}, admin)["error"] == "fecha_invalida"
        assert capacidades.ejecutar("historial_de_actividad",
                                    {"fecha": "2999-01-01"}, admin)["error"] == "fecha_futura"
        assert capacidades.ejecutar("historial_de_actividad",
                                    {"persona": "usuario"}, admin)["error"] == "ambiguo"


# ═════════════════════════════════════════════════════════════════════════════
# 8 · Un año y se olvida
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLaPurga:

    def test_borra_lo_de_mas_de_un_anio(self, usuario_factory):
        from lib import historial_actividad as ha
        u = usuario_factory()
        viejo = _renglon(u, hace_s=366 * 86400)
        nuevo = _renglon(u, hace_s=364 * 86400)
        assert ha.purgar(en_seco=True) == 1
        assert ha.purgar() == 1
        pks = {r.pk for r in _filas(u)}
        assert viejo.pk not in pks and nuevo.pk in pks

    def test_el_comando_y_su_cron(self, usuario_factory):
        from io import StringIO

        from django.core.management import call_command
        u = usuario_factory()
        _renglon(u, hace_s=400 * 86400)
        salida = StringIO()
        call_command("historial_actividad_purgar", "--dry-run", stdout=salida)
        assert "Se borrarían 1" in salida.getvalue()
        assert len(_filas(u)) == 1
        call_command("historial_actividad_purgar", stdout=StringIO())
        assert _filas(u) == []
        cron = (RAIZ / "infra/cron/el-despacho.cron").read_text()
        assert "manage.py historial_actividad_purgar" in cron

    def test_la_retencion_es_un_anio(self):
        from lib import historial_actividad as ha
        assert ha.RETENCION_DIAS == 365
