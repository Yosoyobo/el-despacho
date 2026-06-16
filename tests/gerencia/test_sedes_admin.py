"""S-LC-Feedback-V12 — CRUD de Sedes/POI de LC + modo de geocerca en Gerencia,
columna Acción/descripción en estados de proyecto/tarea, y el comando
quitar_superadmin."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


# ── Sedes CRUD ────────────────────────────────────────────────────────────

def test_sedes_lista_super_admin(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogos/sedes/")
    assert resp.status_code == 200
    assert b"Sedes de LC" in resp.content


def test_sedes_sin_permiso_403(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/catalogos/sedes/")
    assert resp.status_code == 403


def test_crear_sede(client, usuario_factory):
    from apps.checador.models import SedeLC
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/sedes/nueva/", data={
        "nombre": "Oficina Centro", "direccion": "Reforma 100",
        "lat": "19.4326", "lng": "-99.1332", "radio_m": "200",
        "activa": "on", "orden": "10", "notas": "",
    })
    assert resp.status_code in (301, 302)
    s = SedeLC.objects.get(nombre="Oficina Centro")
    assert s.radio_m == 200
    assert float(s.lat) == pytest.approx(19.4326)


def test_editar_y_borrar_sede(client, usuario_factory):
    from apps.checador.models import SedeLC
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    s = SedeLC.objects.create(nombre="Tmp", lat=19.4, lng=-99.1, radio_m=150)
    resp = client.post(f"/catalogos/sedes/{s.pk}/editar/", data={
        "nombre": "Tmp 2", "direccion": "", "lat": "19.4", "lng": "-99.1",
        "radio_m": "300", "activa": "on", "orden": "20", "notas": "",
    })
    assert resp.status_code in (301, 302)
    s.refresh_from_db()
    assert s.nombre == "Tmp 2" and s.radio_m == 300
    resp = client.post(f"/catalogos/sedes/{s.pk}/borrar/")
    assert resp.status_code in (301, 302)
    assert not SedeLC.objects.filter(pk=s.pk).exists()


def test_cambiar_modo_geocerca(client, usuario_factory):
    from apps.checador.models import ConfiguracionGeocerca
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/sedes/geocerca/", data={"modo": "restringido"})
    assert resp.status_code in (301, 302)
    assert ConfiguracionGeocerca.obtener().modo == "restringido"


# ── Estados: columna Acción + descripción (item 2) ──────────────────────────

def test_estados_proyecto_lista_tiene_accion(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/catalogos/estados-proyecto/")
    assert resp.status_code == 200
    assert b"Acci\xc3\xb3n" in resp.content  # encabezado "Acción"


def test_estados_tarea_guarda_accion_y_descripcion(client, usuario_factory):
    from apps.el_pizarron.models import EstadoTarea
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post("/catalogos/estados-tarea/nuevo/", data={
        "label": "En revisión", "descripcion": "Alguien la revisa",
        "color": "#7a5af8", "accion": "notificar_asignado",
        "orden": "25", "terminal": "", "activo": "on",
    })
    assert resp.status_code in (301, 302)
    obj = EstadoTarea.objects.get(label="En revisión")
    assert obj.accion == "notificar_asignado"
    assert obj.descripcion == "Alguien la revisa"


# ── Comando quitar_superadmin (item 4) ───────────────────────────────────────

def test_quitar_superadmin_baja_a_miembro(usuario_factory):
    from django.core.management import call_command
    jorge = usuario_factory(rol="super_admin", email="jorge@lc.mx")
    call_command("quitar_superadmin", email="jorge@lc.mx")
    jorge.refresh_from_db()
    assert jorge.rol == "miembro"


def test_quitar_superadmin_idempotente(usuario_factory):
    from django.core.management import call_command
    usuario_factory(rol="miembro", email="ana@lc.mx")
    # No truena ni cambia nada si ya no es super_admin.
    call_command("quitar_superadmin", email="ana@lc.mx")
