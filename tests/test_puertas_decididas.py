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
from tests.test_permisos_sin_rol_literal import FOTO_ROLES, FOTO_USUARIOS, _filas_de_la_foto

pytestmark = pytest.mark.django_db

MIGRACIONES = ("0047_permisos_sin_rol_literal",)


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
