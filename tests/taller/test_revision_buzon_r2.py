"""Revisión del buzón — Ronda 2 (2026-07): acciones rápidas como form-in-modal
(render de Oscar). Exemplar: «Nueva Tarea»."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_nueva_tarea_modal_get_htmx(client, usuario_factory, proyecto_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    proyecto_factory(creado_por=autor)
    resp = client.get("/tareas/nueva/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "Nueva Tarea" in cuerpo
    assert "data-nueva-tarea" in cuerpo
    assert "data-select-buscable" in cuerpo  # combobox en Proyecto/Asignar a
    assert "data-minical" in cuerpo          # calendario inline


def test_nueva_tarea_modal_post_htmx_crea_y_redirige(client, usuario_factory, proyecto_factory):
    from apps.el_pizarron.models import Tarea

    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    proy = proyecto_factory(creado_por=autor)
    resp = client.post("/tareas/nueva/", {
        "proyecto": proy.pk,
        "titulo": "Diseñar volante",
        "asignada_a": autor.pk,
        "fecha_compromiso": (date.today() + timedelta(days=3)).isoformat(),
        "tipo": "tarea",
    }, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect")
    assert Tarea.objects.filter(titulo="Diseñar volante", proyecto=proy).exists()


def test_nueva_tarea_pagina_full_sigue_de_fallback(client, usuario_factory, proyecto_factory):
    autor = usuario_factory(rol="super_admin")
    client.force_login(autor)
    proyecto_factory(creado_por=autor)
    resp = client.get("/tareas/nueva/")  # sin HX-Request
    assert resp.status_code == 200
    # La página full extiende base.html (trae el shell), el modal no.
    assert b"modal-slot" in resp.content or b"Nueva tarea" in resp.content
