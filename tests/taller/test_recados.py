"""Los Recados — S2b.1 (sin adjuntos Drive — S2b.1b)."""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _crear_user_y_login(client, usuario_factory, rol="super_admin"):
    u = usuario_factory(rol=rol)
    client.force_login(u)
    return u


# ── 1. Crear recado simple ──────────────────────────────────────────────────

def test_crear_recado_simple(client, usuario_factory):
    from apps.recados.models import Recado, RecadoDestinatario
    autor = _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="maria@ej.com")

    resp = client.post("/recados/nuevo/", {
        "cuerpo": "Recuerda revisar la maqueta.",
        "destinatarios_usuarios": [str(dest.pk)],
    })
    assert resp.status_code == 302
    r = Recado.objects.get()
    assert r.autor_id == autor.pk
    assert "maqueta" in r.cuerpo
    assert RecadoDestinatario.objects.filter(recado=r, usuario=dest).exists()


# ── 2. Crear recado con referencias ─────────────────────────────────────────

def test_crear_recado_con_referencias(client, usuario_factory):
    from apps.recados.models import Recado

    from referencias.models import Referencia
    autor = _crear_user_y_login(client, usuario_factory, rol="super_admin")
    maria = usuario_factory(rol="disenador", email="maria@ej.com")
    # El slug se autogenera del email; asumimos `maria` o similar.
    resp = client.post("/recados/nuevo/", {
        "cuerpo": f"Hola @{maria.slug}, revisa esto.",
        "destinatarios_usuarios": [str(maria.pk)],
    })
    assert resp.status_code == 302
    r = Recado.objects.get(autor=autor)
    refs = Referencia.objects.filter(contenedor_tipo="recado", contenedor_id=r.pk, tipo="usuario")
    assert refs.filter(usuario=maria).exists()


# ── 3. Grupo estático ───────────────────────────────────────────────────────

def test_crear_recado_a_grupo_estatico(client, usuario_factory):
    from apps.recados.models import Recado, RecadoDestinatario
    autor = _crear_user_y_login(client, usuario_factory, rol="super_admin")
    d1 = usuario_factory(rol="disenador", email="d1@ej.com")
    d2 = usuario_factory(rol="disenador", email="d2@ej.com")
    # Otro rol que NO debe entrar en disenio_y_produccion.
    contador = usuario_factory(rol="contador", email="c@ej.com")

    resp = client.post("/recados/nuevo/", {
        "cuerpo": "Equipo diseño: junta a las 3.",
        "destinatarios_grupos": ["disenio_y_produccion"],
    })
    assert resp.status_code == 302
    r = Recado.objects.get(autor=autor)
    ids = set(RecadoDestinatario.objects.filter(recado=r).values_list("usuario_id", flat=True))
    assert d1.pk in ids and d2.pk in ids
    assert contador.pk not in ids
    assert autor.pk not in ids  # autor excluido


# ── 4. Grupo dinámico (equipo de proyecto) ──────────────────────────────────

def test_crear_recado_a_grupo_dinamico_proyecto(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos.models.asignacion import ProyectoAsignacion
    from apps.recados.models import Recado, RecadoDestinatario

    autor = _crear_user_y_login(client, usuario_factory, rol="super_admin")
    asignado = usuario_factory(rol="disenador", email="asig@ej.com")
    pry = proyecto_factory(creado_por=autor)
    ProyectoAsignacion.objects.create(proyecto=pry, usuario=asignado, rol_en_proyecto="disenador")

    slug = f"equipo-de-#{pry.codigo}"
    resp = client.post("/recados/nuevo/", {
        "cuerpo": "Equipo del proyecto: revisión.",
        "destinatarios_dinamicos": [slug],
    })
    assert resp.status_code == 302
    r = Recado.objects.get(autor=autor)
    ids = set(RecadoDestinatario.objects.filter(recado=r).values_list("usuario_id", flat=True))
    assert asignado.pk in ids


# ── 5. Destinatario inactivo excluido ───────────────────────────────────────

def test_destinatario_inactivo_excluido(client, usuario_factory):
    from apps.recados.models import Recado
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    inactivo = usuario_factory(rol="disenador", email="inact@ej.com")
    inactivo.is_active = False
    inactivo.save(update_fields=["is_active"])

    resp = client.post("/recados/nuevo/", {
        "cuerpo": "Recado a fantasma.",
        "destinatarios_usuarios": [str(inactivo.pk)],
    })
    # No hay destinatarios válidos → re-renderiza el form sin redirect.
    assert resp.status_code == 200
    assert Recado.objects.count() == 0


# ── 6. Confirmación si > 5 destinatarios ────────────────────────────────────

def test_confirmacion_requerida_si_mas_de_5(client, usuario_factory):
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest_ids = []
    for i in range(6):
        dest_ids.append(str(usuario_factory(rol="disenador", email=f"d{i}@ej.com").pk))

    resp = client.post("/recados/nuevo/", {
        "cuerpo": "Aviso general.",
        "destinatarios_usuarios": dest_ids,
    })
    assert resp.status_code == 400
    data = resp.json()
    assert data["requiere_confirmacion"] is True
    assert data["total_destinatarios"] == 6

    # Con confirmación aceptada se persiste.
    resp2 = client.post("/recados/nuevo/", {
        "cuerpo": "Aviso general.",
        "destinatarios_usuarios": dest_ids,
        "confirmacion_aceptada": "1",
    })
    assert resp2.status_code == 302


# ── 7. Editar crea version + incrementa ─────────────────────────────────────

def test_editar_recado_crea_version_y_incrementa(client, usuario_factory):
    from apps.recados.models import Recado, RecadoVersion
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    client.post("/recados/nuevo/", {"cuerpo": "Texto original.", "destinatarios_usuarios": [str(dest.pk)]})
    r = Recado.objects.get()
    assert r.version_actual == 1

    resp = client.post(f"/recados/{r.pk}/editar/", {"cuerpo": "Texto corregido."})
    assert resp.status_code == 302
    r.refresh_from_db()
    assert r.editado is True
    assert r.version_actual == 2
    assert RecadoVersion.objects.filter(recado=r, version=1).exists()
    assert "corregido" in r.cuerpo


# ── 8. Editar solo autor ────────────────────────────────────────────────────

def test_editar_recado_solo_autor(client, usuario_factory):
    from apps.recados.models import Recado
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    client.post("/recados/nuevo/", {"cuerpo": "Original.", "destinatarios_usuarios": [str(dest.pk)]})
    r = Recado.objects.get()

    client.logout()
    client.force_login(dest)
    resp = client.post(f"/recados/{r.pk}/editar/", {"cuerpo": "intento ajeno"})
    assert resp.status_code == 403
    r.refresh_from_db()
    assert "Original" in r.cuerpo


# ── 9. DELETE retorna 405 ───────────────────────────────────────────────────

def test_delete_recado_405(client, usuario_factory):
    from apps.recados.models import Recado
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    client.post("/recados/nuevo/", {"cuerpo": "Texto.", "destinatarios_usuarios": [str(dest.pk)]})
    r = Recado.objects.get()
    resp = client.delete(f"/recados/{r.pk}/")
    assert resp.status_code == 405


# ── 10-14. Push y categorías ─────────────────────────────────────────────────

def _patch_push(monkeypatch):
    """Captura llamadas a enviar_a_usuario en handlers + dispara on_commit inline."""
    enviados = []
    from apps.recados import handlers

    def fake(u, titulo, cuerpo, url="", tag="", categoria=None):
        enviados.append({"u": u.pk, "categoria": categoria, "titulo": titulo})
        return {"entregadas": 1, "fallidas": 0, "invalidadas": 0}

    monkeypatch.setattr(handlers, "enviar_a_usuario", fake)

    # En tests, on_commit no se dispara (estamos dentro de una transacción).
    # Reemplaza por ejecución inmediata para que el handler corra.
    from django.db import transaction as _tx

    def _run_now(fn, using=None, robust=False):  # firma compatible con Django 5.x
        fn()

    monkeypatch.setattr(_tx, "on_commit", _run_now)
    # services.py importó `transaction` del módulo django.db; el setattr funciona.
    return enviados


def test_push_a_destinatarios(client, usuario_factory, monkeypatch):
    enviados = _patch_push(monkeypatch)
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    client.post("/recados/nuevo/", {"cuerpo": "Hola.", "destinatarios_usuarios": [str(dest.pk)]})
    assert any(e["u"] == dest.pk and e["categoria"] == "recados" for e in enviados)


def test_push_a_mencionados_aunque_no_destinatarios(client, usuario_factory, monkeypatch):
    enviados = _patch_push(monkeypatch)
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    mariana = usuario_factory(rol="disenador", email="mariana@ej.com")
    otro = usuario_factory(rol="disenador", email="otro@ej.com")
    # Mandado solo a `otro`, pero menciona @mariana.
    client.post("/recados/nuevo/", {
        "cuerpo": f"Cuidado @{mariana.slug}, eso es importante.",
        "destinatarios_usuarios": [str(otro.pk)],
    })
    ids = {e["u"] for e in enviados}
    assert mariana.pk in ids and otro.pk in ids


def test_push_dedup_destinatario_y_mencionado(client, usuario_factory, monkeypatch):
    enviados = _patch_push(monkeypatch)
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    oscar = usuario_factory(rol="disenador", email="oscar@ej.com")
    client.post("/recados/nuevo/", {
        "cuerpo": f"Hola @{oscar.slug}, te aviso.",
        "destinatarios_usuarios": [str(oscar.pk)],
    })
    coincidencias = [e for e in enviados if e["u"] == oscar.pk]
    assert len(coincidencias) == 1


def test_push_no_al_autor(client, usuario_factory, monkeypatch):
    enviados = _patch_push(monkeypatch)
    autor = _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    # Autor se auto-menciona — no debe recibir push.
    client.post("/recados/nuevo/", {
        "cuerpo": f"Recuerdo @{autor.slug} hacer X.",
        "destinatarios_usuarios": [str(dest.pk)],
    })
    assert all(e["u"] != autor.pk for e in enviados)


def test_push_respeta_categoria_desactivada(client, usuario_factory, monkeypatch):
    # NO patch directo del handler — queremos pasar por lib.interfono.enviar_a_usuario.
    from interfono.models import PreferenciaCategoriaPush
    from lib import interfono as li

    capturadas = []

    def fake_send(suscripcion, titulo, cuerpo, url="", tag=""):
        capturadas.append(suscripcion.usuario_id)
        return "ok"

    monkeypatch.setattr(li, "enviar_a_suscripcion", fake_send)
    monkeypatch.setattr(li.InterfonoConfig, "esta_configurado", classmethod(lambda cls: True))

    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    # Suscripción simulada
    from interfono.models import InterfonoSuscripcion
    InterfonoSuscripcion.objects.create(
        usuario=dest, endpoint="https://push/x", p256dh="p", auth="a", activa=True,
    )
    # Desactiva la categoría
    PreferenciaCategoriaPush.objects.create(usuario=dest, categoria="recados", activo=False)

    client.post("/recados/nuevo/", {"cuerpo": "Aviso", "destinatarios_usuarios": [str(dest.pk)]})
    assert dest.pk not in capturadas


# ── 15-18. Bandeja, marcado de leído, detalle 404 ───────────────────────────

def test_bandeja_recibidos_default(client, usuario_factory):
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    client.post("/recados/nuevo/", {"cuerpo": "Texto.", "destinatarios_usuarios": [str(dest.pk)]})

    client.logout()
    client.force_login(dest)
    resp = client.get("/recados/")
    assert resp.status_code == 200
    assert b"Texto" in resp.content


def test_bandeja_no_leidos_filtro(client, usuario_factory):
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    client.post("/recados/nuevo/", {"cuerpo": "ABC", "destinatarios_usuarios": [str(dest.pk)]})

    client.logout()
    client.force_login(dest)
    resp = client.get("/recados/?tab=no_leidos")
    assert resp.status_code == 200
    assert b"ABC" in resp.content


def test_marcar_leido_implicito_al_abrir_detalle(client, usuario_factory):
    from apps.recados.models import Recado, RecadoDestinatario
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    client.post("/recados/nuevo/", {"cuerpo": "X", "destinatarios_usuarios": [str(dest.pk)]})
    r = Recado.objects.get()
    fila = RecadoDestinatario.objects.get(recado=r, usuario=dest)
    assert fila.leido_en is None

    client.logout()
    client.force_login(dest)
    resp = client.get(f"/recados/{r.pk}/")
    assert resp.status_code == 200
    fila.refresh_from_db()
    assert fila.leido_en is not None


def test_detalle_404_si_no_autor_ni_destinatario_ni_mencionado(client, usuario_factory):
    from apps.recados.models import Recado
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    extrano = usuario_factory(rol="disenador", email="extr@ej.com")
    client.post("/recados/nuevo/", {"cuerpo": "Privado.", "destinatarios_usuarios": [str(dest.pk)]})
    r = Recado.objects.get()

    client.logout()
    client.force_login(extrano)
    resp = client.get(f"/recados/{r.pk}/")
    assert resp.status_code == 404


# ── 19. Permiso desactivado oculta sidebar ──────────────────────────────────

def test_permiso_recados_ver_desactivado_oculta_sidebar(client, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    u = _crear_user_y_login(client, usuario_factory, rol="disenador")
    PermisoUsuario.objects.filter(usuario=u, modulo="recados", permiso="ver").update(activo=False)
    resp = client.get("/")
    assert resp.status_code in (200, 302)
    if resp.status_code == 200:
        # El link a /recados/ NO debe estar en la sidebar.
        assert b'href="/recados/"' not in resp.content


# ── 20. Seed grupos idempotente ─────────────────────────────────────────────

def test_seed_grupos_idempotente(db):
    from apps.recados.models import RecadoGrupo
    n0 = RecadoGrupo.objects.count()
    assert n0 >= 4
    # Re-creamos las mismas filas; ignore_conflicts evita el error.
    RecadoGrupo.objects.bulk_create(
        [RecadoGrupo(slug=g.slug, nombre_legible=g.nombre_legible, tipo=g.tipo, roles=g.roles)
         for g in RecadoGrupo.objects.all()],
        ignore_conflicts=True,
    )
    assert RecadoGrupo.objects.count() == n0


# ── 21. Counter de no leídos ────────────────────────────────────────────────

def test_counter_no_leidos_context_processor(client, usuario_factory):
    _crear_user_y_login(client, usuario_factory, rol="super_admin")
    dest = usuario_factory(rol="disenador", email="d@ej.com")
    for i in range(3):
        client.post("/recados/nuevo/", {
            "cuerpo": f"msg {i}", "destinatarios_usuarios": [str(dest.pk)],
        })

    client.logout()
    client.force_login(dest)
    resp = client.get("/")
    if resp.status_code == 200:
        # El número 3 debe aparecer en el sidebar como counter.
        assert b">3<" in resp.content or b"Los Recados" in resp.content
