"""Ronda de Tareas del 2026-08-23 (Oscar).

Tres cosas, y las tres tienen una trampa que el test fija:

1. **El breadcrumb sigue el recorrido**, no el proyecto. La trampa: tras guardar
   una edición el referer es el propio formulario, así que sin filtrarlo el botón
   de volver te devuelve al form que acabas de enviar.
2. **El tablero de reparto se ve DENTRO de Tareas.** La trampa: el partial usa
   `total` para contar mandados y el Kanban usa `total` para contar tareas.
3. **La dirección de un mandado se guarda sin pin.** La trampa: antes se exigían
   coordenadas y quien escribía la dirección sin picar el mapa perdía todo — y de
   forma silenciosa, porque el error viajaba en un redirect que `hx-swap="none"`
   no muestra.
"""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _tarea(proyecto, **kw):
    from apps.el_pizarron.models import Tarea
    defaults = dict(titulo="Entregar lona", tipo="entrega", estado="pendiente",
                    fecha_compromiso=dt.date(2026, 8, 24))
    defaults.update(kw)
    return Tarea.objects.create(proyecto=proyecto, **defaults)


def _admin(usuario_factory, correo):
    return usuario_factory(rol="super_admin", email=correo)


# ── 1. El breadcrumb sigue el recorrido ───────────────────────────────────────

def test_desde_tareas_el_breadcrumb_dice_tareas(client, proyecto_factory, usuario_factory):
    u = _admin(usuario_factory, "bc1@lc.mx")
    t = _tarea(proyecto_factory(estado="en_proceso_diseno"))
    client.force_login(u)
    r = client.get(f"/tareas/{t.pk}/", {"volver": "/tareas/?cat=mandados"})
    assert r.status_code == 200
    migas = [m.get("label") for m in r.context["breadcrumb_items"]]
    assert migas[0] == "Tareas"
    assert r.context["back_url"] == "/tareas/?cat=mandados"


def test_el_referer_tambien_cuenta(client, proyecto_factory, usuario_factory):
    """Sin `?volver=`, el referer sirve — es el caso de picar un enlace normal."""
    u = _admin(usuario_factory, "bc2@lc.mx")
    t = _tarea(proyecto_factory(estado="en_proceso_diseno"))
    client.force_login(u)
    r = client.get(f"/tareas/{t.pk}/", HTTP_REFERER="http://testserver/tareas/lista/")
    assert [m.get("label") for m in r.context["breadcrumb_items"]][0] == "Tareas"


def test_sin_rastro_el_breadcrumb_es_el_proyecto(client, proyecto_factory, usuario_factory):
    u = _admin(usuario_factory, "bc3@lc.mx")
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p)
    client.force_login(u)
    r = client.get(f"/tareas/{t.pk}/")
    migas = [m.get("label") for m in r.context["breadcrumb_items"]]
    assert migas[0] == "Proyectos"
    assert p.codigo in migas


def test_venir_del_propio_formulario_no_cuenta_como_rastro(
        client, proyecto_factory, usuario_factory):
    """La trampa: si contara, el botón de volver regresaría al form enviado."""
    u = _admin(usuario_factory, "bc4@lc.mx")
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p)
    client.force_login(u)
    r = client.get(f"/tareas/{t.pk}/",
                   HTTP_REFERER=f"http://testserver/tareas/{t.pk}/editar")
    assert [m.get("label") for m in r.context["breadcrumb_items"]][0] == "Proyectos"
    # Lo que de verdad importa: el botón NO regresa al formulario.
    assert "/editar" not in r.context["back_url"]
    assert r.context["back_url"] == f"/proyectos/{p.pk}/"


def test_al_guardar_la_edicion_el_rastro_sobrevive(
        client, proyecto_factory, usuario_factory):
    u = _admin(usuario_factory, "bc5@lc.mx")
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p)
    client.force_login(u)
    r = client.post(f"/tareas/{t.pk}/editar", {
        "titulo": "Entregar lona v2", "tipo": "entrega", "estado": "pendiente",
        "prioridad": "media", "asignada_a": u.pk,
        "fecha_compromiso": "2026-08-25", "volver": "/tareas/lista/",
    })
    assert r.status_code == 302
    assert "volver=" in r["Location"]


# ── 2. El tablero de reparto, dentro de Tareas ────────────────────────────────

def test_con_la_categoria_mandados_el_tablero_se_ve_en_tareas(
        client, proyecto_factory, usuario_factory):
    u = _admin(usuario_factory, "tb1@lc.mx")
    _tarea(proyecto_factory(estado="en_proceso_diseno"), titulo="Llevar cajas")
    client.force_login(u)
    r = client.get("/tareas/", {"cat": "mandados"})
    assert r.status_code == 200
    assert r.context["tablero_mandados"] is not None
    assert b"Tablero de reparto" in r.content
    # Y ya no manda a nadie fuera de la página.
    assert b"Tablero de reparto (en camino / entregado)" not in r.content


def test_sin_esa_categoria_no_se_pinta(client, proyecto_factory, usuario_factory):
    u = _admin(usuario_factory, "tb2@lc.mx")
    _tarea(proyecto_factory(estado="en_proceso_diseno"))
    client.force_login(u)
    r = client.get("/tareas/")
    assert r.context["tablero_mandados"] is None


def test_el_contador_de_tareas_no_lo_pisa_el_de_mandados(
        client, proyecto_factory, usuario_factory):
    """La trampa: los dos contextos usan la llave `total`."""
    u = _admin(usuario_factory, "tb3@lc.mx")
    p = proyecto_factory(estado="en_proceso_diseno")
    _tarea(p, titulo="Una")
    _tarea(p, titulo="Dos")
    client.force_login(u)
    r = client.get("/tareas/", {"cat": "mandados"})
    # `total` de la página sigue contando TAREAS, no mandados.
    assert r.context["total"] == 2


def test_los_chips_del_tablero_no_te_sacan_de_tareas(
        client, proyecto_factory, usuario_factory):
    u = _admin(usuario_factory, "tb4@lc.mx")
    _tarea(proyecto_factory(estado="en_proceso_diseno"))
    client.force_login(u)
    r = client.get("/tareas/", {"cat": "mandados"})
    urls = [c["url"] for c in r.context["tablero_mandados"]["chips"]]
    assert all(not u_.startswith("/mandados") for u_ in urls), urls
    # Y filtran con `m_estado` para no pisar el filtro de estado de las tareas.
    assert any("m_estado=" in u_ for u_ in urls), urls


# ── 3. La dirección se guarda sin pin ─────────────────────────────────────────

def _mandado_de(proyecto):
    from apps.el_pizarron.models import Mandado
    return Mandado.objects.get(tarea=_tarea(proyecto))


def test_guarda_la_direccion_aunque_no_haya_pin(client, proyecto_factory, usuario_factory):
    u = _admin(usuario_factory, "dst1@lc.mx")
    m = _mandado_de(proyecto_factory(estado="en_proceso_diseno"))
    client.force_login(u)
    r = client.post(f"/mandados/{m.pk}/destino",
                    {"etiqueta": "Av. Insurgentes 123, Roma Norte"})
    assert r.status_code in (204, 302)
    m.tarea.refresh_from_db()
    assert m.tarea.destino_etiqueta == "Av. Insurgentes 123, Roma Norte"


def test_con_pin_guarda_las_dos_cosas(client, proyecto_factory, usuario_factory):
    u = _admin(usuario_factory, "dst2@lc.mx")
    m = _mandado_de(proyecto_factory(estado="en_proceso_diseno"))
    client.force_login(u)
    client.post(f"/mandados/{m.pk}/destino",
                {"lat": "19.4326", "lng": "-99.1332", "etiqueta": "Zócalo"})
    m.tarea.refresh_from_db()
    assert m.tarea.destino_etiqueta == "Zócalo"
    assert m.tarea.destino_lat == pytest.approx(19.4326)


def test_sin_nada_que_guardar_el_error_SE_VE(client, proyecto_factory, usuario_factory):
    """Antes viajaba en un redirect que `hx-swap=none` no mostraba."""
    u = _admin(usuario_factory, "dst3@lc.mx")
    m = _mandado_de(proyecto_factory(estado="en_proceso_diseno"))
    client.force_login(u)
    r = client.post(f"/mandados/{m.pk}/destino", {}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200          # reinyecta el modal, no redirige
    assert b"Escribe una direcci" in r.content
    m.tarea.refresh_from_db()
    assert not m.tarea.destino_etiqueta
