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
    assert p.slug.startswith("pry-")


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
    from referencias.templatetags.referencias import renderizar_referencias
    u = usuario_factory(email="oscar@x.com")
    out = str(renderizar_referencias(f"Hola @{u.slug} pásale"))
    assert "text-brand-600" in out
    assert f"@{u.slug}" in out
    assert 'href="/directorio/' in out


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
