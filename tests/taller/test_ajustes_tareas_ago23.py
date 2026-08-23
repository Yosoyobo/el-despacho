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


# ── 4. El PIN del lugar se guarda (Oscar: «siguen sin guardarse») ─────────────

def test_la_tarea_guarda_el_pin_del_lugar(client, proyecto_factory, usuario_factory):
    """El texto ya se guardaba; el PUNTO se tiraba porque no estaba en el form.

    Sin punto el lugar no sirve de nada: el planeador no lo rutea, el mapa no lo
    muestra y no hay «cómo llegar».
    """
    from apps.el_pizarron.models import Tarea
    u = _admin(usuario_factory, "pin1@lc.mx")
    p = proyecto_factory(estado="en_proceso_diseno")
    client.force_login(u)
    client.post(f"/proyectos/{p.pk}/tareas/nueva", {
        "titulo": "Entregar en Insurgentes", "tipo": "entrega", "estado": "pendiente",
        "prioridad": "media", "asignada_a": u.pk, "fecha_compromiso": "2026-08-26",
        "destino_etiqueta": "Av. Insurgentes Sur 123",
        "destino_lat": "19.4100", "destino_lng": "-99.1700",
    })
    t = Tarea.objects.get(titulo="Entregar en Insurgentes")
    assert t.destino_etiqueta == "Av. Insurgentes Sur 123"
    assert t.destino_lat == pytest.approx(19.4100)
    assert t.destino_lng == pytest.approx(-99.1700)


def test_editar_una_tarea_conserva_el_pin(client, proyecto_factory, usuario_factory):
    u = _admin(usuario_factory, "pin2@lc.mx")
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p, destino_etiqueta="Zócalo", destino_lat=19.4326, destino_lng=-99.1332)
    client.force_login(u)
    client.post(f"/tareas/{t.pk}/editar", {
        "titulo": t.titulo, "tipo": "entrega", "estado": "pendiente",
        "prioridad": "media", "asignada_a": u.pk, "fecha_compromiso": "2026-08-26",
        "destino_etiqueta": "Zócalo", "destino_lat": "19.4326", "destino_lng": "-99.1332",
    })
    t.refresh_from_db()
    assert t.destino_lat == pytest.approx(19.4326)


def test_un_pin_a_medias_no_se_guarda(client, proyecto_factory, usuario_factory):
    """Media coordenada no ubica nada; se descarta en vez de guardar basura."""
    from apps.el_pizarron.models import Tarea
    u = _admin(usuario_factory, "pin3@lc.mx")
    p = proyecto_factory(estado="en_proceso_diseno")
    client.force_login(u)
    client.post(f"/proyectos/{p.pk}/tareas/nueva", {
        "titulo": "Media coordenada", "tipo": "entrega", "estado": "pendiente",
        "prioridad": "media", "asignada_a": u.pk, "fecha_compromiso": "2026-08-26",
        "destino_etiqueta": "Algún lado", "destino_lat": "19.41",
    })
    t = Tarea.objects.get(titulo="Media coordenada")
    assert t.destino_lat is None and t.destino_lng is None
    assert t.destino_etiqueta == "Algún lado"      # el texto sí


def test_con_el_pin_el_planeador_ya_puede_rutear(proyecto_factory, usuario_factory):
    """El porqué de todo esto: sin punto, la entrega no entra a ninguna ruta."""
    from apps.el_pizarron.planeador import candidatos_del_dia, planear_dia

    from cuentas.models.rol import Rol

    r = usuario_factory(rol="disenador", email="pin4@lc.mx")
    r.roles_extra.add(Rol.objects.get(nombre="Runner"))
    p = proyecto_factory(estado="en_proceso_diseno")
    _tarea(p, titulo="Con pin", destino_lat=19.43, destino_lng=-99.13)
    _tarea(p, titulo="Sin pin", destino_etiqueta="Sólo texto")

    assert len(candidatos_del_dia(dt.date(2026, 8, 24))) == 2
    res = planear_dia(dt.date(2026, 8, 24), origen_modo="runner_abierta")
    # La que trae punto entra a la ruta; la otra se reporta como no ubicable.
    assert sum(x.total_paradas for x in res["rutas"]) == 1
    assert len(res["sin_ubicar"]) == 1


def test_los_botones_de_ruta_viajan_con_el_tablero(client, proyecto_factory, usuario_factory):
    """Se quedaron atrás al mudar el tablero a Tareas — «no veo los botones»."""
    u = _admin(usuario_factory, "btn@lc.mx")
    _tarea(proyecto_factory(estado="en_proceso_diseno"))
    client.force_login(u)
    for url, params in (("/tareas/", {"cat": "mandados"}), ("/mandados/", {})):
        r = client.get(url, params)
        assert b"Planear rutas" in r.content, url
        assert b"Mi ruta de hoy" in r.content, url
