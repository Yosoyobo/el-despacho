"""Sprint Pre-S2b.2 — re-arquitectura de ubicaciones.

Tests transversales (Taller + Gerencia + helpers nuevos): template tag puede,
context processor, middleware, redirects, dashboard espejo, perfil chalanes,
Sala de Juntas Taller.
"""

from __future__ import annotations

import pytest
from django.test import override_settings

pytestmark = pytest.mark.django_db


# ── 1) Template tag y context processor ─────────────────────────────────────


def test_filtro_puede_basico(usuario_factory):
    from django.template import Context, Template
    u = usuario_factory(rol="super_admin")
    tpl = Template('{% load permisos %}{% if user|puede:"cartera.ver" %}SI{% else %}NO{% endif %}')
    out = tpl.render(Context({"user": u}))
    assert out == "SI"


def test_filtro_puede_disenador_sin_cartera(usuario_factory):
    from django.template import Context, Template
    u = usuario_factory(rol="disenador")
    tpl = Template('{% load permisos %}{% if user|puede:"cartera.ver" %}SI{% else %}NO{% endif %}')
    assert tpl.render(Context({"user": u})) == "NO"


def test_filtro_puede_anonimo():
    from django.contrib.auth.models import AnonymousUser
    from django.template import Context, Template
    tpl = Template('{% load permisos %}{% if user|puede:"cartera.ver" %}SI{% else %}NO{% endif %}')
    assert tpl.render(Context({"user": AnonymousUser()})) == "NO"


def test_context_processor_permisos_modulos(client, usuario_factory):
    """Settings de prueba registran cuentas.context_processors.permisos_modulos."""

    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/perfil/notificaciones/")
    assert resp.status_code == 200
    # Verifica que el context processor inyecta `permisos_modulos`.
    assert "permisos_modulos" in resp.context
    assert resp.context["permisos_modulos"].get("cartera") is True


def test_context_processor_disenador_sin_cartera(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/")  # taller home
    assert resp.status_code == 200
    assert resp.context["permisos_modulos"].get("cartera") is False


# ── 2) Middleware RedirigirRolesOperativos ──────────────────────────────────

MIDDLEWARE_CON_REDIRECT = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "lib.middleware.RedirigirRolesOperativosMiddleware",
]


@override_settings(
    ROOT_URLCONF="tests.urls_gerencia",
    MIDDLEWARE=MIDDLEWARE_CON_REDIRECT,
    TALLER_URL="http://testserver-taller/",
)
def test_middleware_redirige_disenador_de_gerencia(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/directorio/")
    assert resp.status_code == 302
    assert resp["Location"].startswith("http://testserver-taller/")


@override_settings(
    ROOT_URLCONF="tests.urls_gerencia",
    MIDDLEWARE=MIDDLEWARE_CON_REDIRECT,
    TALLER_URL="http://testserver-taller/",
)
def test_middleware_redirige_contador_de_gerencia(client, usuario_factory):
    u = usuario_factory(rol="contador")
    client.force_login(u)
    resp = client.get("/directorio/")
    assert resp.status_code == 302
    assert resp["Location"].startswith("http://testserver-taller/")


@override_settings(
    ROOT_URLCONF="tests.urls_gerencia",
    MIDDLEWARE=MIDDLEWARE_CON_REDIRECT,
    TALLER_URL="http://testserver-taller/",
)
def test_middleware_no_toca_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/directorio/")
    assert resp.status_code == 200


@override_settings(
    ROOT_URLCONF="tests.urls_gerencia",
    MIDDLEWARE=MIDDLEWARE_CON_REDIRECT,
    TALLER_URL="http://testserver-taller/",
)
def test_middleware_no_toca_dueno(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get("/directorio/")
    assert resp.status_code == 200


@override_settings(
    ROOT_URLCONF="tests.urls_gerencia",
    MIDDLEWARE=MIDDLEWARE_CON_REDIRECT,
    TALLER_URL="http://testserver-taller/",
)
def test_middleware_no_redirige_anonimo(client):
    """Sin autenticación, el middleware no actúa (deja pasar al flujo normal de auth)."""
    resp = client.get("/directorio/")
    # No-auth → flujo normal de Django (302 a /sign-in, no a Taller).
    assert resp.status_code in (302, 200)
    if resp.status_code == 302:
        assert "sign-in" in resp["Location"] or "testserver-taller" not in resp["Location"]


@override_settings(
    ROOT_URLCONF="tests.urls_gerencia",
    MIDDLEWARE=MIDDLEWARE_CON_REDIRECT,
    TALLER_URL="http://testserver-taller/",
)
def test_middleware_no_toca_assets(client, usuario_factory):
    """Whitelist: /static/, /sign-in, /auth/, /ping no disparan redirect."""
    from lib.middleware import RedirigirRolesOperativosMiddleware as M
    # Test directo del helper.
    class _Req:
        path = "/sign-in"
        user = type("U", (), {"is_authenticated": True, "rol": "disenador"})()
    assert M._debe_redirigir(_Req()) is False
    _Req.path = "/static/css/x.css"
    assert M._debe_redirigir(_Req()) is False
    _Req.path = "/auth/google/callback"
    assert M._debe_redirigir(_Req()) is False
    _Req.path = "/ping"
    assert M._debe_redirigir(_Req()) is False


# ── 3) Sala de Juntas en Taller ─────────────────────────────────────────────


def test_sala_juntas_taller_super_admin(client, usuario_factory):
    """S2b.4: admin ve catálogo de KPIs reales + sugerencias del Chalán.

    Los placeholders "Pendiente sprint S2b.4" desaparecieron cuando se
    entregó el catálogo. Ahora super_admin ve KPIs reales como
    'Proyectos activos', 'Buzón sin responder', etc.
    """
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # S-LC-Feedback-V2: header renombrado "Sala de Juntas" → "Dashboard".
    assert "Dashboard" in body
    # S-Dashboard-Render: KPI hero + zona compacta + chatbot + Kanban.
    assert "Proyectos activos" in body
    assert "Tu tablero" in body
    assert "Editar tablero" in body
    # Chatbot (El Dictado) + Kanban de 4 columnas activas.
    assert "Procesar" in body
    assert "Por cotizar" in body


def test_sala_juntas_taller_contador(client, usuario_factory):
    """S2b.4: contador ve subset propio (cartera + buzón vista parcial)."""
    u = usuario_factory(rol="contador")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # S-Dashboard-Render: el contador ve KPIs financieros de la zona compacta.
    assert "Cuentas por cobrar" in body
    # No le aparecen KPIs admin-only
    assert "Tareas vencidas del equipo" not in body


def test_sala_juntas_taller_disenador(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # KPIs del catálogo aplicables al diseñador.
    assert "Mis tareas" in body or "Mis recados" in body
    # No le aparecen KPIs admin-only
    assert "Buzón sin responder" not in body


# ── 4) Dashboard ejecutivo espejo en Gerencia ───────────────────────────────


@pytest.fixture
def _urls_gerencia(settings):
    settings.ROOT_URLCONF = "tests.urls_gerencia"


def test_dashboard_gerencia_espejo(client, usuario_factory, _urls_gerencia):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Dashboard ejecutivo" in body
    # KPIs hero del dashboard (S-Charts reemplazó placeholders Pipeline
    # con métricas reales).
    assert "Usuarios activos" in body
    # CTA a Taller.
    # S-LC-Feedback-V2: link renombrado en Gerencia.
    assert "Ver Dashboard completa en El Taller" in body or "Ver Dashboard" in body


def test_dashboard_gerencia_no_tiene_slot_chalan(client, usuario_factory, _urls_gerencia):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/")
    body = resp.content.decode()
    # El slot del Chalán es exclusivo del Taller ahora.
    assert "Cuéntale al Chalán" not in body


# ── 5) Catálogo: redirect de Gerencia + view en Taller ──────────────────────


def test_catalogo_redirect_de_gerencia(client, usuario_factory, _urls_gerencia):
    """En tests/urls_gerencia.py NO hay /catalogo/ — el path real es solo en
    Taller. Verifico que la URLconf de Gerencia ya no lo tiene."""
    from django.urls import NoReverseMatch, reverse
    with pytest.raises(NoReverseMatch):
        reverse("catalogo-lista")


def test_catalogo_taller_disenador_sin_precios(client, usuario_factory):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Diseño")
    Servicio.objects.create(nombre="Logo único", precio_base="1500.00", categoria=cat)
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/catalogo/")
    assert resp.status_code == 200
    assert b"Logo" in resp.content
    assert b"1500" not in resp.content


# ── 6) Perfil personal /perfil/chalanes/ ────────────────────────────────────


def test_perfil_chalanes_taller_carga(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/perfil/chalanes/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Chalanes" in body
    # Estaciones del Cuadro (seed Pre-S2b.1).
    assert "cotizaciones" in body


def test_perfil_chalanes_disenador_oculta_estaciones_admin(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/perfil/chalanes/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # ocr_recibo NO debe aparecer (oculto a diseñadores).
    assert "ocr_recibo" not in body


def test_perfil_chalanes_guarda_override(client, usuario_factory):
    from chalanes.models import ChalanAsignado
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.post("/perfil/chalanes/guardar", {
        "estacion": "cotizaciones", "proveedor": "deepseek",
    })
    assert resp.status_code == 302
    assert ChalanAsignado.objects.filter(usuario=u, estacion="cotizaciones").exists()


def test_perfil_chalanes_borra_override_con_vacio(client, usuario_factory):
    from chalanes.models import ChalanAsignado
    u = usuario_factory(rol="dueno")
    ChalanAsignado.objects.create(usuario=u, estacion="cotizaciones", proveedor="openai")
    client.force_login(u)
    client.post("/perfil/chalanes/guardar", {"estacion": "cotizaciones", "proveedor": ""})
    assert not ChalanAsignado.objects.filter(usuario=u, estacion="cotizaciones").exists()


def test_perfil_chalanes_vision_rechaza_chino(client, usuario_factory):
    """ocr_recibo requiere_vision=True; Chino no soporta visión → error 302 sin guardar."""
    from chalanes.models import ChalanAsignado
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/perfil/chalanes/guardar", {
        "estacion": "ocr_recibo", "proveedor": "deepseek",
    })
    assert resp.status_code == 302
    assert not ChalanAsignado.objects.filter(usuario=u, estacion="ocr_recibo", proveedor="deepseek").exists()


# ── 7) Sidebar dinámica ─────────────────────────────────────────────────────


def test_sidebar_taller_super_admin_ve_todo(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/")
    body = resp.content.decode()
    assert "Clientes" in body
    assert "Proyectos" in body
    assert "Buzón" in body
    assert "Productos" in body
    assert "Chalanes" in body


def test_sidebar_taller_disenador_sin_cartera(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/")
    body = resp.content.decode()
    # Diseñador no tiene cartera.ver
    assert ">Clientes<" not in body  # ojo: en sidebar, no en otros lados


def test_sidebar_respeta_toggle_individual(client, usuario_factory):
    """Si super_admin desactiva `buzon.ver` para un usuario, el item desaparece."""
    from cuentas.models.permiso_usuario import PermisoUsuario
    u = usuario_factory(rol="dueno")
    PermisoUsuario.objects.filter(usuario=u, modulo="buzon").update(activo=False)
    client.force_login(u)
    resp = client.get("/")
    body = resp.content.decode()
    assert ">Buzón<" not in body


# ── 8) Rename "Probar Analistas" → "Probar Chalanes" ────────────────────────


def test_label_probar_chalanes_en_ajustes(client, usuario_factory, _urls_gerencia):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/ajustes/")
    body = resp.content.decode()
    assert "Probar Chalanes" in body
    assert "Probar Analistas" not in body


# ── 9) Buzón unificado ──────────────────────────────────────────────────────


def test_buzon_admin_ve_todos(client, usuario_factory):
    from buzon.models import MensajeBuzon
    autor = usuario_factory(rol="disenador")
    admin = usuario_factory(rol="super_admin")
    MensajeBuzon.objects.create(autor=autor, tipo="sugerencia", asunto="X", cuerpo="hola "*10)
    client.force_login(admin)
    resp = client.get("/buzon/")
    assert resp.status_code == 200
    # Admin ve mensajes de otros autores.
    assert b"X" in resp.content


def test_buzon_clientes_proximamente(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/buzon/clientes/")
    assert resp.status_code == 200
    assert b"Buz" in resp.content
