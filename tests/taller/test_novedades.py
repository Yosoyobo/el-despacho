"""Ayuda: Novedades vs Manual + contador por usuario + push masivo (S-Chalanes-UX #5)."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_parser_separa_novedades_y_manual():
    from lib import novedades as nov
    nov.invalidar_cache()
    items = nov.novedades()
    assert len(items) >= 5
    # Cada bloque tiene clave única + título de Novedades + html.
    claves = [n["clave"] for n in items]
    assert len(claves) == len(set(claves))
    assert all(n["titulo"].lower().startswith("novedad") for n in items)
    # El manual NO debe contener los bloques de novedades (empieza en Bienvenida).
    manual = nov.manual()
    assert "Bienvenida" in manual["html"]


def test_contador_no_vistas_y_marcado(usuario_factory):
    from lib import novedades as nov
    nov.invalidar_cache()
    u = usuario_factory(rol="disenador")
    total = len(nov.claves_actuales())
    assert nov.no_vistas_para(u) == total
    nov.marcar_todas_vistas(u)
    assert nov.no_vistas_para(u) == 0


def test_pagina_novedades_marca_vistas(client, usuario_factory):
    from lib import novedades as nov
    nov.invalidar_cache()
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    assert nov.no_vistas_para(u) > 0
    resp = client.get("/ayuda/novedades/")
    assert resp.status_code == 200
    assert nov.no_vistas_para(u) == 0


def test_pagina_ayuda_es_solo_manual(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/ayuda/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Bienvenida" in body
    assert "Ver novedades" in body  # link a la página de novedades


def test_anunciar_baseline_no_notifica(monkeypatch, usuario_factory):
    """Primera corrida (tabla vacía) = baseline silencioso."""
    from cuentas.models import NovedadAnunciada
    usuario_factory(rol="super_admin")
    enviados = []
    import lib.interfono as interfono
    monkeypatch.setattr(interfono, "enviar_a_usuario", lambda u, **kw: enviados.append(u.pk))
    call_command("anunciar_novedades", stdout=StringIO())
    assert enviados == []                      # baseline no notifica
    assert NovedadAnunciada.objects.exists()   # pero registra todo


def test_anunciar_notifica_solo_nuevas(monkeypatch, usuario_factory):
    from cuentas.models import NovedadAnunciada
    from lib import novedades as nov
    nov.invalidar_cache()
    u1 = usuario_factory(rol="super_admin")
    u2 = usuario_factory(rol="disenador")
    # Baseline: registra TODAS menos una (simulamos que ya estaban anunciadas).
    todas = nov.claves_actuales()
    NovedadAnunciada.objects.bulk_create([NovedadAnunciada(clave=c) for c in todas[1:]])
    enviados = []
    import lib.interfono as interfono
    monkeypatch.setattr(interfono, "enviar_a_usuario", lambda u, **kw: enviados.append(u.pk))
    call_command("anunciar_novedades", stdout=StringIO())
    # 1 novedad nueva → push a TODOS los usuarios activos (uno por usuario).
    assert set(enviados) == {u1.pk, u2.pk}
    # Idempotente: segunda corrida no notifica.
    enviados.clear()
    call_command("anunciar_novedades", stdout=StringIO())
    assert enviados == []
