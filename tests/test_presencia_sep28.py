"""Sprint de pendientes 2026-09-28 — Quién está en línea, dónde y desde qué.

Oscar pidió ver, en El Directorio (Gerencia), en El Site y El Vigía, en Equipo
(Taller) y en el Dashboard, quién está activo: en línea (últimos 5 min), ausente
(5-30 min) o desconectado con la hora de su última vez; y de cada quien la app,
la sección, la pantalla exacta y el aparato.

Lo que estas pruebas fijan, en orden de importancia:

1. **El sondeo automático NO es actividad.** El banner, el semáforo, las
   bandejas y los paneles se piden solos cada pocos segundos; si contaran, una
   pestaña olvidada dejaría a alguien «en línea» para siempre. Hay un candado que
   recorre las plantillas y exige que todo `hx-trigger="every …"` esté en la
   lista.
2. **Nunca tumba una petición.** La presencia se anota al volver de la vista y
   cualquier error se traga.
3. **Escribe poco**: a lo más una vez por minuto en la misma pantalla, una cada
   15 s si cambió — con los campos que el usuario ya trae, sin consultar nada.
4. **Respeta permisos**: `(equipo, ver_actividad)` decide si se ve, y el nombre
   de lo que alguien tiene abierto sólo sale si quien mira lo podría abrir.
5. **Las dos pantallas del NUC van a la par** (§4 #22).
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]

UA_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
UA_MAC_CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
UA_WIN_EDGE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like "
               "Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0")
UA_ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like "
              "Gecko) Chrome/128.0.0.0 Mobile Safari/537.36")


def _ahora():
    from django.utils import timezone
    return timezone.now()


def _poner_actividad(usuario, *, hace_s=0, url_name="taller-home", ruta="/", app="taller",
                     accion="ver", kwargs=None, agente=UA_MAC_CHROME):
    """Deja al usuario con una actividad hecha a mano, directo en la base."""
    from cuentas.models.usuario import Usuario
    campos = {
        "actividad_en": _ahora() - timedelta(seconds=hace_s),
        "actividad_app": app,
        "actividad_ruta": ruta,
        "actividad_url_name": url_name,
        "actividad_kwargs": kwargs or {},
        "actividad_accion": accion,
        "actividad_agente": agente,
    }
    Usuario.objects.filter(pk=usuario.pk).update(**campos)
    for campo, valor in campos.items():
        setattr(usuario, campo, valor)
    return usuario


def _recargar(usuario):
    from cuentas.models.usuario import Usuario
    return Usuario.objects.get(pk=usuario.pk)


def _revocar(usuario):
    from cuentas.models.permiso_usuario import PermisoUsuario
    PermisoUsuario.objects.update_or_create(
        usuario=usuario, modulo="equipo", permiso="ver_actividad",
        defaults={"activo": False},
    )
    # El caché de permisos vive en la instancia (S-Latencia-Ago24).
    for attr in list(vars(usuario)):
        if "permiso" in attr and attr.startswith("_"):
            delattr(usuario, attr)


# ═════════════════════════════════════════════════════════════════════════════
# 1 · El permiso `(equipo, ver_actividad)`: nace para todos y se delega
# ═════════════════════════════════════════════════════════════════════════════


class TestElPermiso:

    def test_esta_en_el_catalogo_y_se_puede_delegar(self):
        from lib.permisos_defaults import CATALOGO_PERMISOS
        assert "ver_actividad" in CATALOGO_PERMISOS["equipo"]

    def test_aparece_en_los_modulos_visibles(self):
        from cuentas.context_processors import ACCION_VISIBLE_POR_MODULO, MODULOS_VISIBLES
        assert "equipo" in MODULOS_VISIBLES
        assert ACCION_VISIBLE_POR_MODULO["equipo"] == "ver_actividad"

    @pytest.mark.parametrize("rol", ["super_admin", "dueno", "contador", "disenador", "miembro"])
    def test_lo_trae_todo_rol_incluido_el_miembro(self, rol):
        """Decisión de Oscar: «quién ve: todos». `miembro` no tiene defaults
        propios, así que llega por `PERMISOS_UNIVERSALES`."""
        from lib.permisos_defaults import defaults_de
        assert "ver_actividad" in defaults_de(rol).get("equipo", [])

    @pytest.mark.django_db
    def test_un_usuario_nuevo_nace_con_el_permiso(self, usuario_factory):
        from cuentas.models.permiso_usuario import PermisoUsuario
        u = usuario_factory(rol="miembro")
        fila = PermisoUsuario.objects.get(usuario=u, modulo="equipo", permiso="ver_actividad")
        assert fila.activo

    @pytest.mark.django_db
    def test_la_migracion_siembra_a_los_que_ya_existen_y_es_idempotente(self, usuario_factory):
        import importlib

        from django.apps import apps as registro

        from cuentas.models.permiso_usuario import PermisoUsuario
        mig = importlib.import_module("cuentas.migrations.0046_seed_permiso_equipo_actividad")
        u = usuario_factory()
        PermisoUsuario.objects.filter(usuario=u, modulo="equipo").delete()

        mig.sembrar(registro, None)
        mig.sembrar(registro, None)

        filas = PermisoUsuario.objects.filter(usuario=u, modulo="equipo", permiso="ver_actividad")
        assert filas.count() == 1 and filas.get().activo

    @pytest.mark.django_db
    def test_la_migracion_no_reactiva_a_quien_se_le_quito(self, usuario_factory):
        import importlib

        from django.apps import apps as registro

        from cuentas.models.permiso_usuario import PermisoUsuario
        mig = importlib.import_module("cuentas.migrations.0046_seed_permiso_equipo_actividad")
        u = usuario_factory()
        _revocar(u)
        mig.sembrar(registro, None)
        assert not PermisoUsuario.objects.get(usuario=u, modulo="equipo").activo

    @pytest.mark.django_db
    def test_revocarlo_lo_quita(self, usuario_factory):
        from lib.permisos import puede_ver_actividad_equipo
        u = usuario_factory()
        assert puede_ver_actividad_equipo(u)
        _revocar(u)
        assert not puede_ver_actividad_equipo(_recargar(u))


# ═════════════════════════════════════════════════════════════════════════════
# 2 · Qué cuenta como actividad (y qué NO)
# ═════════════════════════════════════════════════════════════════════════════


def _req(path="/", **meta):
    from django.test import RequestFactory
    return RequestFactory().get(path, **meta)


class TestElSondeoNoCuenta:

    @pytest.mark.parametrize("ruta", [
        "/sistema/aviso-deploy/", "/sistema/aviso-deploy/semaforo/",
        "/static/css/tailwind.css", "/medios/ab/cd/x/w400.jpg",
        "/salud", "/ping", "/sw.js", "/site/vivo/fierro", "/site/vivo/equipo",
    ])
    def test_rutas_de_sondeo(self, ruta):
        from lib import presencia
        assert presencia.es_sondeo(_req(ruta))

    @pytest.mark.parametrize("nombre", [
        "recados:partial_bandeja", "recados:partial_mensajes",
        "directorio-en-linea", "site-vivo-negocio", "site-vivo-cualquiera-nuevo",
    ])
    def test_nombres_de_sondeo(self, nombre):
        from lib import presencia
        r = _req("/algo/")
        r.resolver_match = SimpleNamespace(view_name=nombre)
        assert presencia.es_sondeo(r)

    def test_la_cabecera_marca_un_sondeo_futuro(self):
        from lib import presencia
        assert presencia.es_sondeo(_req("/proyectos/", HTTP_X_DESPACHO_SONDEO="1"))

    def test_una_pantalla_normal_si_cuenta(self):
        from lib import presencia
        r = _req("/proyectos/")
        r.resolver_match = SimpleNamespace(view_name="proyectos-lista")
        assert not presencia.es_sondeo(r)

    def test_todo_hx_trigger_every_de_las_plantillas_es_sondeo(self):
        """El candado: si alguien agrega un panel que se refresca solo y olvida
        anotarlo, una pestaña abierta mantendría a su dueño «en línea» sin estar.
        Recorre TODAS las plantillas de las apps y los módulos compartidos."""
        from lib import presencia

        etiqueta = re.compile(r'<(?:[^>"]|"[^"]*")*>', re.S)
        faltan = []
        # Las partes se miran RELATIVAS a la raíz del repo: el repo puede vivir
        # dentro de un worktree (`.claude/worktrees/…`) y eso no lo descarta.
        plantillas = [p for p in RAIZ.rglob("*.html")
                      if not {"node_modules", "vendor", ".claude", ".git"}
                      & set(p.relative_to(RAIZ).parts)
                      and "templates" in p.relative_to(RAIZ).parts]
        assert plantillas, "no se encontró ninguna plantilla"
        for p in plantillas:
            texto = p.read_text(encoding="utf-8", errors="ignore")
            for tag in etiqueta.findall(texto):
                trig = re.search(r'hx-trigger="([^"]*)"', tag)
                if not trig or "every" not in trig.group(1):
                    continue
                get = re.search(r'hx-get="([^"]*)"', tag)
                if not get:
                    faltan.append(f"{p.relative_to(RAIZ)}: every sin hx-get")
                    continue
                valor = get.group(1)
                por_nombre = re.search(r"{%\s*url\s+'([^']+)'", valor)
                if por_nombre:
                    nombre = por_nombre.group(1)
                    if not (nombre in presencia.URL_NAMES_SONDEO
                            or nombre.startswith(presencia.PREFIJO_NOMBRE_SONDEO)):
                        faltan.append(f"{p.relative_to(RAIZ)}: {nombre}")
                elif not valor.startswith(presencia.PREFIJOS_RUTA_SONDEO):
                    faltan.append(f"{p.relative_to(RAIZ)}: {valor}")
        assert not faltan, (
            "Estos endpoints se piden solos y contarían como actividad; agrégalos a "
            f"lib.presencia.URL_NAMES_SONDEO: {faltan}"
        )

    def test_los_nombres_de_las_listas_existen(self):
        """Un nombre mal escrito en el mapa de pantallas no falla: cae al texto
        genérico sin que nadie lo note. Aquí sí se nota."""
        from django.urls import get_resolver

        from lib import presencia

        def nombres(urlconf):
            salida = set()

            def recorrer(res, ns=""):
                for pat in res.url_patterns:
                    if hasattr(pat, "url_patterns"):
                        recorrer(pat, f"{ns}{pat.namespace}:" if pat.namespace else ns)
                    elif pat.name:
                        salida.add(ns + pat.name)

            recorrer(get_resolver(urlconf))
            return salida

        taller, gerencia = nombres("tests.urls_taller"), nombres("tests.urls_gerencia")
        faltan = [n for n in presencia._PANTALLAS if n not in taller | gerencia]
        faltan += [f"{app}:{n}" for (app, n) in presencia._PANTALLAS_APP
                   if n not in (taller if app == "taller" else gerencia)]
        # Los del aviso de deploy viven sólo en los urlconf reales; ya los cubre
        # el prefijo `/sistema/`, así que aquí no se exigen.
        faltan += [n for n in presencia.URL_NAMES_SONDEO - {"aviso-deploy", "aviso-deploy-semaforo"}
                   if n not in taller | gerencia]
        assert not faltan, f"nombres de URL inexistentes: {faltan}"


# ═════════════════════════════════════════════════════════════════════════════
# 3 · Cuándo se escribe
# ═════════════════════════════════════════════════════════════════════════════


class TestCuandoEscribe:

    def _u(self, **campos):
        base = {"actividad_en": None, "actividad_url_name": "", "actividad_ruta": "",
                "actividad_app": "", "actividad_accion": ""}
        base.update(campos)
        return SimpleNamespace(**base)

    def test_sin_actividad_previa_escribe(self):
        from lib import presencia
        assert presencia.toca_escribir(self._u(), "/", "taller", "ver", _ahora())

    def test_misma_pantalla_una_vez_por_minuto(self):
        from lib import presencia
        ahora = _ahora()
        misma = dict(actividad_url_name="proyectos-lista", actividad_ruta="/proyectos/",
                     actividad_app="taller", actividad_accion="ver")
        u = self._u(actividad_en=ahora - timedelta(seconds=40), **misma)
        assert not presencia.toca_escribir(u, "/proyectos/", "taller", "ver", ahora)
        u = self._u(actividad_en=ahora - timedelta(seconds=61), **misma)
        assert presencia.toca_escribir(u, "/proyectos/", "taller", "ver", ahora)

    def test_cambiar_de_pantalla_se_anota_a_los_15_segundos(self):
        from lib import presencia
        ahora = _ahora()
        previo = dict(actividad_url_name="proyectos-lista", actividad_ruta="/proyectos/",
                      actividad_app="taller", actividad_accion="ver")
        u = self._u(actividad_en=ahora - timedelta(seconds=10), **previo)
        assert not presencia.toca_escribir(u, "/cotizaciones/", "taller", "ver", ahora)
        u = self._u(actividad_en=ahora - timedelta(seconds=16), **previo)
        assert presencia.toca_escribir(u, "/cotizaciones/", "taller", "ver", ahora)

    def test_pasar_de_mirar_a_editar_tambien_es_cambio(self):
        from lib import presencia
        ahora = _ahora()
        u = self._u(actividad_en=ahora - timedelta(seconds=20), actividad_url_name="x",
                    actividad_ruta="/proyectos/5/", actividad_app="taller", actividad_accion="ver")
        assert presencia.toca_escribir(u, "/proyectos/5/", "taller", "editar", ahora)

    def test_un_reloj_adelantado_no_congela(self):
        from lib import presencia
        ahora = _ahora()
        u = self._u(actividad_en=ahora + timedelta(minutes=5), actividad_url_name="x",
                    actividad_ruta="/", actividad_app="taller", actividad_accion="ver")
        assert not presencia.toca_escribir(u, "/", "taller", "ver", ahora)


# ═════════════════════════════════════════════════════════════════════════════
# 4 · Qué pantalla se anota
# ═════════════════════════════════════════════════════════════════════════════


class TestLaPantallaQueTieneEnfrente:

    def test_navegacion_normal_es_la_ruta(self):
        from lib import presencia
        assert presencia.ruta_de_pantalla(_req("/proyectos/")) == "/proyectos/"

    def test_htmx_es_la_pantalla_de_fondo_no_el_fragmento(self):
        """Un modal o un autoguardado se piden a su endpoint; la persona sigue
        viendo el proyecto."""
        from lib import presencia
        r = _req("/proyectos/5/editar-fechas", HTTP_HX_REQUEST="true",
                 HTTP_HX_CURRENT_URL="http://testserver/proyectos/5/")
        assert presencia.ruta_de_pantalla(r) == "/proyectos/5/"

    def test_htmx_que_redirige_anota_la_pantalla_nueva(self):
        from django.http import HttpResponse

        from lib import presencia
        r = _req("/proyectos/nuevo/", HTTP_HX_REQUEST="true",
                 HTTP_HX_CURRENT_URL="http://testserver/")
        resp = HttpResponse(status=204, headers={"HX-Redirect": "/proyectos/9/"})
        assert presencia.ruta_de_pantalla(r, resp) == "/proyectos/9/"

    def test_un_formulario_que_redirige_anota_el_destino(self):
        from django.http import HttpResponseRedirect

        from lib import presencia
        assert presencia.ruta_de_pantalla(
            _req("/cartera/nuevo/"), HttpResponseRedirect("/cartera/4/")) == "/cartera/4/"

    def test_un_fetch_de_fondo_es_de_la_pagina_que_lo_pidio(self):
        from lib import presencia
        r = _req("/catalogo/proveedores/buscar", HTTP_SEC_FETCH_MODE="cors",
                 HTTP_REFERER="http://testserver/catalogo/12/editar/")
        assert presencia.ruta_de_pantalla(r) == "/catalogo/12/editar/"

    def test_una_url_de_otro_sitio_no_se_cree(self):
        from lib import presencia
        r = _req("/proyectos/5/editar-fechas", HTTP_HX_REQUEST="true",
                 HTTP_HX_CURRENT_URL="https://malicioso.example/robar")
        assert presencia.ruta_de_pantalla(r) == "/proyectos/5/editar-fechas"


# ═════════════════════════════════════════════════════════════════════════════
# 5 · La petición de punta a punta (middleware)
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDePuntaAPunta:

    def test_entrar_marca_la_entrada(self, client, usuario_factory):
        from lib import presencia
        u = usuario_factory()
        client.force_login(u)
        u = _recargar(u)
        assert u.actividad_url_name == presencia.ENTRADA
        assert presencia.estado_de(u) == "en_linea"

    def test_salir_lo_desconecta_de_inmediato(self, client, usuario_factory):
        """Sin esto, quien cierra sesión seguiría «en línea» cinco minutos."""
        from lib import presencia
        u = usuario_factory()
        client.force_login(u)
        client.logout()
        u = _recargar(u)
        assert u.actividad_url_name == presencia.SALIDA
        assert presencia.estado_de(u) == "desconectado"

    def test_una_pantalla_se_anota_con_su_nombre_y_su_aparato(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        _poner_actividad(u, hace_s=120, url_name="otra", ruta="/otra/")
        r = client.get("/directorio/", HTTP_USER_AGENT=UA_IPHONE)
        assert r.status_code == 200
        u = _recargar(u)
        assert u.actividad_ruta == "/directorio/"
        assert u.actividad_url_name == "directorio-lista"
        assert u.actividad_app == "taller"
        assert u.actividad_accion == "ver"
        assert "iPhone" in u.actividad_agente

    def test_el_recuadro_del_dashboard_no_cuenta(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        _poner_actividad(u, hace_s=600, url_name="taller-home", ruta="/")
        antes = _recargar(u).actividad_en
        assert client.get("/directorio/en-linea/").status_code == 200
        assert _recargar(u).actividad_en == antes

    def test_un_error_no_es_estar_trabajando(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        _poner_actividad(u, hace_s=600)
        antes = _recargar(u).actividad_en
        client.get("/no-existe-esta-ruta/")
        assert _recargar(u).actividad_en == antes

    def test_nunca_tumba_la_peticion(self, client, usuario_factory, monkeypatch):
        """Si la escritura revienta, la pantalla sale igual."""
        from lib import presencia

        def revienta(*a, **k):
            raise RuntimeError("la base se cayó a media escritura")

        monkeypatch.setattr(presencia, "_guardar", revienta)
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        _poner_actividad(u, hace_s=600, url_name="otra", ruta="/otra/")
        assert client.get("/directorio/").status_code == 200

    def test_registrar_con_basura_no_lanza(self):
        from lib import presencia
        assert presencia.registrar(object(), object()) is False

    def test_la_impersonacion_anota_al_que_esta_ahi_de_verdad(self, usuario_factory):
        from django.http import HttpResponse

        from lib import presencia
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        _poner_actividad(admin, hace_s=600)
        _poner_actividad(otro, hace_s=600)
        antes_otro = _recargar(otro).actividad_en
        r = _req("/proyectos/")
        r.user, r.impersonador = otro, admin
        assert presencia.registrar(r, HttpResponse())
        assert _recargar(admin).actividad_ruta == "/proyectos/"
        assert _recargar(otro).actividad_en == antes_otro


# ═════════════════════════════════════════════════════════════════════════════
# 6 · Cómo se dice
# ═════════════════════════════════════════════════════════════════════════════


class TestComoSeDice:

    @pytest.mark.parametrize("hace_s,estado", [
        (30, "en_linea"), (4 * 60, "en_linea"), (6 * 60, "ausente"),
        (29 * 60, "ausente"), (31 * 60, "desconectado"),
    ])
    def test_umbrales(self, hace_s, estado):
        from lib import presencia
        ahora = _ahora()
        u = SimpleNamespace(actividad_en=ahora - timedelta(seconds=hace_s), actividad_url_name="x")
        assert presencia.estado_de(u, ahora) == estado

    def test_sin_actividad_es_nunca(self):
        from lib import presencia
        assert presencia.estado_de(SimpleNamespace(actividad_en=None)) == "nunca"

    def test_hace(self):
        from lib import presencia
        ahora = _ahora()
        assert presencia.hace(ahora - timedelta(seconds=20), ahora) == "hace un momento"
        assert presencia.hace(ahora - timedelta(minutes=12), ahora) == "hace 12 min"
        assert presencia.hace(None, ahora) == ""

    def test_hace_mas_de_una_hora_dice_la_hora(self):
        from django.utils import timezone

        from lib import presencia
        ahora = timezone.localtime(_ahora()).replace(hour=15, minute=0)
        texto = presencia.hace(ahora - timedelta(hours=2), ahora)
        assert texto.startswith("hoy a las")
        texto = presencia.hace(ahora - timedelta(days=1), ahora)
        assert texto.startswith("ayer a las")

    @pytest.mark.parametrize("agente,tipo,so,navegador", [
        (UA_IPHONE, "celular", "iOS", "Safari"),
        (UA_MAC_CHROME, "computadora", "macOS", "Chrome"),
        (UA_WIN_EDGE, "computadora", "Windows", "Edge"),
        (UA_ANDROID, "celular", "Android", "Chrome"),
    ])
    def test_el_aparato(self, agente, tipo, so, navegador):
        from lib import presencia
        d = presencia.dispositivo(agente)
        assert (d["tipo"], d["so"], d["navegador"]) == (tipo, so, navegador)
        assert d["texto"]

    def test_sin_agente_no_inventa(self):
        from lib import presencia
        assert presencia.dispositivo("")["texto"] == ""


@pytest.mark.django_db
class TestLaPantallaExactaRespetaPermisos:

    def test_quien_puede_ver_el_proyecto_ve_su_nombre_y_su_enlace(
            self, usuario_factory, proyecto_factory):
        from lib import presencia
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory(rol="super_admin")
        p = proyecto_factory(nombre="Gorras Cruz Azul")
        _poner_actividad(otro, hace_s=30, url_name="proyectos-detalle",
                         ruta=f"/proyectos/{p.pk}/", accion="editar", kwargs={"pk": p.pk})
        d = presencia.describir(_recargar(otro), viewer=admin, app_de_quien_mira="taller")
        assert d["pantalla"] == f"editando {p.codigo} · Gorras Cruz Azul"
        assert d["url"] == f"/proyectos/{p.pk}/"
        assert d["app_label"] == "El Taller"

    def test_quien_no_lo_podria_abrir_no_ve_el_nombre(self, usuario_factory, proyecto_factory):
        from lib import permisos, presencia
        disenador = usuario_factory(rol="disenador")
        otro = usuario_factory(rol="super_admin")
        p = proyecto_factory(nombre="Proyecto Secreto")
        assert not permisos.puede_ver_proyecto(disenador, p)
        _poner_actividad(otro, hace_s=30, url_name="proyectos-detalle",
                         ruta=f"/proyectos/{p.pk}/", kwargs={"pk": p.pk})
        d = presencia.describir(_recargar(otro), viewer=disenador, app_de_quien_mira="taller")
        assert "Secreto" not in d["pantalla"]
        assert d["pantalla"] == "viendo un proyecto"
        assert d["url"] == ""

    def test_la_pared_ve_todo(self, usuario_factory, proyecto_factory):
        from lib import presencia
        otro = usuario_factory()
        p = proyecto_factory(nombre="Mural")
        _poner_actividad(otro, hace_s=30, url_name="proyectos-detalle",
                         ruta=f"/proyectos/{p.pk}/", kwargs={"pk": p.pk})
        d = presencia.describir(_recargar(otro), viewer=None, app_de_quien_mira="gerencia")
        assert "Mural" in d["pantalla"]
        # Desde La Gerencia, una pantalla de El Taller es un enlace absoluto.
        assert d["url"].startswith("http")

    def test_un_objeto_borrado_no_truena(self, usuario_factory):
        from lib import presencia
        otro = usuario_factory()
        _poner_actividad(otro, hace_s=30, url_name="proyectos-detalle",
                         ruta="/proyectos/999999/", kwargs={"pk": 999999})
        d = presencia.describir(_recargar(otro), viewer=None)
        assert d["pantalla"] == "viendo un proyecto"

    def test_la_misma_url_en_otra_app_dice_otra_cosa(self, usuario_factory):
        from lib import presencia
        u = usuario_factory()
        _poner_actividad(u, hace_s=30, url_name="directorio-lista", ruta="/directorio/",
                         app="gerencia")
        assert presencia.describir(_recargar(u), viewer=None)["pantalla"] == "en El Directorio"
        _poner_actividad(u, hace_s=30, url_name="directorio-lista", ruta="/directorio/",
                         app="taller")
        assert presencia.describir(_recargar(u), viewer=None)["pantalla"] == "en Equipo"


# ═════════════════════════════════════════════════════════════════════════════
# 7 · Las pantallas: El Directorio, Equipo, el Dashboard
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLasPantallas:

    def test_el_directorio_de_gerencia_tiene_la_columna(self, client, settings, usuario_factory):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        _poner_actividad(otro, hace_s=60)
        client.force_login(admin)
        r = client.get("/directorio/")
        assert r.status_code == 200
        texto = r.content.decode()
        assert "Última actividad" in texto
        assert "En línea" in texto

    def test_la_columna_no_asoma_sin_permiso(self, client, settings, usuario_factory):
        """El encabezado sí sale (la tabla no puede cambiar de columnas), pero
        las celdas quedan vacías: nadie ve «En línea» de nadie."""
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        _poner_actividad(otro, hace_s=60)
        _revocar(admin)
        client.force_login(admin)
        texto = client.get("/directorio/").content.decode()
        assert "En línea" not in texto

    def test_equipo_pinta_el_puntito(self, client, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        _poner_actividad(otro, hace_s=8 * 60)
        client.force_login(admin)
        texto = client.get("/directorio/").content.decode()
        assert "Ausente" in texto
        assert "Última actividad" in texto

    def test_la_ficha_pinta_el_estado(self, client, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        _poner_actividad(otro, hace_s=45 * 60)
        client.force_login(admin)
        texto = client.get(f"/directorio/{otro.pk}/").content.decode()
        assert "Desconectado" in texto

    def test_el_recuadro_del_dashboard(self, client, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        lejos = usuario_factory()
        _poner_actividad(otro, hace_s=30, agente=UA_ANDROID)
        _poner_actividad(lejos, hace_s=3 * 60 * 60)
        client.force_login(admin)
        texto = client.get("/directorio/en-linea/").content.decode()
        assert "Quién está conectado" in texto
        assert otro.nombre_completo in texto
        # Los que se fueron viven en Equipo, no en el recuadro.
        assert lejos.nombre_completo not in texto

    def test_el_recuadro_sin_permiso_es_vacio(self, client, usuario_factory):
        """Vacío y 200, no 403: HTMX no pinta un 4xx y el recuadro se quedaría en
        «cargando…» para siempre."""
        u = usuario_factory()
        _revocar(u)
        client.force_login(u)
        r = client.get("/directorio/en-linea/")
        assert r.status_code == 200
        assert r.content == b""

    def test_el_dashboard_pide_el_recuadro(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        client.force_login(u)
        assert "/directorio/en-linea/" in client.get("/").content.decode()

    def test_el_dashboard_no_lo_pide_sin_permiso(self, client, usuario_factory):
        u = usuario_factory(rol="super_admin")
        _revocar(u)
        client.force_login(u)
        assert "/directorio/en-linea/" not in client.get("/").content.decode()

    def test_el_partial_va_en_las_dos_copias_identico(self):
        """Regla §18: dos copias sincronizadas."""
        taller = RAIZ / "el-taller/templates/_componentes_tailadmin/_presencia.html"
        gerencia = RAIZ / "la-gerencia/templates/_componentes_tailadmin/_presencia.html"
        assert taller.read_text() == gerencia.read_text()


# ═════════════════════════════════════════════════════════════════════════════
# 8 · El Vigía y El Site: el mismo panel, a la par
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestElPanelDelNuc:

    def _get(self, client, settings, host="localhost"):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        settings.ALLOWED_HOSTS = ["*"]
        return client.get("/site/vivo/equipo", HTTP_HOST=host)

    def test_en_la_pared_abre_sin_sesion_y_ve_nombres(self, client, settings,
                                                      usuario_factory, proyecto_factory):
        otro = usuario_factory()
        p = proyecto_factory(nombre="Playeras Tessa")
        _poner_actividad(otro, hace_s=20, url_name="proyectos-detalle",
                         ruta=f"/proyectos/{p.pk}/", kwargs={"pk": p.pk})
        r = self._get(client, settings)
        assert r.status_code == 200
        texto = r.content.decode()
        assert "El equipo ahora" in texto
        assert "Playeras Tessa" in texto
        # En la pared no hay a dónde picar: no hay sesión.
        assert f'href="/proyectos/{p.pk}/"' not in texto

    def test_desde_internet_sin_sesion_no_existe(self, client, settings):
        assert self._get(client, settings, host="gerencia.learningcenter.mx").status_code == 404

    def test_desde_gerencia_quien_tiene_site_pero_no_actividad(self, client, settings,
                                                                usuario_factory):
        from cuentas.models.permiso_usuario import PermisoUsuario
        u = usuario_factory(rol="miembro")
        PermisoUsuario.objects.update_or_create(usuario=u, modulo="site", permiso="ver",
                                                defaults={"activo": True})
        _revocar(u)
        client.force_login(u)
        r = self._get(client, settings, host="gerencia.learningcenter.mx")
        assert r.status_code == 200
        assert "No tienes permiso" in r.content.decode()

    def test_desde_gerencia_con_permiso_se_ve(self, client, settings, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        otro = usuario_factory()
        _poner_actividad(otro, hace_s=20)
        client.force_login(admin)
        r = self._get(client, settings, host="gerencia.learningcenter.mx")
        assert r.status_code == 200
        assert otro.nombre_completo in r.content.decode()

    def test_las_dos_pantallas_lo_piden(self):
        for pagina in ("vivo.html", "tablero.html"):
            texto = (RAIZ / "la-gerencia/templates/site" / pagina).read_text()
            assert "site-vivo-equipo" in texto, f"{pagina} no pide el panel del equipo"


# ═════════════════════════════════════════════════════════════════════════════
# 9 · El Chalán (MCP)
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestElChalan:

    def test_la_capacidad_esta_registrada_con_su_permiso(self):
        import capacidades
        cap = capacidades.CAPACIDADES["quien_esta_en_linea"]
        assert cap.gating == "equipo_actividad"
        assert cap.modo == "lectura"

    def test_esta_documentada_para_el_chat(self):
        from lib.dictado_catalogo import CONSULTAS_CHAT
        assert any(c["nombre"] == "quien_esta_en_linea" for c in CONSULTAS_CHAT)

    def test_contesta_quien_esta_en_linea(self, usuario_factory):
        import capacidades
        yo = usuario_factory()
        jorge = usuario_factory()
        _poner_actividad(jorge, hace_s=30, url_name="cotizaciones:lista",
                         ruta="/cotizaciones/", agente=UA_IPHONE)
        salida = capacidades.ejecutar("quien_esta_en_linea", {}, yo)
        assert "error" not in salida
        nombres = [p["nombre"] for p in salida["en_linea"]]
        assert jorge.nombre_completo in nombres
        fila = next(p for p in salida["en_linea"] if p["nombre"] == jorge.nombre_completo)
        assert fila["pantalla"] == "en Cotizaciones"
        assert "iOS" in fila["dispositivo"]

    def test_pregunta_por_una_persona(self, usuario_factory):
        import capacidades
        yo = usuario_factory()
        jorge = usuario_factory()
        jorge.nombre_completo = "Jorge Berebichez"
        jorge.save(update_fields=["nombre_completo"])
        _poner_actividad(jorge, hace_s=10 * 60)
        salida = capacidades.ejecutar("quien_esta_en_linea", {"persona": "jorge"}, yo)
        assert salida["persona"]["nombre"] == "Jorge Berebichez"
        assert salida["persona"]["estado"] == "Ausente"

    def test_dos_que_coinciden_no_se_adivinan(self, usuario_factory):
        import capacidades
        yo = usuario_factory()
        usuario_factory()  # dos «Usuario N»: «usuario» casa con los dos
        salida = capacidades.ejecutar("quien_esta_en_linea", {"persona": "usuario"}, yo)
        assert salida["error"] == "ambiguo"

    def test_sin_permiso_no_contesta(self, usuario_factory):
        import capacidades
        yo = usuario_factory()
        _revocar(yo)
        yo = _recargar(yo)
        assert capacidades.ejecutar("quien_esta_en_linea", {}, yo)["error"] == "sin_permiso"
        assert "quien_esta_en_linea" not in [c.nombre for c in capacidades.listar(yo)]
