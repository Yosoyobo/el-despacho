"""S-Adjuntos-UI — adjuntos del Buzón en bottom pop-over + imágenes inline en
el chat de Recados con lightbox."""

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# --- Buzón: bottom pop-over ---

def _mensaje_con_adjuntos(usuario_factory, autor=None):
    from buzon.models import MensajeBuzon, MensajeBuzonAdjunto
    autor = autor or usuario_factory(rol="disenador")
    msg = MensajeBuzon.objects.create(
        autor=autor, tipo="sugerencia", asunto="Con adjuntos", cuerpo="x" * 30,
    )
    MensajeBuzonAdjunto.objects.create(
        mensaje=msg, drive_file_id="img123", nombre="captura.png",
        mime_type="image/png", tamano_bytes=1024, subido_por=autor,
    )
    MensajeBuzonAdjunto.objects.create(
        mensaje=msg, drive_file_id="doc456", nombre="cotizacion.pdf",
        mime_type="application/pdf", tamano_bytes=2048, subido_por=autor,
    )
    return msg


def test_buzon_detalle_muestra_trigger_de_popover(client, usuario_factory):
    autor = usuario_factory(rol="disenador")
    msg = _mensaje_con_adjuntos(usuario_factory, autor=autor)
    client.force_login(autor)
    resp = client.get(f"/buzon/{msg.pk}/")
    assert resp.status_code == 200
    html = resp.content.decode()
    # Trigger del bottom pop-over (no la lista inline vieja).
    assert "data-adjuntos-popover-trigger" in html
    assert "data-adjuntos-popover-panel" in html
    assert "2 adjunto" in html


def test_buzon_popover_imagen_abre_lightbox(client, usuario_factory):
    autor = usuario_factory(rol="disenador")
    msg = _mensaje_con_adjuntos(usuario_factory, autor=autor)
    adj_img = msg.adjuntos.get(mime_type="image/png")
    client.force_login(autor)
    resp = client.get(f"/buzon/{msg.pk}/")
    html = resp.content.decode()
    # La imagen es un thumbnail con data-lightbox apuntando al proxy.
    assert "data-lightbox=" in html
    assert f"/buzon/adjunto/{adj_img.pk}/" in html
    # El PDF (no imagen) queda como link de descarga.
    adj_pdf = msg.adjuntos.get(mime_type="application/pdf")
    assert f"/buzon/adjunto/{adj_pdf.pk}/" in html


def test_buzon_sin_adjuntos_no_renderiza_popover(client, usuario_factory):
    from buzon.models import MensajeBuzon
    autor = usuario_factory(rol="disenador")
    msg = MensajeBuzon.objects.create(autor=autor, tipo="otro", asunto="Pelado", cuerpo="y" * 30)
    client.force_login(autor)
    resp = client.get(f"/buzon/{msg.pk}/")
    assert b"data-adjuntos-popover-trigger" not in resp.content


# --- Recados chat: imágenes inline con lightbox ---

def test_chat_imagen_inline_con_lightbox(client, usuario_factory, monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())

    from apps.recados.models import MensajeAdjunto
    from apps.recados.services_chat import enviar_mensaje, obtener_o_crear_directa

    autor = usuario_factory(rol="super_admin", email="a@ej.com")
    otro = usuario_factory(rol="disenador", email="o@ej.com")
    conv = obtener_o_crear_directa(autor, otro)
    msg = enviar_mensaje(conversacion=conv, autor=autor, cuerpo="mira esto")
    MensajeAdjunto.objects.create(
        mensaje=msg, drive_file_id="img789", nombre="foto.jpg",
        mime_type="image/jpeg", tamano_bytes=999, subido_por=autor,
    )

    client.force_login(autor)
    resp = client.get(f"/recados/c/{conv.pk}/mensajes", {"desde_id": "0"})
    assert resp.status_code == 200
    html = resp.content.decode()
    # Imagen renderizada inline como <img> con data-lightbox, no como link de texto.
    assert "<img" in html
    assert "data-lightbox=" in html
    assert "/recados/adjunto/" in html


def test_chat_archivo_no_imagen_es_link(client, usuario_factory, monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())

    from apps.recados.models import MensajeAdjunto
    from apps.recados.services_chat import enviar_mensaje, obtener_o_crear_directa

    autor = usuario_factory(rol="super_admin", email="a@ej.com")
    otro = usuario_factory(rol="disenador", email="o@ej.com")
    conv = obtener_o_crear_directa(autor, otro)
    msg = enviar_mensaje(conversacion=conv, autor=autor, cuerpo="el archivo")
    adj = MensajeAdjunto.objects.create(
        mensaje=msg, drive_file_id="doc000", nombre="reporte.pdf",
        mime_type="application/pdf", tamano_bytes=999, subido_por=autor,
    )

    client.force_login(autor)
    resp = client.get(f"/recados/c/{conv.pk}/mensajes", {"desde_id": "0"})
    html = resp.content.decode()
    assert f"/recados/adjunto/{adj.pk}/" in html
    assert "reporte.pdf" in html
