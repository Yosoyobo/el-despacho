"""Ronda de Oscar del 2026-08-23: «las rutas y el planeador todavía no quedan».

Lo que se encontró en producción y lo que estos tests defienden, en orden de
importancia:

1. **Una sola verdad sobre quién hace la entrega.** La ruta del día se armó a
   nombre de Alex y sus dos paradas eran mandados que decían Oscar: el planeador
   repartía entre quien tuviera el permiso, ignoraba al runner ya asignado y no
   escribía nada en la tarea. Ahora manda el dueño puesto a mano, y lo que el
   reparto coloca queda escrito.
2. **La pantalla no puede mentir sobre la razón.** «Sin repartir» acusaba de no
   tener destino a mandados que lo tenían perfectamente puesto (Stampa y
   ninomeando, con coordenadas). Son dos problemas distintos y van separados.
3. **«Mi ruta de hoy» es de hoy.** Traía todos los mandados abiertos del runner
   de cualquier fecha y aunque su tarea estuviera archivada.
"""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

HOY = dt.date(2026, 8, 24)

# Los puntos reales del caso de Oscar, para que un fallo se lea con sentido.
STAMPA = (19.350313, -99.298189)
NINOMEANDO = (19.371382, -99.267477)
OFICINA = (19.443446, -99.207820)


def _hacer_runner(*usuarios):
    from cuentas.models.rol import Rol
    r = Rol.objects.get(nombre="Runner")
    for u in usuarios:
        u.roles_extra.add(r)


def _mandado(proyecto, punto, *, titulo="Entregar lona", fecha=HOY,
             runner=None, runner_auto=False, hora=None, archivada=False):
    """Crea la Tarea de entrega (la señal crea el Mandado).

    `punto=None` deja la tarea sin destino, que es el caso que la pantalla tiene
    que reportar distinto.
    """
    from apps.el_pizarron.models import Mandado, Tarea
    t = Tarea.objects.create(
        proyecto=proyecto, titulo=titulo, tipo="entrega", estado="pendiente",
        fecha_compromiso=fecha, hora=hora, archivada=archivada,
        destino_lat=punto[0] if punto else None,
        destino_lng=punto[1] if punto else None,
        destino_etiqueta=titulo if punto else "",
        runner=runner, runner_auto=runner_auto,
        requiere_runner=bool(runner),
    )
    return Mandado.objects.get(tarea=t)


# ── 1. Manda el dueño, y queda UNA sola verdad ────────────────────────────────

def test_el_planeador_respeta_al_runner_asignado_a_mano(
        proyecto_factory, usuario_factory):
    """El caso exacto de Oscar: el mandado es suyo y no tiene el permiso.

    Antes su parada se iba a la ruta del primer elegible y la tarea seguía
    diciendo su nombre: dos pantallas, dos respuestas.
    """
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    dueno = usuario_factory(rol="super_admin", email="dueno@lc.mx")
    otro = usuario_factory(rol="disenador", email="elegible@lc.mx")
    _hacer_runner(otro)  # el dueño a propósito NO es elegible
    _mandado(p, STAMPA, titulo="Recoger el NUC", runner=dueno)

    res = planear_dia(HOY, origen_modo="runner_abierta")

    assert res["sin_runner"] is False
    rutas = list(Ruta.objects.filter(fecha=HOY))
    assert [r.runner_id for r in rutas] == [dueno.pk]
    assert not Ruta.objects.filter(fecha=HOY, runner=otro).exists()


def test_lo_que_reparte_el_planeador_queda_escrito_en_la_tarea(
        proyecto_factory, usuario_factory):
    """La tarea es la fuente única del runner: si el reparto decide, ahí se anota."""
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="unico@lc.mx")
    _hacer_runner(a)
    m = _mandado(p, STAMPA)          # sin dueño
    assert m.tarea.runner_id is None

    planear_dia(HOY, origen_modo="runner_abierta")

    m.tarea.refresh_from_db()
    assert m.tarea.runner_id == a.pk
    # Marcado como automático: una edición a mano lo puede pisar después.
    assert m.tarea.runner_auto is True
    m.refresh_from_db()
    assert m.estado == "asignado"


def test_un_runner_que_puso_el_propio_reparto_si_es_re_repartible(
        proyecto_factory, usuario_factory):
    """`runner_auto=True` no es dueño: si lo fuera, «rehacer» nunca movería nada."""
    from apps.el_pizarron.planeador import _candidato, candidatos_del_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="auto@lc.mx")
    _mandado(p, STAMPA, runner=a, runner_auto=True)

    (candidato,) = [_candidato(m) for m in candidatos_del_dia(HOY)]
    assert candidato["runner"] is None


def test_al_dueno_sin_permiso_no_se_le_carga_trabajo_nuevo(
        proyecto_factory, usuario_factory):
    """Se le respeta lo suyo, pero el reparto no le encarga nada más."""
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    dueno = usuario_factory(rol="super_admin", email="d2@lc.mx")
    elegible = usuario_factory(rol="disenador", email="e2@lc.mx")
    _hacer_runner(elegible)
    _mandado(p, STAMPA, titulo="Suyo", runner=dueno)
    _mandado(p, NINOMEANDO, titulo="Libre")

    planear_dia(HOY, origen_modo="runner_abierta")

    del_dueno = Ruta.objects.get(fecha=HOY, runner=dueno)
    del_elegible = Ruta.objects.get(fecha=HOY, runner=elegible)
    assert [p.etiqueta for p in del_dueno.paradas.all()] == ["Suyo"]
    assert [p.etiqueta for p in del_elegible.paradas.all()] == ["Libre"]


def test_el_dueno_sin_permiso_se_reporta_para_avisarlo(
        proyecto_factory, usuario_factory):
    """No se le quita el mandado en silencio: la pantalla lo dice."""
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    dueno = usuario_factory(rol="super_admin", email="d3@lc.mx")
    _mandado(p, STAMPA, runner=dueno)

    res = planear_dia(HOY, origen_modo="runner_abierta")
    assert [u.pk for u in res["sin_permiso"]] == [dueno.pk]


def test_sin_nadie_elegible_pero_con_dueno_el_dia_se_planea_igual(
        proyecto_factory, usuario_factory):
    """Nadie tiene el permiso, pero el mandado ya tiene quién lo haga."""
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    dueno = usuario_factory(rol="super_admin", email="d4@lc.mx")
    _mandado(p, STAMPA, runner=dueno)

    res = planear_dia(HOY, origen_modo="runner_abierta")
    assert res["sin_runner"] is False
    assert Ruta.objects.filter(fecha=HOY, runner=dueno).exists()


def test_sin_nadie_y_sin_dueno_no_hay_nada_que_planear(
        proyecto_factory, usuario_factory):
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    usuario_factory(rol="super_admin", email="d5@lc.mx")
    _mandado(p, STAMPA)

    res = planear_dia(HOY, origen_modo="runner_abierta")
    assert res["sin_runner"] is True
    assert not Ruta.objects.filter(fecha=HOY).exists()


# ── 2. La pantalla dice la razón de verdad ────────────────────────────────────

def test_los_sueltos_se_separan_por_si_se_sabe_a_donde_van(
        proyecto_factory, usuario_factory):
    from apps.el_pizarron.planeador import sueltos_del_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    _mandado(p, STAMPA, titulo="Con destino")
    _mandado(p, None, titulo="Sin destino")

    res = sueltos_del_dia(HOY)
    assert [m.tarea.titulo for m in res["con_destino"]] == ["Con destino"]
    assert [m.tarea.titulo for m in res["sin_destino"]] == ["Sin destino"]


def test_el_panel_no_acusa_de_falta_de_destino_a_quien_lo_tiene(
        client, proyecto_factory, usuario_factory):
    """El bug de la captura: los dos tenían destino y salían como si no."""
    p = proyecto_factory(estado="en_proceso_diseno")
    jefe = usuario_factory(rol="super_admin", email="panel23@lc.mx")
    _mandado(p, STAMPA, titulo="Recoger el NUC")

    client.force_login(jefe)
    cuerpo = client.get(f"/rutas/?fecha={HOY.isoformat()}").content.decode()

    assert "Todavía sin repartir (1)" in cuerpo
    assert "Sin destino" not in cuerpo
    assert "no se sabe a dónde van" not in cuerpo
    # Y la casilla para rearmar el día está a la vista, junto al botón.
    assert 'name="rehacer"' in cuerpo
    assert "Rehacer desde cero" in cuerpo


def test_el_panel_si_avisa_del_que_de_verdad_no_tiene_destino(
        client, proyecto_factory, usuario_factory):
    p = proyecto_factory(estado="en_proceso_diseno")
    jefe = usuario_factory(rol="super_admin", email="panel24@lc.mx")
    _mandado(p, None, titulo="A saber dónde")

    client.force_login(jefe)
    cuerpo = client.get(f"/rutas/?fecha={HOY.isoformat()}").content.decode()

    assert "Sin destino (1)" in cuerpo
    assert "no se sabe a dónde van" in cuerpo
    assert "Todavía sin repartir" not in cuerpo


# ── 3. Rehacer el reparto ─────────────────────────────────────────────────────

def test_rehacer_tira_los_borradores_y_arma_el_dia_de_cero(
        proyecto_factory, usuario_factory):
    from apps.el_pizarron.models.ruta import ParadaRuta, Ruta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="reh@lc.mx")
    _hacer_runner(a)
    _mandado(p, STAMPA)
    _mandado(p, NINOMEANDO, titulo="Otra")

    planear_dia(HOY, origen_modo="runner_abierta")
    primera = Ruta.objects.get(fecha=HOY).pk

    planear_dia(HOY, origen_modo="runner_abierta", rehacer=True)

    assert Ruta.objects.filter(fecha=HOY).count() == 1
    assert Ruta.objects.get(fecha=HOY).pk != primera  # es una nueva, no la vieja
    assert ParadaRuta.objects.count() == 2             # y no se perdió ninguna


def test_rehacer_no_toca_una_ruta_ya_despachada(proyecto_factory, usuario_factory):
    """Una despachada ya está en manos de alguien y le llegó por correo."""
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import planear_dia, tirar_borradores

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="desp@lc.mx")
    _hacer_runner(a)
    _mandado(p, STAMPA)
    planear_dia(HOY, origen_modo="runner_abierta")
    Ruta.objects.filter(fecha=HOY).update(estado="despachada")

    assert tirar_borradores(HOY) == 0
    assert Ruta.objects.filter(fecha=HOY, estado="despachada").exists()


def test_rehacer_desde_la_pantalla(client, proyecto_factory, usuario_factory):
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    jefe = usuario_factory(rol="super_admin", email="rehp@lc.mx")
    a = usuario_factory(rol="disenador", email="rehr@lc.mx")
    _hacer_runner(a)
    _mandado(p, STAMPA)
    planear_dia(HOY, origen_modo="runner_abierta")
    vieja = Ruta.objects.get(fecha=HOY).pk

    client.force_login(jefe)
    r = client.post("/rutas/planear", {
        "fecha": HOY.isoformat(), "origen_modo": "runner_abierta", "rehacer": "1",
    })
    assert r.status_code == 302
    assert Ruta.objects.get(fecha=HOY).pk != vieja


# ── 4. «Mi ruta de hoy» es de hoy ─────────────────────────────────────────────

def test_mi_ruta_no_trae_mandados_archivados(proyecto_factory, usuario_factory):
    """La vuelta de Alex arrancaba con dos entregas archivadas de junio."""
    from apps.el_pizarron.ruta import ruta_de

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="arch@lc.mx")
    _hacer_runner(a)
    hoy = dt.date.today()
    _mandado(p, STAMPA, titulo="Vigente", fecha=hoy, runner=a)
    _mandado(p, NINOMEANDO, titulo="Archivada", fecha=hoy, runner=a, archivada=True)

    titulos = [x["titulo"] for x in ruta_de(a)["paradas"]]
    assert titulos == ["Vigente"]


def test_mi_ruta_no_trae_lo_de_la_semana_que_entra(proyecto_factory, usuario_factory):
    from apps.el_pizarron.ruta import ruta_de

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="prox@lc.mx")
    _hacer_runner(a)
    hoy = dt.date.today()
    _mandado(p, STAMPA, titulo="Hoy", fecha=hoy, runner=a)
    _mandado(p, NINOMEANDO, titulo="En ocho", fecha=hoy + dt.timedelta(days=7), runner=a)

    titulos = [x["titulo"] for x in ruta_de(a)["paradas"]]
    assert titulos == ["Hoy"]


def test_mi_ruta_si_trae_lo_atrasado_de_ayer(proyecto_factory, usuario_factory):
    """Lo de ayer que sigue abierto hay que hacerlo: no se esconde."""
    from apps.el_pizarron.ruta import ruta_de

    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="ayer@lc.mx")
    _hacer_runner(a)
    _mandado(p, STAMPA, titulo="De ayer",
             fecha=dt.date.today() - dt.timedelta(days=1), runner=a)

    assert [x["titulo"] for x in ruta_de(a)["paradas"]] == ["De ayer"]


# ── 5. El sello de «completada» en una tarea reabierta ────────────────────────

def test_el_sello_de_completada_no_aplica_a_una_tarea_reabierta(proyecto_factory):
    """En el Kanban salía «✓ Completada» sobre una tarjeta parada en Pendiente."""
    from apps.el_pizarron.models import Tarea
    from django.utils import timezone

    p = proyecto_factory(estado="en_proceso_diseno")
    t = Tarea.objects.create(
        proyecto=p, titulo="Reabierta", tipo="tarea", estado="pendiente",
        completada_en=timezone.now(),
    )
    assert t.completada_en is not None
    assert t.esta_terminada is False

    t.estado = "completada"
    assert t.esta_terminada is True


# ── 6. Fijar el destino te devuelve a donde estabas ───────────────────────────

def test_fijar_destino_regresa_a_donde_lo_llamaron(
        client, proyecto_factory, usuario_factory):
    """Se pide desde la lista de Mandados Y desde el planeador."""
    p = proyecto_factory(estado="en_proceso_diseno")
    jefe = usuario_factory(rol="super_admin", email="dest@lc.mx")
    m = _mandado(p, None, titulo="Sin destino")

    client.force_login(jefe)
    volver = f"/rutas/?fecha={HOY.isoformat()}"
    r = client.post(f"/mandados/{m.pk}/destino",
                    {"etiqueta": "Stampa", "volver": volver},
                    HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r["HX-Redirect"] == volver
    m.tarea.refresh_from_db()
    assert m.tarea.destino_etiqueta == "Stampa"


def test_fijar_destino_no_acepta_un_volver_de_otro_dominio(
        client, proyecto_factory, usuario_factory):
    p = proyecto_factory(estado="en_proceso_diseno")
    jefe = usuario_factory(rol="super_admin", email="dest2@lc.mx")
    m = _mandado(p, None, titulo="Sin destino")

    client.force_login(jefe)
    r = client.post(f"/mandados/{m.pk}/destino",
                    {"etiqueta": "Stampa", "volver": "https://evil.example/x"},
                    HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r["HX-Redirect"] == "/mandados/"
