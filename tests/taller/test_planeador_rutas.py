"""S-Planeador-Rutas — el reparto del día, guardado, y el correo del runner.

Lo que estos tests defienden, en orden de importancia:

1. **La hora es cita fija.** Ninguna reordenación puede mover de lugar una
   parada con cita. Es la decisión de Oscar y es la que más fácil se rompe al
   optimizar kilómetros, así que se prueba con un caso donde respetar la cita
   CUESTA distancia.
2. **Replanear no duplica.** Es la garantía que hace seguro apretar el botón dos
   veces con rutas ya despachadas.
3. **El correo sale de runner@** y no se manda dos veces.
"""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

HOY = dt.date(2026, 8, 24)

# Puntos reales-ish de la Ciudad de México, para que las distancias tengan
# sentido al leer un fallo.
CENTRO = (19.4326, -99.1332)      # Zócalo
CERCA = (19.4340, -99.1400)       # ~700 m del Zócalo
LEJOS = (19.3600, -99.2700)       # ~15 km al suroeste
MEDIO = (19.4000, -99.1800)       # entre los dos


def _hacer_runner(*usuarios):
    """S-Roles-V2: runner es opt-in vía el rol «Runner» (sembrado en 0033)."""
    from cuentas.models.rol import Rol
    r = Rol.objects.get(nombre="Runner")
    for u in usuarios:
        u.roles_extra.add(r)


def _mandado(proyecto, punto, *, hora=None, titulo="Entregar lona", fecha=HOY):
    """Crea la Tarea de entrega (la señal crea el Mandado) con destino fijado."""
    from apps.el_pizarron.models import Mandado, Tarea
    t = Tarea.objects.create(
        proyecto=proyecto, titulo=titulo, tipo="entrega", estado="pendiente",
        fecha_compromiso=fecha, hora=hora,
        destino_lat=punto[0], destino_lng=punto[1],
        destino_etiqueta=titulo,
    )
    return Mandado.objects.get(tarea=t)


# ── 1. La hora es cita fija ───────────────────────────────────────────────────

def test_las_citas_quedan_en_orden_de_reloj_aunque_cueste_distancia():
    """El caso que más importa: respetar la cita contra el ahorro de kilómetros.

    La cita de las 9 está LEJOS y la de las 11 está CERCA del origen. Optimizar
    distancia querría empezar por la cercana; la regla de Oscar dice que no.
    """
    from apps.el_pizarron.planeador import _ordenar_con_citas

    paradas = [
        {"id": "cerca_11", "lat": CERCA[0], "lng": CERCA[1], "hora": dt.time(11, 0)},
        {"id": "lejos_9", "lat": LEJOS[0], "lng": LEJOS[1], "hora": dt.time(9, 0)},
    ]
    orden = _ordenar_con_citas(CENTRO, paradas, cerrar=False)
    assert [p["id"] for p in orden] == ["lejos_9", "cerca_11"]


def test_una_parada_libre_no_se_cuela_entre_dos_citas_desordenandolas():
    from apps.el_pizarron.planeador import _ordenar_con_citas

    paradas = [
        {"id": "cita_9", "lat": CENTRO[0], "lng": CENTRO[1], "hora": dt.time(9, 0)},
        {"id": "cita_17", "lat": LEJOS[0], "lng": LEJOS[1], "hora": dt.time(17, 0)},
        {"id": "libre", "lat": MEDIO[0], "lng": MEDIO[1], "hora": None},
    ]
    orden = [p["id"] for p in _ordenar_con_citas(CENTRO, paradas, cerrar=False)]
    assert orden.index("cita_9") < orden.index("cita_17")


def test_las_libres_se_ordenan_por_cercania():
    from apps.el_pizarron.planeador import _ordenar_con_citas

    paradas = [
        {"id": "lejos", "lat": LEJOS[0], "lng": LEJOS[1], "hora": None},
        {"id": "cerca", "lat": CERCA[0], "lng": CERCA[1], "hora": None},
    ]
    orden = [p["id"] for p in _ordenar_con_citas(CENTRO, paradas, cerrar=False)]
    assert orden == ["cerca", "lejos"]


def test_las_paradas_sin_coordenadas_van_al_final_pero_no_se_pierden():
    from apps.el_pizarron.planeador import _ordenar_con_citas

    paradas = [
        {"id": "sin_ubicar", "lat": None, "lng": None, "hora": None},
        {"id": "ubicada", "lat": CERCA[0], "lng": CERCA[1], "hora": None},
    ]
    orden = [p["id"] for p in _ordenar_con_citas(CENTRO, paradas, cerrar=False)]
    assert orden == ["ubicada", "sin_ubicar"]


def test_la_ruta_redonda_mide_el_regreso():
    from apps.el_pizarron.planeador import largo_de

    secuencia = [{"lat": LEJOS[0], "lng": LEJOS[1]}]
    abierta = largo_de(CENTRO, secuencia, cerrar=False)
    redonda = largo_de(CENTRO, secuencia, cerrar=True)
    assert redonda > abierta
    assert redonda == pytest.approx(abierta * 2, rel=0.01)


# ── 2. Horas estimadas ────────────────────────────────────────────────────────

def test_si_llega_antes_de_la_cita_la_hora_que_se_muestra_es_la_de_la_cita():
    from apps.el_pizarron.planeador import estimar_horas

    secuencia = [{"lat": CERCA[0], "lng": CERCA[1], "hora": dt.time(14, 0)}]
    (_, hora, _), = estimar_horas(CENTRO, secuencia, inicio=dt.time(9, 0))
    assert hora == dt.time(14, 0)


def test_sin_cita_la_hora_sale_del_viaje():
    from apps.el_pizarron.planeador import estimar_horas

    secuencia = [{"lat": CERCA[0], "lng": CERCA[1], "hora": None}]
    (_, hora, metros), = estimar_horas(CENTRO, secuencia, inicio=dt.time(9, 0))
    assert hora >= dt.time(9, 0)
    assert metros > 0


# ── 3. Planear y guardar ──────────────────────────────────────────────────────

def test_planear_reparte_entre_los_runners_y_guarda_las_rutas(
        proyecto_factory, usuario_factory):
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="runner-a@lc.mx")
    b = usuario_factory(rol="disenador", email="runner-b@lc.mx")
    _hacer_runner(a, b)

    for i, punto in enumerate((CENTRO, CERCA, LEJOS, MEDIO)):
        _mandado(p, punto, titulo=f"Entrega {i}")

    res = planear_dia(HOY, origen_modo="runner_abierta")
    assert res["sin_runner"] is False
    rutas = Ruta.objects.filter(fecha=HOY)
    # Las 4 paradas quedaron repartidas, sin perder ninguna.
    assert sum(r.total_paradas for r in rutas) == 4
    # Y el reparto tocó a los dos runners, no se apiló en uno.
    assert rutas.count() == 2


def test_replanear_no_duplica_las_paradas_ya_ruteadas(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models.ruta import ParadaRuta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="idem@lc.mx")
    _hacer_runner(a)
    _mandado(p, CENTRO)
    _mandado(p, CERCA, titulo="Otra")

    planear_dia(HOY, origen_modo="runner_abierta")
    antes = ParadaRuta.objects.count()
    planear_dia(HOY, origen_modo="runner_abierta")
    assert ParadaRuta.objects.count() == antes == 2


def test_solo_puede_haber_una_ruta_viva_por_runner_y_dia(usuario_factory):
    """El candado vive en la BASE, no en el código que escribe."""
    from django.db import IntegrityError, transaction

    from apps.el_pizarron.models.ruta import Ruta
    a = usuario_factory(rol="disenador", email="candado@lc.mx")
    Ruta.objects.create(fecha=HOY, runner=a, estado="borrador")
    with pytest.raises(IntegrityError), transaction.atomic():
        Ruta.objects.create(fecha=HOY, runner=a, estado="despachada")


def test_una_cancelada_no_estorba_para_volver_a_planear(usuario_factory):
    from apps.el_pizarron.models.ruta import Ruta
    a = usuario_factory(rol="disenador", email="cancel@lc.mx")
    Ruta.objects.create(fecha=HOY, runner=a, estado="cancelada")
    # No debe levantar: la cancelada queda fuera del candado parcial.
    Ruta.objects.create(fecha=HOY, runner=a, estado="borrador")
    assert Ruta.objects.filter(fecha=HOY, runner=a).count() == 2


def test_un_mandado_entregado_no_entra_al_reparto(proyecto_factory, usuario_factory):
    from apps.el_pizarron.planeador import candidatos_del_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="cerrado@lc.mx")
    _hacer_runner(a)
    m = _mandado(p, CENTRO)
    m.estado = "entregado"
    m.save(update_fields=["estado"])
    assert m not in candidatos_del_dia(HOY)


# ── 4. Reacomodo a mano ───────────────────────────────────────────────────────

def test_reordenar_respeta_lo_que_dejo_la_persona_y_recalcula(
        proyecto_factory, usuario_factory):
    from apps.el_pizarron.planeador import planear_dia, reordenar

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="reord@lc.mx")
    _hacer_runner(a)
    _mandado(p, CERCA, titulo="Cercana")
    _mandado(p, LEJOS, titulo="Lejana")

    ruta = planear_dia(HOY, origen_modo="runner_abierta")["rutas"][0]
    pks = list(ruta.paradas.values_list("pk", flat=True))
    reordenar(ruta, list(reversed(pks)))
    assert list(ruta.paradas.values_list("pk", flat=True)) == list(reversed(pks))


def test_mover_una_parada_de_una_ruta_a_otra(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import mover_parada, planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="mov-a@lc.mx")
    b = usuario_factory(rol="disenador", email="mov-b@lc.mx")
    _hacer_runner(a, b)
    _mandado(p, CENTRO, titulo="Una")
    _mandado(p, LEJOS, titulo="Dos")
    planear_dia(HOY, origen_modo="runner_abierta")

    ruta_a = Ruta.objects.filter(fecha=HOY, runner=a).first()
    ruta_b = Ruta.objects.filter(fecha=HOY, runner=b).first()
    parada = ruta_a.paradas.first()
    mover_parada(parada, ruta_b)
    parada.refresh_from_db()
    assert parada.ruta_id == ruta_b.pk


# ── 5. Los enlaces a las apps (lo que Oscar pidió desde el principio) ────────

def test_los_enlaces_a_las_apps_salen_de_la_ruta_guardada(
        proyecto_factory, usuario_factory):
    from apps.el_pizarron.planeador import enlaces_de, planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="apps@lc.mx")
    _hacer_runner(a)
    _mandado(p, CENTRO, titulo="Una")
    _mandado(p, LEJOS, titulo="Dos")
    ruta = planear_dia(HOY, origen_modo="runner_abierta")["rutas"][0]

    enlaces = enlaces_de(ruta)
    assert "google.com/maps/dir" in enlaces["google"]
    assert "waypoints=" in enlaces["google"]      # multiparada de verdad
    assert "maps.apple.com" in enlaces["apple"]
    assert "waze.com" in enlaces["waze"]


# ── 6. El correo del runner ───────────────────────────────────────────────────

def _interceptar_correo(monkeypatch):
    """Captura lo que le llega a El Cartero sin mandar nada."""
    enviados = []

    class _Res:
        ok = True
        error = ""

    def _falso(**kw):
        enviados.append(kw)
        return _Res()

    from lib import cartero
    monkeypatch.setattr(cartero, "enviar", _falso)
    return enviados


def test_despachar_manda_la_ruta_al_runner_desde_runner_arroba(
        proyecto_factory, usuario_factory, monkeypatch):
    from apps.el_pizarron.planeador import despachar, planear_dia

    enviados = _interceptar_correo(monkeypatch)
    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="correo@lc.mx")
    _hacer_runner(a)
    _mandado(p, CENTRO, titulo="Con correo")
    ruta = planear_dia(HOY, origen_modo="runner_abierta")["rutas"][0]

    despachar(ruta, actor=None)
    ruta.refresh_from_db()
    assert ruta.estado == "despachada"
    assert len(enviados) == 1
    assert enviados[0]["destinatario"] == "correo@lc.mx"
    # El alias departamental que Oscar pidió integrar.
    assert "runner@learningcenter.mx" in enviados[0]["remitente"]
    assert ruta.correo_enviado_en is not None


def test_la_ruta_no_se_manda_dos_veces(proyecto_factory, usuario_factory, monkeypatch):
    from apps.el_pizarron import rutas_correo
    from apps.el_pizarron.planeador import despachar, planear_dia

    enviados = _interceptar_correo(monkeypatch)
    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="unavez@lc.mx")
    _hacer_runner(a)
    _mandado(p, CENTRO)
    ruta = planear_dia(HOY, origen_modo="runner_abierta")["rutas"][0]

    despachar(ruta, actor=None)
    assert rutas_correo.avisar_ruta_al_runner(ruta) is False  # ya se mandó
    assert len(enviados) == 1


def test_el_correo_lleva_las_paradas_y_los_tres_enlaces(
        proyecto_factory, usuario_factory):
    from apps.el_pizarron.planeador import planear_dia
    from apps.el_pizarron.rutas_correo import contexto_de_ruta

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="ctx@lc.mx")
    _hacer_runner(a)
    _mandado(p, CENTRO, titulo="Primera", hora=dt.time(10, 0))
    _mandado(p, LEJOS, titulo="Segunda")
    ruta = planear_dia(HOY, origen_modo="runner_abierta")["rutas"][0]

    ctx = contexto_de_ruta(ruta)
    assert ctx["total_paradas"] == 2
    assert len(ctx["paradas"]) == 2
    assert any(par["cita"] for par in ctx["paradas"])   # la de las 10 trae cita
    assert ctx["enlace_google"] and ctx["enlace_waze"] and ctx["enlace_apple"]
    assert ctx["runner"]


def test_un_runner_sin_correo_no_tumba_el_despacho(
        proyecto_factory, usuario_factory, monkeypatch):
    """El correo es best-effort: la ruta se despacha igual."""
    from apps.el_pizarron.planeador import despachar, planear_dia

    enviados = _interceptar_correo(monkeypatch)
    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="tiene@lc.mx")
    _hacer_runner(a)
    _mandado(p, CENTRO)
    ruta = planear_dia(HOY, origen_modo="runner_abierta")["rutas"][0]
    a.email = ""
    a.save(update_fields=["email"])
    # Recargar la ruta: `ruta.runner` es una instancia ya cacheada y seguiría
    # trayendo el correo viejo.
    from apps.el_pizarron.models.ruta import Ruta
    ruta = Ruta.objects.get(pk=ruta.pk)

    despachar(ruta, actor=None)
    ruta.refresh_from_db()
    assert ruta.estado == "despachada"
    assert enviados == []


def test_el_aviso_al_cliente_arranca_apagado(proyecto_factory, usuario_factory,
                                             monkeypatch):
    """La regla `mandado_en_camino` no manda nada hasta que alguien la encienda."""
    from apps.el_pizarron import mandados as svc

    enviados = _interceptar_correo(monkeypatch)
    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="encamino@lc.mx")
    _hacer_runner(a)
    m = _mandado(p, CENTRO)
    svc.marcar_en_camino(m)
    assert enviados == []


# ── 7. Permisos ───────────────────────────────────────────────────────────────

def test_el_super_admin_trae_las_llaves_del_planeador(usuario_factory):
    from lib.permisos import (
        puede_despachar_rutas, puede_planear_rutas, puede_ver_rutas,
    )
    jefe = usuario_factory(rol="super_admin", email="jefe-rutas@lc.mx")
    assert puede_ver_rutas(jefe)
    assert puede_planear_rutas(jefe)
    assert puede_despachar_rutas(jefe)


def test_el_runner_ve_pero_no_despacha(usuario_factory):
    from lib.permisos import puede_despachar_rutas, puede_ver_rutas
    u = usuario_factory(rol="disenador", email="solo-ve@lc.mx")
    _hacer_runner(u)
    assert puede_ver_rutas(u)
    assert not puede_despachar_rutas(u)


def test_rutas_aparece_en_el_catalogo_delegable():
    """Si no está en el catálogo, no se puede delegar desde El Directorio."""
    from lib.permisos_defaults import CATALOGO_PERMISOS
    assert set(CATALOGO_PERMISOS["rutas"]) == {"ver", "planear", "despachar"}
