"""Persistencia de adjuntos en el chat de El Chalán (S-Drive-Cierre).

Antes la imagen se pasaba al LLM y se descartaba; ahora se sube a Drive y
queda un MensajeChatAdjunto en el turno del usuario. Mockea el LLM y la subida
a Drive (no pega a servicios externos).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _ns(texto):
    return SimpleNamespace(
        texto=texto, provider="anthropic", modelo="claude-haiku-4-5",
        prompt_tokens=1, completion_tokens=1, costo_usd=0.0, latencia_ms=1,
    )


def _fake_responder(monkeypatch):
    import lib.analistas as la
    monkeypatch.setattr(
        la, "analizar",
        lambda estacion, prompt, **kw: _ns(json.dumps({"tipo": "responder", "texto": "ok"})),
    )


class _ArchivoFake:
    """Imita un UploadedFile mínimo (name, content_type, size, read, seek)."""
    def __init__(self, data=b"\x89PNG fake", name="recibo.png", content_type="image/png"):
        self._data = data
        self.name = name
        self.content_type = content_type
        self.size = len(data)
        self._pos = 0

    def read(self):
        return self._data

    def seek(self, pos):
        self._pos = pos


def test_conversar_persiste_adjunto_en_drive(monkeypatch, usuario_factory):
    from apps.el_dictado.models import MensajeChatAdjunto
    from apps.el_dictado.services_chat import conversar, crear_conversacion

    _fake_responder(monkeypatch)
    # Mock de la subida a Drive (lib.adjuntos.subir).
    from lib import adjuntos
    monkeypatch.setattr(
        adjuntos, "subir",
        lambda archivo, subcarpeta=None: adjuntos.ResultadoAdjunto(
            ok=True, data={"id": "DRV1", "name": "recibo.png",
                           "mimeType": "image/png", "size": 9}),
    )

    u = usuario_factory(rol="super_admin")
    conv = crear_conversacion(usuario=u)
    res = conversar(
        mensaje="¿qué dice este recibo?", usuario=u, conversacion=conv,
        imagenes=[{"base64": "x", "media_type": "image/png"}],
        archivo_adjunto=_ArchivoFake(),
    )
    msg_user = res["mensajes"][0]
    adj = MensajeChatAdjunto.objects.filter(mensaje=msg_user)
    assert adj.count() == 1
    assert adj.first().drive_file_id == "DRV1"
    assert adj.first().es_imagen


def test_conversar_sin_drive_no_falla(monkeypatch, usuario_factory):
    """Si Drive no responde, el chat sigue (no se crea adjunto, no lanza)."""
    from apps.el_dictado.models import MensajeChatAdjunto
    from apps.el_dictado.services_chat import conversar, crear_conversacion

    _fake_responder(monkeypatch)
    from lib import adjuntos
    monkeypatch.setattr(
        adjuntos, "subir",
        lambda archivo, subcarpeta=None: adjuntos.ResultadoAdjunto(ok=False, error="Drive caído"),
    )
    u = usuario_factory(rol="super_admin")
    conv = crear_conversacion(usuario=u)
    res = conversar(
        mensaje="lee esto", usuario=u, conversacion=conv,
        imagenes=[{"base64": "x", "media_type": "image/png"}],
        archivo_adjunto=_ArchivoFake(),
    )
    assert res["mensajes"]  # respondió igual
    assert MensajeChatAdjunto.objects.count() == 0


def test_adjunto_descargar_solo_dueno(monkeypatch, usuario_factory):
    from apps.el_dictado.models import (
        ConversacionChat,
        MensajeChat,
        MensajeChatAdjunto,
    )

    dueno = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="contador")
    conv = ConversacionChat.objects.create(usuario=dueno)
    msg = MensajeChat.objects.create(conversacion=conv, orden=0, rol="user", cuerpo="x")
    adj = MensajeChatAdjunto.objects.create(
        mensaje=msg, drive_file_id="D1", nombre="r.png", mime_type="image/png")

    from lib.google_drive import drive
    monkeypatch.setattr(drive, "descargar", lambda fid: (b"BYTES", "image/png", "r.png"))

    from django.test import Client
    c = Client()
    c.force_login(otro)
    assert c.get(f"/chalan/adjunto/{adj.pk}").status_code == 404  # no es su conversación
    c.force_login(dueno)
    resp = c.get(f"/chalan/adjunto/{adj.pk}")
    assert resp.status_code == 200
    assert resp.content == b"BYTES"
