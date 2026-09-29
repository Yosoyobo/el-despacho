"""Las puertas que Oscar decidió el 2026-09-28 — éstas SÍ cambian a alguien.

2026.09.05 pasó las puertas por rol a permisos «como hoy» y dejó tres por rol
PRIMARIO porque convertirlas cambiaba a alguien (más un Director que no leía
comentarios). Oscar las decidió; aquí se fija el CAMBIO, no la equivalencia:
para cada persona de la foto de producción (la misma de
`tests/test_permisos_sin_rol_literal.py`, anonimizada) se escribe qué pasaba
ANTES (la regla vieja, congelada) y qué pasa DESPUÉS (el código de hoy sobre
los datos que dejan las migraciones 0047 + 0048).

Quién es quién en la foto:
  · 1 y 3 — super_admin.
  · 4 — rol «Director» (clave `dueno`) sobre primario `miembro` (Alex).
  · 5 — rol «Administrativo» (personalizado) sobre primario `miembro` (Larry).

Si una tabla de aquí falla, alguien ganó o perdió algo que Oscar no decidió.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from django.test import override_settings

from lib import permisos
from tests.test_permisos_sin_rol_literal import (
    ASIGNABLES,
    FOTO_ROLES,
    FOTO_USUARIOS,
    PRIMARIOS,
    _comentarios,
    _filas_de_la_foto,
    v_ver_comentario,
    v_ver_proyecto,
)

pytestmark = pytest.mark.django_db

MIGRACIONES = ("0047_permisos_sin_rol_literal", "0048_puertas_decididas")


@pytest.fixture
def foto(proyecto_factory):
    """La foto de producción cargada y con las migraciones de datos aplicadas:
    el estado en que queda producción al desplegar."""
    from apps.los_proyectos.models import ProyectoAsignacion
    from django.apps import apps as django_apps

    from cuentas.models.permiso_usuario import PermisoUsuario
    from cuentas.models.rol import Rol
    from cuentas.models.usuario import Usuario

    Rol.objects.all().delete()
    for rid, (clave, nombre, p) in FOTO_ROLES.items():
        Rol.objects.create(pk=rid, clave=clave, nombre=nombre, permisos=p)
    for uid, d in FOTO_USUARIOS.items():
        u = Usuario(pk=uid, email=f"foto{uid}@ejemplo.com", nombre_completo=f"Foto {uid}", rol=d["rol"])
        u.set_unusable_password()
        u.save()
        u.roles_extra.set(Rol.objects.filter(pk__in=d["roles"]))
    PermisoUsuario.objects.filter(usuario_id__in=FOTO_USUARIOS).delete()  # las del signal
    PermisoUsuario.objects.bulk_create([
        PermisoUsuario(usuario_id=uid, modulo=m, permiso=a, activo=activo)
        for (uid, m, a), activo in _filas_de_la_foto().items()
    ])
    # Después de los usuarios: los ids 1–5 son los de la foto, y la fábrica de
    # proyectos crea a su propio autor (que es «otra persona» para los
    # comentarios ajenos).
    propio, ajeno = proyecto_factory(nombre="Asignado"), proyecto_factory(nombre="Ajeno")
    for uid in FOTO_USUARIOS:
        ProyectoAsignacion.objects.create(proyecto=propio, usuario_id=uid)
    for nombre in MIGRACIONES:
        importlib.import_module(f"cuentas.migrations.{nombre}").aplicar(django_apps, None)
    permisos.invalidar_cache_permisos()
    usuarios = {u.pk: u for u in Usuario.objects.filter(pk__in=FOTO_USUARIOS)}
    return SimpleNamespace(u=usuarios, propio=propio, ajeno=ajeno)


def _tabla(foto, vieja, nueva):
    """{uid: (antes, después)} para cada persona de la foto."""
    return {uid: (vieja(u), nueva(u)) for uid, u in sorted(foto.u.items())}


# ═════════════════════════════════════════════════════════════════════════════
# 1. La sesión de La Gerencia: `gerencia.acceder`, en cada petición
# ═════════════════════════════════════════════════════════════════════════════

def v_gerencia_saca(u):
    """Antes: el middleware sacaba sólo al rol PRIMARIO contador/diseñador."""
    return getattr(u, "rol", None) in ("contador", "disenador")


def n_gerencia_saca(u):
    from lib.middleware import RedirigirRolesOperativosMiddleware as M

    return M._debe_redirigir(SimpleNamespace(path="/", user=u))


MIDDLEWARE_GERENCIA = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "lib.middleware.RedirigirRolesOperativosMiddleware",
]


class TestSesionDeLaGerencia:
    def test_quien_sale_antes_y_despues(self, foto):
        """Larry (5) tiene `gerencia.acceder` apagado: no podía ENTRAR (el login
        ya pedía el permiso), pero con una sesión abierta se quedaba. Ahora sale.
        Nadie más de la foto cambia."""
        assert _tabla(foto, v_gerencia_saca, n_gerencia_saca) == {
            1: (False, False),
            3: (False, False),
            4: (False, False),   # Alex tiene gerencia.acceder: se queda
            5: (False, True),    # ← el cambio decidido
        }

    @override_settings(ROOT_URLCONF="tests.urls_gerencia", MIDDLEWARE=MIDDLEWARE_GERENCIA,
                       TALLER_URL="http://testserver-taller/")
    def test_con_la_sesion_abierta_sale_de_inmediato(self, client, foto):
        client.force_login(foto.u[5])
        resp = client.get("/")
        assert resp.status_code == 302
        assert resp["Location"] == "http://testserver-taller/"
        # …y la sesión de La Gerencia quedó cerrada: la siguiente petición ya
        # es anónima (el login la atiende, no el middleware).
        assert "_auth_user_id" not in client.session
        assert client.get("/sign-in").status_code == 200

    @override_settings(ROOT_URLCONF="tests.urls_gerencia", MIDDLEWARE=MIDDLEWARE_GERENCIA,
                       TALLER_URL="http://testserver-taller/")
    def test_alex_sigue_en_la_gerencia(self, client, foto):
        client.force_login(foto.u[4])
        assert client.get("/").status_code == 200
        assert "_auth_user_id" in client.session

    @override_settings(ROOT_URLCONF="tests.urls_gerencia", MIDDLEWARE=MIDDLEWARE_GERENCIA,
                       TALLER_URL="http://testserver-taller/")
    def test_revocar_desde_el_directorio_saca_a_la_siguiente_peticion(self, client, foto):
        from cuentas.models.permiso_usuario import PermisoUsuario

        client.force_login(foto.u[4])
        assert client.get("/").status_code == 200
        PermisoUsuario.objects.filter(usuario_id=4, modulo="gerencia", permiso="acceder").update(activo=False)
        permisos.invalidar_cache_permisos()
        resp = client.get("/")
        assert resp.status_code == 302 and resp["Location"] == "http://testserver-taller/"


# ═════════════════════════════════════════════════════════════════════════════
# 2. Google SSO a La Gerencia: `gerencia.acceder`
# ═════════════════════════════════════════════════════════════════════════════

GERENCIA = "gerencia.learningcenter.mx"
TALLER = "taller.learningcenter.mx"


def v_sso_gerencia(u):
    """Antes: sólo el rol PRIMARIO super_admin/dueño entraba por Google."""
    return getattr(u, "rol", None) in ("super_admin", "dueno")


def n_sso(host):
    from auth_google.views import _host_permite

    return lambda u: _host_permite(host, u)


def _configurar_google():
    from ajustes.models.credencial import Credencial

    Credencial.guardar("google_oauth_client_id", "abc.apps.googleusercontent.com")
    Credencial.guardar("google_oauth_client_secret", "GOCSPX-prueba")


def _callback_google(client, email, host):
    from unittest.mock import patch

    from lib.google_oauth import PerfilGoogle

    client.get("/auth/google/iniciar", HTTP_HOST=host)
    state = client.session.get("_google_oauth_state")
    perfil = PerfilGoogle(sub=f"g-{email}", email=email, email_verified=True, nombre="X",
                          apellido="", foto_url=None, locale=None)
    with patch("auth_google.views.intercambiar_codigo_por_perfil", return_value=perfil):
        return client.get("/auth/google/callback", {"code": "c", "state": state}, HTTP_HOST=host)


class TestGoogleALaGerencia:
    def test_quien_entra_antes_y_despues(self, foto):
        """Alex (4) es Director sobre primario `miembro`: entraba con contraseña
        pero no con Google. Ahora entra por los dos (consecuencia aceptada)."""
        assert _tabla(foto, v_sso_gerencia, n_sso(GERENCIA)) == {
            1: (True, True),
            3: (True, True),
            4: (False, True),    # ← el cambio decidido
            5: (False, False),   # sin gerencia.acceder, igual que con contraseña
        }

    def test_el_taller_no_cambia(self, foto):
        assert _tabla(foto, lambda u: True, n_sso(TALLER)) == {
            uid: (True, True) for uid in foto.u
        }

    def test_google_y_contrasena_deciden_igual(self, foto):
        """Las dos puertas de La Gerencia dicen lo mismo para cada persona."""
        from apps.auth_gerencia.views import _puede_entrar_gerencia

        for uid, u in foto.u.items():
            assert n_sso(GERENCIA)(u) == _puede_entrar_gerencia(u), uid

    def test_alex_entra_con_google(self, client, foto):
        _configurar_google()
        resp = _callback_google(client, "foto4@ejemplo.com", GERENCIA)
        assert resp.status_code == 302 and resp["Location"] == "/"
        assert client.session.get("_auth_user_id") == "4"

    def test_larry_no_entra_con_google(self, client, foto):
        _configurar_google()
        resp = _callback_google(client, "foto5@ejemplo.com", GERENCIA)
        assert resp.status_code == 403
        assert "gerencia · acceder" in resp.content.decode()
        assert "_auth_user_id" not in client.session


# ═════════════════════════════════════════════════════════════════════════════
# 3. Autocompletar @#$: las sugerencias siguen a los permisos de ver
# ═════════════════════════════════════════════════════════════════════════════

def _sugerencias(client, u, tipo):
    client.force_login(u)
    resp = client.get(f"/api/autocomplete/{tipo}")
    assert resp.status_code == 200
    return {r["slug"] for r in resp.json()["resultados"]}


def v_clientes(u):
    """Antes: todos veían clientes menos el rol PRIMARIO diseñador."""
    return getattr(u, "rol", None) != "disenador"


def v_proyectos(u):
    """Antes: el rol PRIMARIO diseñador, sus asignados; todos los demás, todos."""
    return "asignados" if getattr(u, "rol", None) == "disenador" else "todos"


class TestAutocompletar:
    def test_clientes_antes_y_despues(self, client, foto):
        """Larry (5) deja de ver clientes: Clientes ya le daba 403 (su
        `cartera.ver` quedó apagado en la 0047). Consecuencia aceptada."""
        slug = foto.propio.cliente.slug
        assert _tabla(foto, v_clientes, lambda u: slug in _sugerencias(client, u, "clientes")) == {
            1: (True, True),
            3: (True, True),
            4: (True, True),
            5: (True, False),    # ← el cambio decidido
        }

    def test_proyectos_antes_y_despues(self, client, foto):
        """Con la misma regla, Larry tampoco ve proyectos al autocompletar: sin
        `proyectos.ver` ni `ver_todos`, su lista de Proyectos ya salía vacía."""
        propio, ajeno = foto.propio.slug, foto.ajeno.slug

        def nueva(u):
            vistos = _sugerencias(client, u, "proyectos") & {propio, ajeno}
            return {frozenset({propio, ajeno}): "todos", frozenset({propio}): "asignados",
                    frozenset(): "ninguno"}[frozenset(vistos)]

        assert _tabla(foto, v_proyectos, nueva) == {
            1: ("todos", "todos"),
            3: ("todos", "todos"),
            4: ("todos", "todos"),       # Alex: proyectos.ver_todos
            5: ("todos", "ninguno"),     # ← mismo permiso que su lista de Proyectos
        }

    def test_las_sugerencias_dicen_lo_mismo_que_las_pantallas(self, client, foto):
        """Para cada persona: sugiere un cliente sii puede ver La Cartera, y un
        proyecto sii puede abrirlo."""
        for uid, u in foto.u.items():
            assert (foto.propio.cliente.slug in _sugerencias(client, u, "clientes")) \
                == permisos.puede_ver_cartera(u), uid
            proyectos = _sugerencias(client, u, "proyectos")
            for p in (foto.propio, foto.ajeno):
                assert (p.slug in proyectos) == permisos.puede_ver_proyecto(u, p), (uid, p.nombre)

    def test_personas_no_cambian(self, client, foto):
        """`@` no tiene permiso de ver que lo gatee: todos ven al mismo equipo."""
        vistas = {uid: _sugerencias(client, u, "usuarios") for uid, u in foto.u.items()}
        assert vistas[1] and all(v == vistas[1] for v in vistas.values()), vistas

    @pytest.mark.parametrize("primario,esperado", [
        ("disenador", "asignados"), ("contador", "todos"), ("dueno", "todos"),
        ("super_admin", "todos"), ("miembro", "ninguno"),
    ])
    def test_por_rol_primario_con_sus_defaults(self, client, usuario_factory, proyecto_factory,
                                               primario, esperado):
        """Sin la foto: el diseñador sigue acotado a sus asignados, contador y
        dueño ven todos, y un `miembro` sin permisos de proyectos (antes veía
        todos) ya no ve ninguno."""
        from apps.los_proyectos.models import ProyectoAsignacion

        u = usuario_factory(rol=primario)
        propio, ajeno = proyecto_factory(), proyecto_factory()
        ProyectoAsignacion.objects.create(proyecto=propio, usuario=u)
        vistos = _sugerencias(client, u, "proyectos") & {propio.slug, ajeno.slug}
        assert vistos == {"todos": {propio.slug, ajeno.slug}, "asignados": {propio.slug},
                          "ninguno": set()}[esperado]

    def test_busqueda_inversa_de_clientes_sigue_a_cartera_ver(self, client, foto):
        from referencias.models import Referencia

        cliente = foto.propio.cliente
        Referencia.objects.create(contenedor_tipo="recado", contenedor_id=1, tipo="cliente",
                                  cliente_id=cliente.pk, token_original=f"${cliente.slug}",
                                  posicion_inicio=0, posicion_fin=5)
        totales = {}
        for uid, u in foto.u.items():
            client.force_login(u)
            resp = client.get(f"/api/referencias/clientes/{cliente.pk}")
            assert resp.status_code == 200
            totales[uid] = resp.json()["total"]
        assert totales == {1: 1, 3: 1, 4: 1, 5: 0}


# ═════════════════════════════════════════════════════════════════════════════
# 4. Alex lee comentarios (0048): los roles asignados cuentan
# ═════════════════════════════════════════════════════════════════════════════

TODAS = frozenset(f"{clase} en {cual}" for clase in ("público", "interno ajeno", "interno propio")
                  for cual in ("asignado", "ajeno"))


def _lee(foto_o_esc, fn):
    """Qué comentarios lee `u` según `fn(u, c)`: {«clase en proyecto»}."""
    def _para(u):
        return frozenset(
            f"{clase} en {cual}"
            for cual, p in (("asignado", foto_o_esc.propio), ("ajeno", foto_o_esc.ajeno))
            for clase, c in _comentarios(foto_o_esc.ajeno.creado_por_id, p, u).items()
            if fn(u, c)
        )
    return _para


def v_ver_comentario_por_roles_asignados(u, c):
    """La regla vieja leyendo los roles EFECTIVOS en vez del primario: lo que
    decidió Oscar para quien tiene un rol del sistema asignado."""
    from lib.permisos import roles_efectivos

    roles = roles_efectivos(u)
    if roles & {"super_admin", "dueno", "contador"}:
        return True
    if "disenador" in roles:
        if c.es_interno and c.autor_id != u.pk:
            return False
        return v_ver_proyecto(u, c.proyecto)
    return False


def _migracion_0048():
    return importlib.import_module("cuentas.migrations.0048_puertas_decididas")


class TestAlexLeeComentarios:
    def test_quien_lee_que_antes_y_despues(self, foto):
        """Alex (4) no leía nada —la regla era por su primario `miembro`— y
        ahora lee como el dueño que es: todo, internos ajenos incluidos."""
        antes = _lee(foto, v_ver_comentario)
        despues = _lee(foto, permisos.puede_ver_comentario)
        assert _tabla(foto, antes, despues) == {
            1: (TODAS, TODAS),
            3: (TODAS, TODAS),
            4: (frozenset(), TODAS),      # ← el cambio decidido
            5: (frozenset(), frozenset()),  # «Administrativo» no es rol del sistema
        }

    def test_la_0048_toca_exactamente_estas_filas_de_la_foto(self):
        roles = [{"id": rid, "clave": clave} for rid, (clave, _n, _p) in FOTO_ROLES.items()]
        usuarios = [{"id": uid, "rol": d["rol"], "roles": d["roles"]} for uid, d in FOTO_USUARIOS.items()]
        # Las filas como quedan tras la 0047 (que apagó ver_internos de Alex).
        from tests.test_permisos_sin_rol_literal import _migracion

        filas = _filas_de_la_foto()
        _json, filas_0047 = _migracion().planear(
            usuarios, [{**r, "permisos": FOTO_ROLES[r["id"]][2]} for r in roles], filas)
        filas.update({(u, m, a): activo for u, m, a, activo in filas_0047})
        assert filas[(4, "pizarron", "ver_internos")] is False
        plan = _migracion_0048().planear_comentarios(usuarios, roles, filas)
        assert sorted(plan) == [
            (4, "pizarron", "ver_comentarios", True),
            (4, "pizarron", "ver_internos", True),
        ]
        # Idempotente: con esas filas ya puestas no queda nada que hacer.
        filas.update({(u, m, a): activo for u, m, a, activo in plan})
        assert _migracion_0048().planear_comentarios(usuarios, roles, filas) == []

    def test_enciende_aunque_la_grilla_la_haya_guardado_apagada(self, foto):
        """La grilla de El Directorio escribe una fila por acción al guardarse:
        una fila apagada no es una decisión. La 0048 gana."""
        from django.apps import apps as django_apps

        from cuentas.models.permiso_usuario import PermisoUsuario

        PermisoUsuario.objects.filter(usuario_id=4, modulo="pizarron",
                                      permiso="ver_comentarios").update(activo=False)
        _migracion_0048().aplicar(django_apps, None)
        assert PermisoUsuario.objects.get(usuario_id=4, modulo="pizarron",
                                          permiso="ver_comentarios").activo is True

    def test_regla_general_sobre_cada_combinacion_de_roles(self, usuario_factory, proyecto_factory):
        """Sobre los 160 usuarios sintéticos (5 primarios × 32 combinaciones de
        roles asignados): tras la 0048, cada quien lee exactamente lo que la
        regla vieja le daría leyendo sus roles EFECTIVOS. Y sólo cambió quien
        tiene asignado un rol del sistema que su primario no le daba."""
        import itertools

        from apps.los_proyectos.models import ProyectoAsignacion
        from django.apps import apps as django_apps

        from cuentas.models.rol import Rol

        propio, ajeno = proyecto_factory(nombre="Asignado"), proyecto_factory(nombre="Ajeno")
        roles = {c: Rol.objects.get(clave=c) for c in ASIGNABLES}
        usuarios = []
        for primario in PRIMARIOS:
            for n in range(len(ASIGNABLES) + 1):
                for extra in itertools.combinations(ASIGNABLES, n):
                    u = usuario_factory(rol=primario)
                    if extra:
                        u.roles_extra.add(*(roles[c] for c in extra))
                    ProyectoAsignacion.objects.create(proyecto=propio, usuario=u)
                    usuarios.append((primario, set(extra), u))
        esc = SimpleNamespace(propio=propio, ajeno=ajeno)
        antes = {u.pk: _lee(esc, permisos.puede_ver_comentario)(u) for _p, _e, u in usuarios}
        _migracion_0048().aplicar(django_apps, None)
        permisos.invalidar_cache_permisos()
        esperado_lee = _lee(esc, v_ver_comentario_por_roles_asignados)
        distintos, cambiaron = [], set()
        for primario, extra, u in usuarios:
            ahora = _lee(esc, permisos.puede_ver_comentario)(u)
            if ahora != esperado_lee(u):
                distintos.append(f"{primario}+{sorted(extra)}")
            if ahora != antes[u.pk]:
                cambiaron.add((primario, frozenset(extra)))
        assert not distintos, distintos
        todos, fin = {"super_admin", "dueno", "contador", "disenador"}, {"super_admin", "dueno", "contador"}
        # El caso de Alex, y el diseñador de primario que tiene asignado un rol
        # que lee los internos, están entre los que cambiaron.
        assert ("miembro", frozenset({"dueno"})) in cambiaron
        assert ("disenador", frozenset({"contador"})) in cambiaron
        for primario, extra in cambiaron:
            assert (primario not in todos and extra & todos) or (primario not in fin and extra & fin), \
                (primario, extra)
