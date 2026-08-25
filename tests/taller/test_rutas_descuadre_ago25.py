"""El descuadre que quedó vivo: la ruta dice una persona y el mandado dice otra.

Reporte de Oscar del 2026-08-25, con la evidencia en la mano: tres mandados con
**Runner: Oscar · asignado manualmente** y la vuelta del día armada a nombre de
**Alex**, con dos de esos mandados dentro. El tercero no aparecía en ninguna
parte.

Diagnosticado contra producción, salieron tres cosas distintas:

1. **El descuadre no tenía salida.** `S-Rutas-Dueno` (2026-08-23 22:59) evitó
   CREAR nuevas contradicciones, pero la ruta de ese día se armó a las 22:23 —
   treinta y seis minutos antes— y quedó fija: `candidatos_del_dia` excluye lo
   que ya está ruteado y `tirar_borradores` no toca una ruta despachada. Se
   apretaba «Rehacer desde cero», no pasaba nada, y nada lo explicaba. Encima el
   correo salió: Alex recibió una vuelta que no era suya.
2. **Un reparto cancelado dejaba su tarea viva y muda.** El tercer mandado
   («Entrega de playeras») estaba `cancelado` con la tarea en `pendiente`: se
   veía Pendiente y Atrasada, el planeador la excluía para siempre y ninguna
   pantalla lo decía. Y no había forma de deshacerlo: `sincronizar_mandado`
   respeta la cancelación «para siempre».
3. **La regla del dueño estaba escrita una sola vez, y así se queda.** Vive en
   `dueno_de` porque las dos mitades del planeador la necesitan; dos copias es
   exactamente cómo vuelven las dos verdades.
"""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

HOY = dt.date(2026, 8, 23)

# Los puntos reales del caso, para que un fallo se lea con sentido.
STAMPA = (19.350313, -99.298189)
NINOMEANDO = (19.371382, -99.267477)
OFICINA = (19.443446, -99.207820)


def _hacer_runner(*usuarios):
    from cuentas.models.rol import Rol
    r = Rol.objects.get(nombre="Runner")
    for u in usuarios:
        u.roles_extra.add(r)


def _mandado(proyecto, punto, *, titulo="Entregar lona", fecha=HOY,
             runner=None, runner_auto=False, archivada=False,
             estado_tarea="pendiente"):
    from apps.el_pizarron.models import Mandado, Tarea
    t = Tarea.objects.create(
        proyecto=proyecto, titulo=titulo, tipo="entrega", estado=estado_tarea,
        fecha_compromiso=fecha, archivada=archivada,
        destino_lat=punto[0] if punto else None,
        destino_lng=punto[1] if punto else None,
        destino_etiqueta=titulo if punto else "",
        runner=runner, runner_auto=runner_auto, requiere_runner=bool(runner),
    )
    return Mandado.objects.get(tarea=t)


def _ruta_ajena(fecha, runner_de_la_ruta, mandados, *, estado="despachada"):
    """El fósil: una ruta a nombre de alguien con paradas de otro.

    Es lo que dejó el planeador viejo, así que se arma a mano — hoy ya no hay
    forma de producirlo desde el código.
    """
    from apps.el_pizarron.models.ruta import ParadaRuta, Ruta
    ruta = Ruta.objects.create(
        fecha=fecha, runner=runner_de_la_ruta, estado=estado,
        origen_modo="sede_redonda",
        origen_lat=OFICINA[0], origen_lng=OFICINA[1], origen_etiqueta="la oficina",
    )
    for i, m in enumerate(mandados, start=1):
        ParadaRuta.objects.create(
            ruta=ruta, mandado=m, orden=i,
            lat=m.tarea.destino_lat, lng=m.tarea.destino_lng,
            etiqueta=m.tarea.destino_etiqueta,
        )
    return ruta


# ── 1. Se detecta el descuadre ────────────────────────────────────────────────

def test_se_detecta_la_parada_en_la_ruta_de_otro(proyecto_factory, usuario_factory):
    """El caso exacto de las capturas: dos paradas de Oscar en la ruta de Alex."""
    from apps.el_pizarron.planeador import paradas_con_dueno_ajeno

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    alex = usuario_factory(rol="disenador", email="alex@lc.mx")
    _hacer_runner(alex, oscar)
    m1 = _mandado(p, NINOMEANDO, titulo="Test", runner=oscar)
    m2 = _mandado(p, STAMPA, titulo="Recoger el NUC", runner=oscar)
    _ruta_ajena(HOY, alex, [m1, m2])

    fuera = paradas_con_dueno_ajeno(HOY)
    assert len(fuera) == 2
    assert {d.pk for _, d in fuera} == {oscar.pk}


def test_un_runner_que_puso_el_reparto_no_cuenta_como_dueno(
        proyecto_factory, usuario_factory):
    """`runner_auto=True` es el sistema, no una persona: si contara como dueño,
    «rehacer desde cero» nunca podría mover una parada."""
    from apps.el_pizarron.planeador import paradas_con_dueno_ajeno

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    alex = usuario_factory(rol="disenador", email="alex@lc.mx")
    _hacer_runner(alex, oscar)
    m = _mandado(p, STAMPA, runner=oscar, runner_auto=True)
    _ruta_ajena(HOY, alex, [m])

    assert paradas_con_dueno_ajeno(HOY) == []


def test_un_mandado_ya_cerrado_no_es_descuadre(proyecto_factory, usuario_factory):
    """Entregado o cancelado ya no le toca a nadie: moverlo no significa nada."""
    from apps.el_pizarron import mandados as svc
    from apps.el_pizarron.planeador import paradas_con_dueno_ajeno

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    alex = usuario_factory(rol="disenador", email="alex@lc.mx")
    _hacer_runner(alex, oscar)
    m = _mandado(p, STAMPA, runner=oscar)
    _ruta_ajena(HOY, alex, [m])
    svc.cancelar(m)

    assert paradas_con_dueno_ajeno(HOY) == []


# ── 2. La parada vuelve con su dueño ──────────────────────────────────────────

def test_la_parada_vuelve_a_la_ruta_de_su_dueno(proyecto_factory, usuario_factory):
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import devolver_a_su_dueno

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    alex = usuario_factory(rol="disenador", email="alex@lc.mx")
    _hacer_runner(alex, oscar)
    m1 = _mandado(p, NINOMEANDO, titulo="Test", runner=oscar)
    m2 = _mandado(p, STAMPA, titulo="Recoger el NUC", runner=oscar)
    _ruta_ajena(HOY, alex, [m1, m2])

    movidas = devolver_a_su_dueno(HOY, origen_modo="runner_abierta")

    assert len(movidas) == 2
    ruta_oscar = Ruta.objects.get(fecha=HOY, runner=oscar, estado__in=("borrador", "despachada"))
    assert {p_.mandado_id for p_ in ruta_oscar.paradas.all()} == {m1.pk, m2.pk}


def test_la_ruta_que_se_queda_vacia_se_cancela(proyecto_factory, usuario_factory):
    """Una ruta viva sin paradas en la pantalla no significa nada."""
    from apps.el_pizarron.planeador import devolver_a_su_dueno

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    alex = usuario_factory(rol="disenador", email="alex@lc.mx")
    _hacer_runner(alex, oscar)
    m = _mandado(p, STAMPA, runner=oscar)
    ruta_alex = _ruta_ajena(HOY, alex, [m])

    devolver_a_su_dueno(HOY, origen_modo="runner_abierta")

    ruta_alex.refresh_from_db()
    assert ruta_alex.estado == "cancelada"


def test_reporta_que_la_ruta_ya_estaba_despachada(proyecto_factory, usuario_factory):
    """Si ya salió por correo, a esa persona hay que avisarle a mano: el dato
    viaja en el resultado para que la pantalla lo pueda decir."""
    from apps.el_pizarron.planeador import devolver_a_su_dueno

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    alex = usuario_factory(rol="disenador", email="alex@lc.mx")
    _hacer_runner(alex, oscar)
    m = _mandado(p, STAMPA, titulo="Recoger el NUC", runner=oscar)
    _ruta_ajena(HOY, alex, [m], estado="despachada")

    movidas = devolver_a_su_dueno(HOY, origen_modo="runner_abierta")

    assert movidas[0]["ya_despachada"] is True
    assert movidas[0]["de"].pk == alex.pk
    assert movidas[0]["a"].pk == oscar.pk
    assert movidas[0]["titulo"] == "Recoger el NUC"


def test_devolver_es_idempotente(proyecto_factory, usuario_factory):
    from apps.el_pizarron.planeador import devolver_a_su_dueno

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    alex = usuario_factory(rol="disenador", email="alex@lc.mx")
    _hacer_runner(alex, oscar)
    m = _mandado(p, STAMPA, runner=oscar)
    _ruta_ajena(HOY, alex, [m])

    assert len(devolver_a_su_dueno(HOY, origen_modo="runner_abierta")) == 1
    assert devolver_a_su_dueno(HOY, origen_modo="runner_abierta") == []


def test_planear_el_dia_endereza_antes_de_repartir(proyecto_factory, usuario_factory):
    """Es el botón que Oscar apretaba sin que pasara nada."""
    from apps.el_pizarron.models.ruta import Ruta
    from apps.el_pizarron.planeador import planear_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    alex = usuario_factory(rol="disenador", email="alex@lc.mx")
    _hacer_runner(alex, oscar)
    m = _mandado(p, STAMPA, titulo="Recoger el NUC", runner=oscar)
    _ruta_ajena(HOY, alex, [m])

    res = planear_dia(HOY, origen_modo="runner_abierta", rehacer=True)

    assert len(res["reconciliadas"]) == 1
    ruta_oscar = Ruta.objects.get(fecha=HOY, runner=oscar,
                                 estado__in=("borrador", "despachada"))
    assert ruta_oscar.paradas.filter(mandado=m).exists()


# ── 3. El reparto cancelado deja de ser invisible ─────────────────────────────

def test_un_reparto_cancelado_con_tarea_viva_se_reporta(
        proyecto_factory, usuario_factory):
    """El tercer mandado de las capturas: cancelado, pero la tarea Pendiente."""
    from apps.el_pizarron import mandados as svc
    from apps.el_pizarron.planeador import repartos_cancelados, sueltos_del_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    m = _mandado(p, OFICINA, titulo="Entrega de playeras a NoKo Devs", runner=oscar)
    svc.cancelar(m)

    assert [x.pk for x in repartos_cancelados(HOY)] == [m.pk]
    sueltos = sueltos_del_dia(HOY)
    assert [x.pk for x in sueltos["cancelados"]] == [m.pk]
    # Y no se cuenta dos veces: los otros dos grupos son de mandados vivos.
    assert m.pk not in {x.pk for x in sueltos["con_destino"]}
    assert m.pk not in {x.pk for x in sueltos["sin_destino"]}


def test_una_tarea_ya_terminada_no_se_reporta(proyecto_factory, usuario_factory):
    """Ahí el reparto cancelado no contradice nada."""
    from apps.el_pizarron import mandados as svc
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    from apps.el_pizarron.planeador import repartos_cancelados

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    terminal = next(iter(slugs_terminales_tarea()))
    m = _mandado(p, OFICINA, runner=oscar)
    svc.cancelar(m)
    m.tarea.estado = terminal
    m.tarea.save(update_fields=["estado"])

    assert repartos_cancelados(HOY) == []


def test_una_tarea_archivada_no_se_reporta(proyecto_factory, usuario_factory):
    from apps.el_pizarron import mandados as svc
    from apps.el_pizarron.planeador import repartos_cancelados

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    m = _mandado(p, OFICINA, runner=oscar, archivada=True)
    svc.cancelar(m)

    assert repartos_cancelados(HOY) == []


# ── 4. Reactivar: la salida que no existía ────────────────────────────────────

def test_reactivar_devuelve_el_mandado_a_la_vida(proyecto_factory, usuario_factory):
    from apps.el_pizarron import mandados as svc
    from apps.el_pizarron.planeador import candidatos_del_dia

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    m = _mandado(p, OFICINA, runner=oscar)
    svc.cancelar(m)
    assert m.pk not in {c.pk for c in candidatos_del_dia(HOY)}

    svc.reactivar(m)
    m.refresh_from_db()

    assert m.estado == "asignado"  # tiene runner, la tarea está viva
    assert m.cancelado_en is None
    # Y vuelve a entrar al planeador, que es el punto.
    assert m.pk in {c.pk for c in candidatos_del_dia(HOY)}


def test_reactivar_no_toca_un_mandado_que_no_esta_cancelado(
        proyecto_factory, usuario_factory):
    from apps.el_pizarron import mandados as svc

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    m = _mandado(p, OFICINA, runner=oscar)
    svc.marcar_en_camino(m)

    svc.reactivar(m)
    m.refresh_from_db()
    assert m.estado == "en_camino"


# ── 5. Las pantallas lo dicen ─────────────────────────────────────────────────

def test_el_panel_avisa_del_descuadre_sin_picar_nada(
        client, proyecto_factory, usuario_factory):
    """Nadie va a apretar «Planear el día» para arreglar algo que no sabe que
    está roto: la ruta se ve perfectamente bien."""
    from django.urls import reverse

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    alex = usuario_factory(rol="disenador", email="alex@lc.mx")
    _hacer_runner(alex, oscar)
    m = _mandado(p, STAMPA, titulo="Recoger el NUC", runner=oscar)
    _ruta_ajena(HOY, alex, [m])

    client.force_login(oscar)
    resp = client.get(f"{reverse('rutas-panel')}?fecha={HOY.isoformat()}")
    cuerpo = resp.content.decode()

    assert resp.status_code == 200
    assert len(resp.context["descuadres"]) == 1
    assert "no es su dueño" in cuerpo
    assert "ya se despachó por correo" in cuerpo


def test_el_panel_muestra_los_repartos_cancelados_con_su_boton(
        client, proyecto_factory, usuario_factory):
    from apps.el_pizarron import mandados as svc
    from django.urls import reverse

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    _hacer_runner(oscar)
    m = _mandado(p, OFICINA, titulo="Entrega de playeras a NoKo Devs", runner=oscar)
    svc.cancelar(m)

    client.force_login(oscar)
    resp = client.get(f"{reverse('rutas-panel')}?fecha={HOY.isoformat()}")
    cuerpo = resp.content.decode()

    assert [x.pk for x in resp.context["cancelados"]] == [m.pk]
    assert "Con el reparto cancelado" in cuerpo
    assert "reactivar" in cuerpo


def test_reactivar_desde_el_panel_regresa_al_panel(
        client, proyecto_factory, usuario_factory):
    """El botón vive en el planeador: mandar a la lista de Mandados saca al
    usuario de donde estaba trabajando."""
    from apps.el_pizarron import mandados as svc
    from django.urls import reverse

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    _hacer_runner(oscar)
    m = _mandado(p, OFICINA, runner=oscar)
    svc.cancelar(m)
    volver = f"{reverse('rutas-panel')}?fecha={HOY.isoformat()}"

    client.force_login(oscar)
    resp = client.post(reverse("mandado-avanzar", args=[m.pk]),
                       {"accion": "reactivar", "volver": volver})

    assert resp.status_code == 302
    assert resp["Location"] == volver
    m.refresh_from_db()
    assert m.estado == "asignado"


def test_el_detalle_de_la_tarea_dice_que_el_reparto_esta_cancelado(
        client, proyecto_factory, usuario_factory):
    """La pantalla de la captura: se veía «Pendiente» y nada más."""
    from apps.el_pizarron import mandados as svc
    from django.urls import reverse

    p = proyecto_factory(estado="en_proceso_diseno")
    oscar = usuario_factory(rol="super_admin", email="oscar@lc.mx")
    m = _mandado(p, OFICINA, titulo="Entrega de playeras a NoKo Devs", runner=oscar)
    svc.cancelar(m)

    client.force_login(oscar)
    resp = client.get(reverse("pizarron-detalle-tarea", args=[m.tarea.pk]))
    cuerpo = resp.content.decode()

    assert resp.status_code == 200
    assert "El reparto está" in cuerpo
    assert "no va a entrar al" in cuerpo
