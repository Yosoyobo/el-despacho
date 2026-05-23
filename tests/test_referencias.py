"""Tests del Sistema de Referencias (@/#/$) — Pre-S2b.1."""

from __future__ import annotations

import pytest

from referencias.parser import extraer_tokens

pytestmark = pytest.mark.django_db


# ── Slugs ───────────────────────────────────────────────────────────────────

def test_slug_usuario_desde_email(usuario_factory):
    u = usuario_factory(email="oscar.bautista@ejemplo.com")
    assert u.slug == "oscar-bautista"


def test_slug_usuario_desambigua(usuario_factory):
    u1 = usuario_factory(email="oscar@a.com")
    u2 = usuario_factory(email="oscar@b.com")
    u3 = usuario_factory(email="oscar@c.com")
    assert u1.slug == "oscar"
    assert u2.slug == "oscar-2"
    assert u3.slug == "oscar-3"


def test_slug_cliente_desde_razon_social(cliente_factory):
    from lib.slug import _normalizar
    assert _normalizar("Heladería La Diferencia, S.A. de C.V.") == "heladeria-la-diferencia-s-a-de-c-v"
    c = cliente_factory(razon_social="Café Niño, S.A.")
    assert c.slug == "cafe-nino-s-a"


def test_slug_proyecto_desde_codigo(proyecto_factory):
    p = proyecto_factory()
    assert p.slug == p.codigo.lower()
    # S-LC-Feedback-V2: códigos ahora correlativos LC-NNNN.
    assert p.slug.startswith("lc-")


# ── Parser ──────────────────────────────────────────────────────────────────

def test_parser_detecta_basicos():
    tokens = extraer_tokens("Hola @oscar, revisa #pry-001 del cliente $heladeria")
    sigs = [t.sigil for t in tokens]
    slugs = [t.slug for t in tokens]
    assert sigs == ["@", "#", "$"]
    assert slugs == ["oscar", "pry-001", "heladeria"]


def test_parser_ignora_email():
    tokens = extraer_tokens("Escribe a oscar@bautista.mx por favor")
    assert tokens == []


def test_parser_ignora_dolar_numero():
    tokens = extraer_tokens("El proyecto cuesta $50 y $100 dólares")
    assert tokens == []


def test_parser_ignora_hashtag_dentro_de_palabra():
    tokens = extraer_tokens("La url foo#bar no es referencia")
    assert tokens == []


def test_parser_acepta_al_inicio_de_linea():
    tokens = extraer_tokens("@oscar reporta\n#pry-001 listo")
    assert len(tokens) == 2


# ── Modelo Referencia + CHECK constraint ───────────────────────────────────

def test_referencia_check_constraint_tipo_usuario(usuario_factory, proyecto_factory):
    from django.db import IntegrityError, transaction

    from referencias.models import Referencia
    u = usuario_factory()
    p = proyecto_factory()
    # tipo=usuario con proyecto poblado debe violar
    with pytest.raises(IntegrityError), transaction.atomic():
        Referencia.objects.create(
            contenedor_tipo="t", contenedor_id=1,
            tipo="usuario", usuario=u, proyecto_id=p.pk,
            token_original="@x", posicion_inicio=0, posicion_fin=1,
        )


def test_referencia_valida_tipo_usuario(usuario_factory):
    from referencias.models import Referencia
    u = usuario_factory()
    r = Referencia.objects.create(
        contenedor_tipo="recado", contenedor_id=42,
        tipo="usuario", usuario=u,
        token_original=f"@{u.slug}", posicion_inicio=0, posicion_fin=len(u.slug)+1,
    )
    assert r.entidad == u


# ── Services: sincronizar_referencias ──────────────────────────────────────

def test_sincronizar_persiste_solo_resueltas(usuario_factory):
    from referencias.models import Referencia
    from referencias.services import sincronizar_referencias

    u = usuario_factory(email="oscar@a.com")  # slug='oscar'
    texto = "Hola @oscar y @noexiste"
    out = sincronizar_referencias(
        texto=texto, contenedor_tipo="recado", contenedor_id=1, autor=None,
    )
    refs = Referencia.objects.filter(contenedor_tipo="recado", contenedor_id=1)
    assert refs.count() == 1
    assert refs.first().usuario_id == u.pk
    assert len(out["tokens"]) == 2  # parser detecta ambos
    assert len(out["creadas"]) == 1


def test_sincronizar_reemplaza_referencias_previas(usuario_factory):
    from referencias.models import Referencia
    from referencias.services import sincronizar_referencias

    u1 = usuario_factory(email="a@x.com")
    u2 = usuario_factory(email="b@x.com")
    sincronizar_referencias(texto=f"@{u1.slug}", contenedor_tipo="r", contenedor_id=1)
    sincronizar_referencias(texto=f"@{u2.slug}", contenedor_tipo="r", contenedor_id=1)
    refs = list(Referencia.objects.filter(contenedor_id=1))
    assert len(refs) == 1
    assert refs[0].usuario_id == u2.pk


def test_sincronizar_dedup_menciones_y_excluye_autor(usuario_factory):
    from referencias.services import sincronizar_referencias

    autor = usuario_factory(email="autor@x.com")
    mencionado = usuario_factory(email="men@x.com")
    out = sincronizar_referencias(
        texto=f"@{autor.slug} @{mencionado.slug} @{mencionado.slug}",
        contenedor_tipo="r", contenedor_id=99, autor=autor,
    )
    # Autor no se notifica a sí mismo; mencionado solo una vez
    assert out["usuarios_mencionados"] == [mencionado.pk]


# ── Filtro renderizar_referencias ───────────────────────────────────────────

def test_filtro_render_chip_activo(usuario_factory):
    """S-LC-Feedback-V4: el chip renderizado muestra el nombre legible, no el slug.
    El slug viaja en data-ref-slug para que el JS de autocomplete lo siga viendo."""
    from referencias.templatetags.referencias import renderizar_referencias
    u = usuario_factory(email="oscar@x.com")
    out = str(renderizar_referencias(f"Hola @{u.slug} pásale"))
    assert "text-brand-600" in out
    assert 'href="/directorio/' in out
    # El slug ya no es el visible, ahora va en data-ref-slug.
    assert f'data-ref-slug="{u.slug}"' in out


def test_filtro_render_chip_roto():
    from referencias.templatetags.referencias import renderizar_referencias
    out = str(renderizar_referencias("Hola @inexistente"))
    assert "line-through" in out
    assert "@inexistente" in out


def test_filtro_escapa_html():
    from referencias.templatetags.referencias import renderizar_referencias
    out = str(renderizar_referencias("texto <script>alert(1)</script>"))
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


# ── Autocomplete endpoints ──────────────────────────────────────────────────


@pytest.fixture
def _urls_gerencia(settings):
    settings.ROOT_URLCONF = "tests.urls_gerencia"


def test_autocomplete_usuarios_prefijo(client, usuario_factory, _urls_gerencia):
    usuario_factory(email="oscar@a.com", rol="dueno")
    usuario_factory(email="otro@a.com", rol="dueno")
    auth = usuario_factory(email="admin@a.com", rol="super_admin")
    client.force_login(auth)
    r = client.get("/api/autocomplete/usuarios?q=osc")
    assert r.status_code == 200
    data = r.json()
    slugs = [x["slug"] for x in data["resultados"]]
    assert "oscar" in slugs
    assert "otro" not in slugs


def test_autocomplete_clientes_disenador_silencioso(client, usuario_factory, cliente_factory, _urls_gerencia):
    cliente_factory(razon_social="Heladería Foo")
    d = usuario_factory(rol="disenador")
    client.force_login(d)
    r = client.get("/api/autocomplete/clientes?q=hela")
    assert r.status_code == 200
    assert r.json() == {"resultados": []}


def test_autocomplete_clientes_admin_ve(client, usuario_factory, cliente_factory, _urls_gerencia):
    cliente_factory(razon_social="Heladería Foo")
    a = usuario_factory(rol="super_admin")
    client.force_login(a)
    r = client.get("/api/autocomplete/clientes?q=hela")
    assert r.status_code == 200
    assert len(r.json()["resultados"]) == 1


# ── Autocomplete sin prefijo (hotfix UX Slack-style) ────────────────────────


def test_autocomplete_usuarios_sin_prefijo_retorna_top_8_alfabetico(
    client, usuario_factory, _urls_gerencia
):
    """`@` sin prefijo → top 8 usuarios activos ordenados por slug."""
    for letra in "bdacefghij":  # 10 emails desordenados
        usuario_factory(email=f"{letra}@a.com", rol="dueno")
    auth = usuario_factory(email="admin@a.com", rol="super_admin")
    client.force_login(auth)
    r = client.get("/api/autocomplete/usuarios?q=")
    assert r.status_code == 200
    slugs = [x["slug"] for x in r.json()["resultados"]]
    assert len(slugs) == 8
    assert slugs == sorted(slugs), "deben venir alfabéticos por slug"


def test_autocomplete_usuarios_sin_prefijo_excluye_inactivos(
    client, usuario_factory, _urls_gerencia
):
    """Permiso de inactividad preservado con q vacío."""
    u_inactivo = usuario_factory(email="zzz@a.com", rol="dueno")
    u_inactivo.is_active = False
    u_inactivo.save()
    auth = usuario_factory(email="admin@a.com", rol="super_admin")
    client.force_login(auth)
    r = client.get("/api/autocomplete/usuarios?q=")
    slugs = {x["slug"] for x in r.json()["resultados"]}
    assert "zzz" not in slugs


def test_autocomplete_proyectos_sin_prefijo_retorna_top_8(
    client, usuario_factory, proyecto_factory, _urls_gerencia
):
    """`#` sin prefijo → top 8 proyectos alfabéticos."""
    for i in range(10):
        proyecto_factory(nombre=f"Proyecto {i:02d}")
    auth = usuario_factory(rol="super_admin")
    client.force_login(auth)
    r = client.get("/api/autocomplete/proyectos?q=")
    assert r.status_code == 200
    resultados = r.json()["resultados"]
    assert len(resultados) == 8
    slugs = [x["slug"] for x in resultados]
    assert slugs == sorted(slugs)


def test_autocomplete_proyectos_disenador_sin_prefijo_solo_asignados(
    client, usuario_factory, proyecto_factory, _urls_gerencia
):
    """Permiso de diseñador (solo proyectos asignados) preservado con q vacío."""
    from apps.los_proyectos.models import ProyectoAsignacion

    d = usuario_factory(rol="disenador")
    asignado = proyecto_factory(nombre="Mío")
    proyecto_factory(nombre="Ajeno")  # no asignado a d
    ProyectoAsignacion.objects.create(proyecto=asignado, usuario=d, rol_en_proyecto="disenador")
    client.force_login(d)
    r = client.get("/api/autocomplete/proyectos?q=")
    slugs = [x["slug"] for x in r.json()["resultados"]]
    assert asignado.slug in slugs
    assert len(slugs) == 1  # sólo el asignado


def test_autocomplete_clientes_sin_prefijo_retorna_top_8(
    client, usuario_factory, cliente_factory, _urls_gerencia
):
    """`$` sin prefijo → top 8 clientes activos alfabéticos."""
    for i in range(10):
        cliente_factory(razon_social=f"Cliente {chr(ord('a') + i)}")
    auth = usuario_factory(rol="super_admin")
    client.force_login(auth)
    r = client.get("/api/autocomplete/clientes?q=")
    assert r.status_code == 200
    resultados = r.json()["resultados"]
    assert len(resultados) == 8
    slugs = [x["slug"] for x in resultados]
    assert slugs == sorted(slugs)


def test_autocomplete_clientes_disenador_sin_prefijo_sigue_vacio(
    client, usuario_factory, cliente_factory, _urls_gerencia
):
    """Permiso de diseñador preservado con q vacío — silencioso."""
    cliente_factory(razon_social="Heladería Foo")
    d = usuario_factory(rol="disenador")
    client.force_login(d)
    r = client.get("/api/autocomplete/clientes?q=")
    assert r.status_code == 200
    assert r.json() == {"resultados": []}


def test_autocomplete_q_inexistente_devuelve_vacio(
    client, usuario_factory, _urls_gerencia
):
    """Regresión: `q=xyz` sin matches sigue retornando lista vacía."""
    usuario_factory(email="oscar@a.com", rol="dueno")
    auth = usuario_factory(email="admin@a.com", rol="super_admin")
    client.force_login(auth)
    r = client.get("/api/autocomplete/usuarios?q=xyz")
    assert r.status_code == 200
    assert r.json() == {"resultados": []}
