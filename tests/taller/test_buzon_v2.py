"""S-LC-Buzon-V2: estado_manual (#3), archivar→leído, marcar todo, filtros,
acción automática de estado, tipo configurable."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _msg(autor, **kw):
    from buzon.models import MensajeBuzon
    kw.setdefault("tipo", "otro")
    kw.setdefault("asunto", "Asunto")
    kw.setdefault("cuerpo", "Cuerpo suficientemente largo.")
    return MensajeBuzon.objects.create(autor=autor, **kw)


def test_abrir_nuevo_autoavanza_a_leido(client, usuario_factory):
    from buzon.models import MensajeBuzon
    admin = usuario_factory(rol="super_admin")
    m = _msg(admin, estado="nuevo")
    client.force_login(admin)
    client.get(f"/buzon/{m.pk}/")
    assert MensajeBuzon.objects.get(pk=m.pk).estado == "leido"


def test_nuevo_manual_no_se_autoavanza(client, usuario_factory):
    """#3: si un admin fija el estado a 'nuevo' a mano, abrir el mensaje NO lo
    vuelve a 'leido'."""
    from buzon.models import MensajeBuzon
    admin = usuario_factory(rol="super_admin")
    m = _msg(admin, estado="leido")
    client.force_login(admin)
    # Cambio explícito a 'nuevo' vía acción masiva → estado_manual=True.
    client.post("/buzon/masivo", data={"ids": [m.pk], "accion": "estado_nuevo"})
    m.refresh_from_db()
    assert m.estado == "nuevo" and m.estado_manual is True
    # Abrir no lo auto-avanza.
    client.get(f"/buzon/{m.pk}/")
    assert MensajeBuzon.objects.get(pk=m.pk).estado == "nuevo"


def test_archivar_marca_leido(client, usuario_factory):
    from buzon.models import LecturaBuzon
    admin = usuario_factory(rol="super_admin")
    m = _msg(admin, estado="nuevo")
    client.force_login(admin)
    client.post("/buzon/masivo", data={"ids": [m.pk], "accion": "estado_archivado"})
    assert LecturaBuzon.objects.filter(usuario=admin, mensaje=m).exists()


def test_marcar_todo_leido(client, usuario_factory):
    from buzon.models import LecturaBuzon
    u = usuario_factory(rol="disenador")
    m1 = _msg(u)
    m2 = _msg(u)
    client.force_login(u)
    client.post("/buzon/masivo", data={"accion": "marcar_todo_leido_mio"})
    assert LecturaBuzon.objects.filter(usuario=u, mensaje__in=[m1, m2]).count() == 2


def test_filtro_adjunto(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    con = _msg(admin, asunto="ConAdjunto")
    _msg(admin, asunto="SinAdjunto")
    from buzon.models import MensajeBuzonAdjunto
    MensajeBuzonAdjunto.objects.create(
        mensaje=con, drive_file_id="x", nombre="f.pdf", mime_type="application/pdf",
        tamano_bytes=10, subido_por=admin,
    )
    client.force_login(admin)
    resp = client.get("/buzon/?adjunto=1")
    assert b"ConAdjunto" in resp.content
    assert b"SinAdjunto" not in resp.content


def test_paginacion_15(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    for i in range(20):
        _msg(admin, asunto=f"Msg{i:02d}")
    client.force_login(admin)
    resp = client.get("/buzon/")
    # 20 mensajes → 2 páginas, la primera muestra 15.
    assert resp.context["page_obj"].paginator.num_pages == 2
    assert len(resp.context["page_obj"].object_list) == 15


def test_tipo_configurable_en_form(client, usuario_factory):
    """Un tipo custom activo aparece como opción en el form de nuevo mensaje."""
    from buzon.models import TipoBuzon
    from buzon.tipos import invalidar_cache
    TipoBuzon.objects.create(slug="felicitacion", label="Felicitación", orden=40, activo=True)
    invalidar_cache()  # cache de proceso es compartido entre tests
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/buzon/nuevo")
    assert b"Felicitaci" in resp.content


def test_accion_notificar_autor_persiste_entrega(client, usuario_factory, monkeypatch):
    """Un estado con accion=notificar_autor dispara push (InterfonoEntrega) al
    autor al mover el mensaje a ese estado."""
    from django.db import transaction

    # on_commit inmediato (Bug E del §14).
    monkeypatch.setattr(transaction, "on_commit",
                        lambda fn, using=None, robust=False: fn())
    from buzon.models import EstadoBuzon
    EstadoBuzon.objects.filter(slug="respondido").update(accion="notificar_autor")
    from buzon.estados import invalidar_cache
    invalidar_cache()

    admin = usuario_factory(rol="super_admin")
    autor = usuario_factory(rol="disenador")
    m = _msg(autor, estado="nuevo")
    client.force_login(admin)
    client.post("/buzon/masivo", data={"ids": [m.pk], "accion": "estado_respondido"})
    from interfono.models.entrega import InterfonoEntrega
    assert InterfonoEntrega.objects.filter(usuario=autor, origen_id=m.pk).exists()
