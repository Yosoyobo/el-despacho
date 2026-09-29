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

    def test_no_toca_a_quien_ya_leia_por_su_rol_primario(self):
        """Un contador de primario con Director asignado ya leía por la regla
        vieja: si alguien le apagó los comentarios, esa fila no es de la 0048."""
        roles = [{"id": 1, "clave": "dueno"}]
        usuarios = [{"id": 7, "rol": "contador", "roles": [1]}]
        filas = {(7, "pizarron", "ver_comentarios"): False, (7, "pizarron", "ver_internos"): False}
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


# ═════════════════════════════════════════════════════════════════════════════
# 5. proyectos.crear / asignar / cambiar_estado: conectadas «como hoy»
# ═════════════════════════════════════════════════════════════════════════════
#
# Aquí sí es equivalencia: hasta hoy las tres pedían `proyectos.editar`
# (`puede_gestionar_proyectos`), y la 0048 las sembró a exactamente quien lo
# tenía. El recorrido de las 160 combinaciones está en el candado
# (`PUERTAS` de `tests/test_permisos_sin_rol_literal.py`).

NUEVAS = {
    "crear": permisos.puede_crear_proyecto,
    "asignar": permisos.puede_asignar_proyecto,
    "cambiar_estado": permisos.puede_cambiar_estado_proyecto,
}


def _gestionar_de_antes(u):
    """La puerta de antes de las tres: `puede_gestionar_proyectos` (`editar`)."""
    return permisos.puede_gestionar_proyectos(u)


class TestProyectosComoHoy:
    def test_en_la_foto_nadie_gana_ni_pierde(self, foto):
        for nombre, nueva in NUEVAS.items():
            assert _tabla(foto, _gestionar_de_antes, nueva) == {
                1: (True, True), 3: (True, True), 4: (True, True), 5: (False, False),
            }, nombre

    def test_en_la_foto_la_0048_no_escribe_nada_de_proyectos(self):
        from tests.test_permisos_sin_rol_literal import _migracion

        roles = [{"id": rid, "clave": c, "permisos": p} for rid, (c, _n, p) in FOTO_ROLES.items()]
        usuarios = [{"id": uid, "rol": d["rol"], "roles": d["roles"]} for uid, d in FOTO_USUARIOS.items()]
        filas = _filas_de_la_foto()
        json_0047, filas_0047 = _migracion().planear(usuarios, roles, filas)
        filas.update({(u, m, a): activo for u, m, a, activo in filas_0047})
        roles = [{**r, "permisos": json_0047.get(r["id"], r["permisos"])} for r in roles]
        assert _migracion_0048().planear_proyectos(usuarios, roles, filas) == ({}, [])

    def test_casos_raros_quedan_igual_que_editar(self, usuario_factory):
        """Los casos en que las tres acciones decían otra cosa que `editar` —y no
        importaba porque nadie las leía—. Tras la 0048 dicen lo mismo."""
        from django.apps import apps as django_apps

        from cuentas.models.permiso_usuario import PermisoUsuario as PU
        from cuentas.models.rol import Rol

        def fila(u, accion, activo):
            PU.objects.update_or_create(usuario=u, modulo="proyectos", permiso=accion,
                                        defaults={"activo": activo})

        # El JSON del diseñador (rol del sistema) trae `crear` sin `editar`.
        dis = Rol.objects.get(clave="disenador")
        dis.permisos = {**dis.permisos, "proyectos": ["crear", "ver"]}
        dis.save()
        # Un rol personalizado que da `asignar` sin `editar`.
        raro = Rol.objects.create(clave="raro", nombre="Raro", permisos={"proyectos": ["asignar", "ver"]})

        casos = {}
        casos["fila editar, sin las otras"] = u = usuario_factory(rol="miembro")
        fila(u, "editar", True)
        casos["fila crear, sin editar"] = u = usuario_factory(rol="miembro")
        fila(u, "crear", True)
        casos["rol raro con asignar"] = u = usuario_factory(rol="miembro")
        u.roles_extra.add(raro)
        casos["diseñador asignado (JSON con crear)"] = u = usuario_factory(rol="miembro")
        u.roles_extra.add(dis)
        casos["dueño con editar revocado"] = u = usuario_factory(rol="dueno")
        fila(u, "editar", False)
        casos["Director asignado con editar revocado"] = u = usuario_factory(rol="miembro")
        u.roles_extra.add(Rol.objects.get(clave="dueno"))
        fila(u, "editar", False)
        casos["contador con Director asignado"] = u = usuario_factory(rol="contador")
        u.roles_extra.add(Rol.objects.get(clave="dueno"))
        casos["super_admin con todo revocado"] = u = usuario_factory(rol="super_admin")
        for a in ("editar", *NUEVAS):
            fila(u, a, False)
        permisos.invalidar_cache_permisos()

        antes = {n: _gestionar_de_antes(u) for n, u in casos.items()}
        # Sin la 0048, varios casos dirían otra cosa (la prueba no es de adorno).
        assert any(nueva(u) != antes[n] for n, u in casos.items() for nueva in NUEVAS.values())

        _migracion_0048().aplicar(django_apps, None)
        permisos.invalidar_cache_permisos()
        distintos = [f"{n}: {a}" for n, u in casos.items() for a, nueva in NUEVAS.items()
                     if nueva(u) != antes[n]]
        assert not distintos, distintos
        assert antes == {
            "fila editar, sin las otras": True,
            "fila crear, sin editar": False,
            "rol raro con asignar": False,
            "diseñador asignado (JSON con crear)": False,
            "dueño con editar revocado": False,
            "Director asignado con editar revocado": False,
            "contador con Director asignado": True,
            "super_admin con todo revocado": True,
        }
        # El JSON del diseñador quedó parejo con `editar`; el personalizado, intacto.
        dis.refresh_from_db()
        raro.refresh_from_db()
        assert dis.permisos["proyectos"] == ["ver"]
        assert raro.permisos == {"proyectos": ["asignar", "ver"]}
        # Idempotente.
        filas = PU.objects.count()
        _migracion_0048().aplicar(django_apps, None)
        assert PU.objects.count() == filas

    @pytest.mark.parametrize("simulado", ["super_admin", "dueno", "contador", "disenador"])
    def test_ver_como_rol_decide_igual(self, usuario_factory, simulado):
        """«Ver como rol» lee sólo el JSON del rol: las tres van con `editar`."""
        sa = usuario_factory(rol="super_admin")
        sa._rol_simulado = simulado
        for nombre, nueva in NUEVAS.items():
            assert nueva(sa) == permisos.puede(sa, "proyectos", "editar"), (simulado, nombre)


def _solo(usuario_factory, **acciones):
    """Un `miembro` (sin defaults de proyectos) con exactamente estas acciones
    de proyectos encendidas —más `ver_todos` para llegar a cualquiera—."""
    from cuentas.models.permiso_usuario import PermisoUsuario

    u = usuario_factory(rol="miembro")
    for accion, activo in {"ver": True, "ver_todos": True, **acciones}.items():
        PermisoUsuario.objects.update_or_create(usuario=u, modulo="proyectos", permiso=accion,
                                                defaults={"activo": activo})
    permisos.invalidar_cache_permisos()
    return u


class TestCadaPantallaPreguntaPorSuAccion:
    """Que las tres acciones de verdad estén conectadas: con `editar` a secas
    ya no se crea, asigna ni cambia de estado, y con la acción sola sí."""

    def test_crear(self, client, usuario_factory, proyecto_factory):
        p = proyecto_factory()
        client.force_login(_solo(usuario_factory, editar=True))
        assert client.get("/proyectos/nuevo").status_code == 403
        assert client.get(f"/proyectos/{p.pk}/duplicar").status_code == 403
        assert "+ Nuevo proyecto" not in client.get("/proyectos/").content.decode()
        client.force_login(_solo(usuario_factory, crear=True))
        assert client.get("/proyectos/nuevo").status_code == 200
        assert client.get(f"/proyectos/{p.pk}/duplicar").status_code == 200
        assert "+ Nuevo proyecto" in client.get("/proyectos/").content.decode()

    def test_asignar(self, client, usuario_factory, proyecto_factory):
        p = proyecto_factory()
        client.force_login(_solo(usuario_factory, editar=True))
        assert client.get(f"/proyectos/{p.pk}/asignar").status_code == 403
        client.force_login(_solo(usuario_factory, asignar=True))
        assert client.get(f"/proyectos/{p.pk}/asignar").status_code == 200

    def test_cambiar_estado(self, client, usuario_factory, proyecto_factory):
        from apps.los_proyectos.models import Proyecto

        p = proyecto_factory(estado="por_cotizar")
        client.force_login(_solo(usuario_factory, editar=True))
        assert client.post(f"/proyectos/{p.pk}/cambiar-estado", {"estado": "esperando_respuesta"},
                           HTTP_HX_REQUEST="true").status_code == 403
        assert client.get(f"/proyectos/{p.pk}/motivo-cancelacion").status_code == 403
        client.force_login(_solo(usuario_factory, cambiar_estado=True))
        r = client.post(f"/proyectos/{p.pk}/cambiar-estado", {"estado": "esperando_respuesta"},
                        HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert Proyecto.objects.get(pk=p.pk).estado == "esperando_respuesta"

    def test_el_autoguardado_del_detalle_no_se_salta_estado_ni_equipo(
            self, client, usuario_factory, proyecto_factory):
        """El detalle manda estado (oculto) y equipo en el mismo POST que el
        resto: con `editar` sin las otras dos, se guarda lo demás y esos no."""
        from apps.los_proyectos.models import Proyecto, ProyectoAsignacion

        p = proyecto_factory(estado="por_cotizar", descripcion="antes")
        otro = usuario_factory(rol="miembro")
        u = _solo(usuario_factory, editar=True)
        client.force_login(u)
        pagina = client.get(f"/proyectos/{p.pk}/").content.decode()
        assert 'name="estado"' in pagina and "disabled" in pagina
        datos = _post_del_detalle(client, p, descripcion="después", estado="esperando_respuesta",
                                  **{"equipo__lider": str(otro.pk)})
        r = client.post(f"/proyectos/{p.pk}/", datos)
        assert r.status_code in (200, 302), r.status_code
        p = Proyecto.objects.get(pk=p.pk)
        assert p.descripcion == "después"
        assert p.estado == "por_cotizar"
        assert not ProyectoAsignacion.objects.filter(proyecto=p, usuario=otro).exists()
        # Control: el mismo POST con las tres acciones sí mueve estado y equipo
        # (si no, lo de arriba pasaría por un POST mal armado).
        client.force_login(_solo(usuario_factory, editar=True, asignar=True, cambiar_estado=True))
        datos = _post_del_detalle(client, p, estado="esperando_respuesta",
                                  **{"equipo__lider": str(otro.pk)})
        assert client.post(f"/proyectos/{p.pk}/", datos).status_code in (200, 302)
        assert Proyecto.objects.get(pk=p.pk).estado == "esperando_respuesta"
        assert ProyectoAsignacion.objects.filter(proyecto=p, usuario=otro).exists()

    def test_chalan(self, usuario_factory, proyecto_factory):
        from apps.el_dictado.ejecutores.basicos import (
            actualizar_proyecto,
            asignar_usuario_proyecto,
            crear_proyecto,
        )
        from apps.el_dictado.ejecutores.cui_v1 import duplicar_proyecto

        from lib.dictado_catalogo import comandos_para

        p = proyecto_factory(estado="por_cotizar")

        def accion(**payload):
            return SimpleNamespace(payload=payload, entidad_tipo=None, entidad_id=None)

        def falla_por_permiso(fn, u, **payload):
            try:
                fn(accion(**payload), u)
            except ValueError as exc:
                return str(exc).startswith("No tienes permiso")
            return False

        solo_editar = _solo(usuario_factory, editar=True)
        for fn in (crear_proyecto, duplicar_proyecto, asignar_usuario_proyecto):
            assert falla_por_permiso(fn, solo_editar), fn.__name__
        assert falla_por_permiso(actualizar_proyecto, solo_editar, proyecto_slug=p.slug,
                                 estado="esperando_respuesta")
        # …pero sin `estado`, `editar` basta.
        actualizar_proyecto(accion(proyecto_slug=p.slug, descripcion="nueva"), solo_editar)
        tipos = {c["tipo"] for c in comandos_para(solo_editar)}
        assert "actualizar_proyecto" in tipos
        assert not tipos & {"crear_proyecto", "duplicar_proyecto", "asignar_usuario_proyecto"}

        cada_una = _solo(usuario_factory, crear=True, asignar=True, cambiar_estado=True)
        for fn in (crear_proyecto, duplicar_proyecto, asignar_usuario_proyecto):
            assert not falla_por_permiso(fn, cada_una), fn.__name__
        tipos = {c["tipo"] for c in comandos_para(cada_una)}
        assert {"crear_proyecto", "duplicar_proyecto", "asignar_usuario_proyecto"} <= tipos


def _post_del_detalle(client, proyecto, **cambios):
    """Lo que manda el autoguardado del detalle: el form tal como se pintó,
    con `cambios` encima."""
    import re

    html = client.get(f"/proyectos/{proyecto.pk}/").content.decode()
    form = html[html.index('id="form-proyecto"'):]
    form = form[:form.index("</form>")]
    datos = {}
    for m in re.finditer(r"<input[^>]*>", form):
        tag = m.group(0)
        nombre = re.search(r'name="([^"]+)"', tag)
        if not nombre or "disabled" in tag:
            continue
        tipo = (re.search(r'type="([^"]+)"', tag) or [None, "text"])[1]
        if tipo == "checkbox" and "checked" not in tag:
            continue
        valor = re.search(r'value="([^"]*)"', tag)
        datos[nombre.group(1)] = valor.group(1) if valor else ("on" if tipo == "checkbox" else "")
    for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', form, re.S):
        if "disabled" in m.group(0)[:m.group(0).index(">")]:
            continue
        sel = re.search(r'<option[^>]*value="([^"]*)"[^>]*selected', m.group(2))
        datos[m.group(1)] = sel.group(1) if sel else ""
    for m in re.finditer(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', form, re.S):
        datos[m.group(1)] = m.group(2)
    datos.update(cambios)
    return datos


# ═════════════════════════════════════════════════════════════════════════════
# 6. Contaduría: lo técnico se enseña al failsafe con `|es_super_admin`
# ═════════════════════════════════════════════════════════════════════════════

class TestContaduriaPorElFailsafe:
    """Las plantillas comparaban `user.rol == 'super_admin'`; ahora usan el
    filtro del failsafe. Mismo resultado para quien tiene el rol de verdad."""

    @pytest.mark.parametrize("ruta,marca", [
        ("/contaduria/", "+ Movimiento avanzado"),
        ("/contaduria/asientos/", "+ Avanzado"),
        ("/contaduria/cuentas/", ">Naturaleza<"),
        ("/contaduria/balance/", ">Tipo<"),
    ])
    def test_lo_ve_el_super_admin_y_no_el_contador(self, client, usuario_factory, ruta, marca):
        client.force_login(usuario_factory(rol="super_admin"))
        assert marca in client.get(ruta).content.decode()
        client.force_login(usuario_factory(rol="contador"))
        r = client.get(ruta)
        assert r.status_code == 200
        assert marca not in r.content.decode()

    def test_el_filtro_es_el_failsafe(self, usuario_factory):
        from cuentas.templatetags.permisos import filtro_es_super_admin

        for rol in ("super_admin", "dueno", "contador", "disenador", "miembro"):
            u = usuario_factory(rol=rol)
            assert filtro_es_super_admin(u) == permisos.es_super_admin(u) == (rol == "super_admin")
