"""S2b.1.5 — Historial Interfón (InterfonoEntrega + endpoint click + UI)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.django_db


def _configurar_vapid():
    from ajustes.models.credencial import Credencial
    Credencial.guardar("vapid_public_key", "BNpublica-prueba")
    Credencial.guardar("vapid_private_key", "ZHByaXZhZGEtcHJ1ZWJh")
    Credencial.guardar("vapid_email", "mailto:test@ejemplo.com")


def _crear_sub(usuario, endpoint="https://e1"):
    from interfono.models import InterfonoSuscripcion
    return InterfonoSuscripcion.objects.create(
        usuario=usuario,
        endpoint=endpoint,
        p256dh="BN-publica",
        auth="auth-secret",
        user_agent="test",
    )


def test_envio_push_se_persiste_aunque_categoria_desactivada(usuario_factory):
    """Entrega queda registrada incluso si la categoría está apagada."""
    from interfono.models import (
        InterfonoEntrega,
        PreferenciaCategoriaPush,
    )
    from lib.interfono import enviar_a_usuario

    _configurar_vapid()
    u = usuario_factory()
    _crear_sub(u)
    PreferenciaCategoriaPush.objects.create(usuario=u, categoria="recados", activo=False)

    with patch("pywebpush.webpush", return_value=None):
        totales = enviar_a_usuario(u, "Hola", "Cuerpo", categoria="recados")

    assert totales["entregadas"] == 0  # silenciada
    entregas = list(InterfonoEntrega.objects.filter(usuario=u))
    assert len(entregas) == 1
    assert entregas[0].titulo == "Hola"
    assert entregas[0].estado_despacho == "silenciada_categoria"


def test_envio_push_persiste_sin_vapid(usuario_factory):
    """Sin VAPID configurado tampoco se pierde la entrega."""
    from interfono.models import InterfonoEntrega
    from lib.interfono import enviar_a_usuario

    u = usuario_factory()
    totales = enviar_a_usuario(u, "T", "C", origen_modulo="recados", origen_id=42)

    assert totales["entregadas"] == 0
    entrega = InterfonoEntrega.objects.get(usuario=u)
    assert entrega.estado_despacho == "no_configurado"
    assert entrega.origen_modulo == "recados"
    assert entrega.origen_id == 42


def test_historial_solo_propio_usuario(client, usuario_factory):
    """Bandeja de notificaciones nunca expone entregas de otros."""
    from interfono.models import InterfonoEntrega

    u1 = usuario_factory()
    u2 = usuario_factory()
    InterfonoEntrega.objects.create(usuario=u1, titulo="Para U1", cuerpo="x")
    InterfonoEntrega.objects.create(usuario=u2, titulo="Para U2", cuerpo="y")

    client.force_login(u1)
    resp = client.get("/perfil/notificaciones/")
    assert resp.status_code == 200
    assert b"Para U1" in resp.content
    assert b"Para U2" not in resp.content


def test_click_marca_clickeado(client, usuario_factory):
    """POST /perfil/notificaciones/<id>/clickeado marca la entrega."""
    from interfono.models import InterfonoEntrega

    u = usuario_factory()
    e = InterfonoEntrega.objects.create(usuario=u, titulo="X", cuerpo="Y", url="/foo")

    client.force_login(u)
    resp = client.post(f"/perfil/notificaciones/{e.pk}/clickeado")
    assert resp.status_code == 200
    e.refresh_from_db()
    assert e.clickeado_en is not None


def test_click_idempotente_y_defensivo(client, usuario_factory):
    """Re-click no actualiza; click ajeno devuelve 404."""
    from interfono.models import InterfonoEntrega

    u = usuario_factory()
    otro = usuario_factory()
    e = InterfonoEntrega.objects.create(usuario=u, titulo="X", cuerpo="Y")

    client.force_login(u)
    client.post(f"/perfil/notificaciones/{e.pk}/clickeado")
    e.refresh_from_db()
    primera = e.clickeado_en

    client.post(f"/perfil/notificaciones/{e.pk}/clickeado")
    e.refresh_from_db()
    assert e.clickeado_en == primera  # no se re-actualizó

    # Otro usuario no puede marcar la entrega de u
    client.force_login(otro)
    resp = client.post(f"/perfil/notificaciones/{e.pk}/clickeado")
    assert resp.status_code == 404
    e.refresh_from_db()
    assert e.clickeado_en == primera


def test_historial_paginacion_htmx(client, usuario_factory):
    """Endpoint HTMX devuelve siguiente lote."""
    from interfono.models import InterfonoEntrega

    u = usuario_factory()
    for i in range(30):
        InterfonoEntrega.objects.create(usuario=u, titulo=f"T{i}", cuerpo="x")

    client.force_login(u)
    resp = client.get("/perfil/notificaciones/historial/pagina/?offset=25")
    assert resp.status_code == 200
    # Las creadas primero son las más viejas → en offset=25 vemos las primeras 5
    assert b"T4" in resp.content
    assert b"T0" in resp.content


def test_payload_push_incluye_entrega_id_e_iconos(usuario_factory):
    """enviar_a_suscripcion mete entrega_id, icon y badge en el payload JSON."""
    import json

    _configurar_vapid()
    u = usuario_factory()
    sub = _crear_sub(u)

    capturado = {}

    def fake_webpush(**kwargs):
        capturado["data"] = kwargs.get("data")
        return None

    with patch("pywebpush.webpush", side_effect=fake_webpush):
        from lib.interfono import enviar_a_suscripcion
        enviar_a_suscripcion(sub, "T", "C", url="/x", entrega_id=777)

    data = json.loads(capturado["data"])
    assert data["entrega_id"] == 777
    assert data["icon"].endswith("Logo_LC-192.png")
    assert data["badge"].endswith("Logo_LC-64.png")
