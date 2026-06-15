"""S-LC-Feedback-V11 — formato de hora por usuario (24h / AM-PM) aplicado a
TODAS las horas vía el filtro `hfmt` (decisión Oscar; default 24h)."""

from __future__ import annotations

import datetime

import pytest
from django.template import Context, Template
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _render(fmt, valor, pref):
    from lib.formato_hora import set_formato
    set_formato(pref)
    t = Template("{% load horas %}{{ v|hfmt:'" + fmt + "' }}")
    return t.render(Context({"v": valor}))


def test_hfmt_24h_default():
    dt = timezone.make_aware(datetime.datetime(2026, 6, 15, 14, 30))
    assert _render("H:i", dt, "24h") == "14:30"
    assert _render("Y-m-d H:i", dt, "24h") == "2026-06-15 14:30"


def test_hfmt_ampm():
    dt = timezone.make_aware(datetime.datetime(2026, 6, 15, 14, 30))
    out = _render("H:i", dt, "ampm")
    assert out == "2:30 p.m."
    # La parte de fecha se preserva, solo cambia la hora.
    full = _render("Y-m-d H:i", dt, "ampm")
    assert full == "2026-06-15 2:30 p.m."


def test_hfmt_ampm_manana():
    dt = timezone.make_aware(datetime.datetime(2026, 6, 15, 9, 5))
    assert _render("H:i", dt, "ampm") == "9:05 a.m."


def test_hfmt_vacio():
    assert _render("H:i", None, "ampm") == ""


def test_formato_hora_default_usuario(usuario_factory):
    u = usuario_factory(rol="disenador")
    assert u.formato_hora == "24h"


def test_guardar_formato_hora_view(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.post("/perfil/notificaciones/formato-hora/", {"formato_hora": "ampm"})
    assert resp.status_code in (302, 200)
    u.refresh_from_db()
    assert u.formato_hora == "ampm"


def test_guardar_formato_hora_invalido(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    client.post("/perfil/notificaciones/formato-hora/", {"formato_hora": "xx"})
    u.refresh_from_db()
    assert u.formato_hora == "24h"  # no se cambia con valor inválido
