"""El planeador de rutas — reparte los mandados del día y los pone en orden.

S-Planeador-Rutas (Oscar 2026-08-22): «ya tenemos que lanzar el planeador de
rutas». Es el paso siguiente de `ruta.py`, que ya resolvía «mi ruta de hoy» al
vuelo y los botones para mandarla a Waze / Google Maps / Apple Maps. Aquí la
ruta **se guarda**, se reparte entre varios runners y respeta las citas.

Las cuatro decisiones de Oscar, y cómo se cumplen:

1. **Ruta guardada por runner y día** → se persiste en `Ruta`/`ParadaRuta`; el
   candado de «una sola viva» vive en la base, no en este archivo.
2. **Reparte entre los runners disponibles** → `_repartir`, por inserción más
   barata con tope de carga, reusando los pesos de `runners.evaluar_runners`
   para que la elección se pueda explicar con palabras.
3. **La hora es cita fija** → `_ordenar_con_citas`: las paradas con hora son
   ANCLAS en orden de reloj y el 2-opt sólo reacomoda DENTRO de los tramos que
   quedan entre ellas. Por construcción no existe un reordenamiento que mueva
   una cita de lugar.
4. **Los dos modos de origen** → `sede_redonda` (sale de la sede y vuelve) y
   `runner_abierta` (sale de donde está el runner y termina en la última
   parada).

Las distancias salen del mapa (OSRM en el NUC) y se piden **de una sola vez**:
`ruteo.Tabla` trae la matriz completa del día —los orígenes de cada runner y
todas las paradas— y luego se consulta como un diccionario. Antes se preguntaba
de un par a la vez desde dentro de los bucles de optimización, que para doce
paradas entre tres runners eran **3,508 consultas** (medido el 2026-08-24);
ahora es una. Si el mapa no contesta, la Tabla se arma con el haversine de El
Checador y el planeador sigue planeando: pierde precisión, no funcionalidad.

Las horas salen de las duraciones que da el mapa —que sí saben de tipos de
calle y límites de velocidad— multiplicadas por el factor de tráfico de
Ajustes → Rutas, porque OSRM las calcula a calle libre. Sólo cuando no hay
duración se cae a repartir los metros entre la velocidad promedio configurada.

Ojo con los nombres: `apps.el_pizarron.ruta` es el ayudante de V1 (orden al
vuelo + enlaces a las apps) y `apps.el_pizarron.models.ruta` son los modelos.
Este módulo usa los dos.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

logger = logging.getLogger(__name__)

# Los cuatro supuestos con los que se estima la vuelta. Se editan en La Gerencia
# → Ajustes → Rutas (`ajustes.ConfiguracionRutas`); lo de aquí abajo es el
# RESPALDO, para que el planeador siga funcionando si la tabla todavía no existe
# o la base no contesta. Nunca se leen directo: se pide con `_cfg()`.
VELOCIDAD_KMH = 25.0
MINUTOS_POR_PARADA = 10
HORA_INICIO_DEFAULT = time(9, 0)
MAX_PARADAS_POR_RUTA = 9

#: Cuánto se recuerda la configuración antes de volver a preguntarla. Planear un
#: día son decenas de llamadas a `_cfg()`; sin esto, decenas de consultas.
_CACHE_SEGUNDOS = 60
_cache: dict = {"hasta": None, "valor": None}


def _cfg():
    """Los supuestos vigentes, como objeto con los cuatro atributos.

    Defensivo a propósito: si la tabla no está migrada, la base no contesta o el
    valor viene absurdo, se cae a los respaldos de arriba. Un planeador que se
    niega a planear porque no pudo leer una preferencia no le sirve a nadie.
    """
    import time as _t
    from types import SimpleNamespace

    ahora = _t.monotonic()
    if _cache["valor"] is not None and _cache["hasta"] and ahora < _cache["hasta"]:
        return _cache["valor"]

    valor = SimpleNamespace(
        velocidad_kmh=VELOCIDAD_KMH,
        minutos_por_parada=MINUTOS_POR_PARADA,
        hora_inicio=HORA_INICIO_DEFAULT,
        max_paradas=MAX_PARADAS_POR_RUTA,
    )
    try:
        from ajustes.models import ConfiguracionRutas
        cfg = ConfiguracionRutas.obtener()
        velocidad = float(cfg.velocidad_kmh or 0)
        valor = SimpleNamespace(
            # Una velocidad en cero dividiría entre cero al estimar tiempos.
            velocidad_kmh=velocidad if velocidad > 0 else VELOCIDAD_KMH,
            minutos_por_parada=int(cfg.minutos_por_parada or 0),
            hora_inicio=cfg.hora_inicio or HORA_INICIO_DEFAULT,
            max_paradas=max(1, int(cfg.max_paradas_por_ruta or MAX_PARADAS_POR_RUTA)),
        )
    except Exception:  # noqa: BLE001 — sin configuración, se planea con los respaldos
        logger.debug("no se pudo leer la configuración de rutas", exc_info=True)

    _cache.update(hasta=ahora + _CACHE_SEGUNDOS, valor=valor)
    return valor


def olvidar_configuracion() -> None:
    """Tira el recuerdo de la configuración. La llama el GUI al guardar, para que
    el cambio se note sin esperar el minuto de la caché."""
    _cache.update(hasta=None, valor=None)


# ── Candidatos ────────────────────────────────────────────────────────────────

def candidatos_del_dia(fecha):
    """Mandados que hay que repartir ese día y todavía no están en una ruta viva.

    Se excluyen los cerrados (entregado/cancelado) y los que ya pertenecen a una
    ruta viva: replanear no debe duplicar una parada que alguien ya trae.
    """
    from apps.el_pizarron.models.mandado import Mandado
    from apps.el_pizarron.models.ruta import ESTADOS_RUTA_VIVOS

    ya_ruteados = set(
        _ParadaRuta().objects.filter(
            ruta__fecha=fecha, ruta__estado__in=ESTADOS_RUTA_VIVOS,
        ).values_list("mandado_id", flat=True)
    )
    qs = (
        Mandado.objects
        .exclude(estado__in=("entregado", "cancelado"))
        .filter(tarea__fecha_compromiso=fecha, tarea__archivada=False)
        .select_related("tarea", "tarea__proyecto", "tarea__proyecto__cliente")
    )
    return [m for m in qs if m.pk not in ya_ruteados]


def _ParadaRuta():
    from apps.el_pizarron.models.ruta import ParadaRuta
    return ParadaRuta


def asignar_runner(tarea, runner, *, actor=None, auto: bool = True):
    """Escribe el runner que decidió el reparto. Envoltura perezosa de
    `runners.asignar_runner` (importar arriba haría un ciclo)."""
    from apps.el_pizarron.runners import asignar_runner as _asignar
    return _asignar(tarea, runner, actor=actor, auto=auto)


def _punto_de(mandado):
    """Destino del mandado (pin propio o la última visita al cliente)."""
    from apps.el_pizarron.runners import ubicacion_destino_de_tarea
    try:
        return ubicacion_destino_de_tarea(mandado.tarea)
    except Exception:  # noqa: BLE001
        logger.warning("no se pudo ubicar el mandado %s", mandado.pk, exc_info=True)
        return None


def _etiqueta_de(mandado) -> str:
    tarea = mandado.tarea
    lugar = (getattr(tarea, "destino_etiqueta", "") or "").strip()
    if lugar:
        return lugar[:200]
    proyecto = getattr(tarea, "proyecto", None)
    cliente = getattr(proyecto, "cliente", None)
    if cliente is not None:
        return (cliente.razon_social or "")[:200]
    return (tarea.titulo or "")[:200]


def _candidato(mandado) -> dict:
    """La parada como diccionario, en la forma que ya usa `ruta.py`.

    `runner` es el DUEÑO: quien fue puesto A MANO en la tarea. El reparto lo
    respeta y no se lo quita (ver `planear_dia`).

    Un runner que puso el propio reparto (`runner_auto=True`) NO cuenta como
    dueño: si contara, «rehacer desde cero» nunca podría mover una parada de
    persona, porque el primer reparto ya habría dejado su nombre escrito.
    """
    tarea = mandado.tarea
    a_mano = bool(getattr(tarea, "runner_id", None)) and not getattr(tarea, "runner_auto", False)
    punto = _punto_de(mandado)
    return {
        "mandado": mandado,
        "runner": tarea.runner if a_mano else None,
        "lat": punto[0] if punto else None,
        "lng": punto[1] if punto else None,
        "etiqueta": _etiqueta_de(mandado),
        "hora": getattr(mandado.tarea, "hora", None),
    }


def sueltos_del_dia(fecha) -> dict:
    """Los mandados del día que todavía no están en una ruta, separados por si se
    sabe a dónde van.

    Son dos problemas distintos y la pantalla los tiene que decir distinto: uno
    se arregla apretando «Planear el día» y el otro poniéndole el destino. Antes
    se mostraban juntos bajo «no se sabe a dónde van», así que un mandado con su
    destino perfectamente puesto salía acusado de no tenerlo — el reporte de
    Oscar del 2026-08-23.
    """
    con, sin = [], []
    for mandado in candidatos_del_dia(fecha):
        (con if _punto_de(mandado) else sin).append(mandado)
    return {"con_destino": con, "sin_destino": sin}


# ── Distancias ────────────────────────────────────────────────────────────────

def _d(a, b, tabla=None) -> float:
    """Metros entre dos puntos; 0 si alguno no se puede ubicar.

    Con `tabla` es una consulta a un diccionario; sin ella pega al mapa, que es
    lo caro. Todo lo que corre dentro de un bucle de optimización DEBE pasarla.
    """
    if not a or not b:
        return 0.0
    if tabla is not None:
        return tabla.metros(a, b)
    from apps.el_pizarron.ruta import _distancia
    return _distancia(a, b) or 0.0


def tabla_de(puntos):
    """La matriz de un conjunto de puntos, en una sola consulta al mapa."""
    from lib import ruteo
    return ruteo.Tabla([p for p in puntos if p])


def _pt(parada):
    lat, lng = parada.get("lat"), parada.get("lng")
    return (lat, lng) if lat is not None and lng is not None else None


def largo_de(origen, secuencia, *, cerrar: bool, tabla=None) -> float:
    """Metros del recorrido completo en ese orden."""
    puntos = [p for p in (_pt(x) for x in secuencia) if p]
    if origen:
        puntos.insert(0, origen)
    if len(puntos) < 2:
        return 0.0
    total = sum(_d(a, b, tabla) for a, b in zip(puntos, puntos[1:], strict=False))
    if cerrar and origen and puntos[-1] != origen:
        total += _d(puntos[-1], origen, tabla)
    return total


# ── Orden con las citas como ancla ────────────────────────────────────────────

def _tramos(secuencia):
    """Parte la secuencia en tramos de paradas libres separados por anclas.

    Devuelve `[(desde, hasta)]` con índices de rebanada de cada tramo movible.
    Las anclas quedan fuera de los tramos: nunca se reordenan.
    """
    idx_anclas = [i for i, p in enumerate(secuencia) if p.get("hora")]
    tramos, ini = [], 0
    for i in idx_anclas:
        if i > ini:
            tramos.append((ini, i))
        ini = i + 1
    if ini < len(secuencia):
        tramos.append((ini, len(secuencia)))
    return tramos


def _dos_opt_tramo(origen, secuencia, desde, hasta, *, cerrar, tabla=None):
    """2-opt dentro de un tramo, con los extremos clavados.

    Invierte sub-rutas mientras el recorrido total baje. Como sólo toca
    `[desde:hasta]` y ahí no hay anclas, ninguna cita se puede mover.
    """
    mejor = secuencia[:]
    mejor_largo = largo_de(origen, mejor, cerrar=cerrar, tabla=tabla)
    hubo_mejora = True
    while hubo_mejora:
        hubo_mejora = False
        for i in range(desde, hasta - 1):
            for j in range(i + 1, hasta):
                cand = mejor[:]
                cand[i:j + 1] = reversed(cand[i:j + 1])
                largo = largo_de(origen, cand, cerrar=cerrar, tabla=tabla)
                if largo < mejor_largo - 0.5:  # medio metro: evita zumbido
                    mejor, mejor_largo = cand, largo
                    hubo_mejora = True
    return mejor


def _ordenar_con_citas(origen, paradas, *, cerrar: bool, tabla=None):
    """Ordena respetando las citas: anclas en orden de reloj, el resto donde
    menos estorbe, y pulido sólo dentro de los tramos libres."""
    ubicables = [p for p in paradas if _pt(p)]
    sin_ubicar = [p for p in paradas if not _pt(p)]

    anclas = sorted((p for p in ubicables if p.get("hora")), key=lambda p: p["hora"])
    libres = [p for p in ubicables if not p.get("hora")]

    secuencia = list(anclas)
    # Cada parada libre entra donde el recorrido crezca menos. Se procesan de la
    # más lejana al origen a la más cercana: mete primero las difíciles, que son
    # las que de verdad condicionan el trazo.
    libres.sort(key=lambda p: -_d(origen, _pt(p), tabla) if origen else 0)
    for libre in libres:
        mejor_pos, mejor_costo = len(secuencia), None
        for pos in range(len(secuencia) + 1):
            cand = secuencia[:pos] + [libre] + secuencia[pos:]
            costo = largo_de(origen, cand, cerrar=cerrar, tabla=tabla)
            if mejor_costo is None or costo < mejor_costo:
                mejor_pos, mejor_costo = pos, costo
        secuencia.insert(mejor_pos, libre)

    for desde, hasta in _tramos(secuencia):
        if hasta - desde > 1:
            secuencia = _dos_opt_tramo(origen, secuencia, desde, hasta,
                                       cerrar=cerrar, tabla=tabla)

    # Las que no se pueden ubicar no se pierden: van al final, en su orden.
    return secuencia + sin_ubicar


# ── Horas estimadas ───────────────────────────────────────────────────────────

def _minutos_de(metros: float) -> int:
    """Minutos a la velocidad promedio configurada. El respaldo de siempre."""
    return int(round((metros / 1000.0) / _cfg().velocidad_kmh * 60)) if metros else 0


def _minutos_viaje(a, b, metros: float, tabla=None) -> int:
    """Cuánto se tarda entre dos puntos.

    Con la duración del mapa cuando la hay: sabe de tipos de calle y límites de
    velocidad, y ya viene multiplicada por el factor de tráfico. Repartir los
    metros entre una velocidad plana ignora todo eso — medido Zócalo→Satélite,
    el mapa dice 24 minutos y la velocidad plana decía 49.
    """
    if tabla is not None and a and b:
        segundos = tabla.segundos(a, b)
        if segundos is not None:
            return int(round(segundos / 60.0))
    return _minutos_de(metros)


def estimar_horas(origen, secuencia, *, inicio: time | None = None, tabla=None):
    """Llegada estimada a cada parada. Devuelve `[(parada, hora, metros)]`.

    Si una parada tiene cita y se llega antes, se espera: la hora que se muestra
    es la de la cita, no la del reloj del viaje. Si se llega después, se muestra
    la real — mentir aquí sería peor que llegar tarde.
    """
    anclas = [p["hora"] for p in secuencia if p.get("hora")]
    arranque = inicio or _cfg().hora_inicio
    if anclas:
        # Si la primera cita es temprano, la vuelta empieza antes.
        arranque = min([arranque, *anclas])

    base = datetime(2000, 1, 1, arranque.hour, arranque.minute)
    reloj = base
    anterior = origen
    salida = []
    for parada in secuencia:
        punto = _pt(parada)
        metros = _d(anterior, punto, tabla) if (anterior and punto) else 0.0
        reloj += timedelta(minutes=_minutos_viaje(anterior, punto, metros, tabla))
        cita = parada.get("hora")
        if cita:
            hora_cita = datetime(2000, 1, 1, cita.hour, cita.minute)
            if reloj < hora_cita:
                reloj = hora_cita  # llegó antes: espera a su cita
        salida.append((parada, reloj.time(), int(metros)))
        reloj += timedelta(minutes=_cfg().minutos_por_parada)
        if punto:
            anterior = punto
    return salida


# ── Reparto entre runners ─────────────────────────────────────────────────────

def _origen_para(runner, modo: str, sede):
    """(punto, etiqueta) de donde arranca ese runner, según el modo."""
    if modo == "sede_redonda":
        if sede is not None and sede.tiene_pin:
            return (float(sede.lat), float(sede.lng)), sede.nombre
        return None, (sede.nombre if sede is not None else "")
    from apps.el_pizarron.runners import ubicacion_actual_de
    try:
        pos = ubicacion_actual_de(runner)
    except Exception:  # noqa: BLE001
        pos = None
    if pos:
        return (pos[0], pos[1]), "Donde está el runner"
    # Sin posición conocida no se inventa: la ruta queda sin origen y el orden
    # se encadena entre paradas, que sigue siendo útil.
    return None, ""


def _repartir(candidatos, contextos, *, tabla=None):
    """Reparte las paradas entre los runners por inserción más barata.

    `contextos` es `{runner_pk: {"runner", "origen", "cerrar", "paradas", "acepta"}}`.
    Cada parada se le da al runner cuya ruta crece menos, con tope de carga para
    que no se le apile todo al que quedó más cerca. Las citas se reparten
    primero: son las que no admiten acomodo.

    Sólo se le carga trabajo nuevo a los contextos con `acepta=True` (los runners
    elegibles). Un contexto de dueño-no-elegible existe para conservar lo que ya
    es suyo, no para recibir más.
    """
    if not contextos:
        return []

    def _peso_cita(p):
        return (0, p["hora"]) if p.get("hora") else (1, time(23, 59))

    tope = _cfg().max_paradas
    pendientes = sorted(candidatos, key=_peso_cita)
    sobrantes = []
    for parada in pendientes:
        mejor, mejor_costo = None, None
        for ctx in contextos.values():
            if not ctx.get("acepta", True):
                continue
            if len(ctx["paradas"]) >= tope:
                continue
            antes = largo_de(ctx["origen"], ctx["paradas"],
                             cerrar=ctx["cerrar"], tabla=tabla)
            tentativa = _ordenar_con_citas(
                ctx["origen"], [*ctx["paradas"], parada], cerrar=ctx["cerrar"],
                tabla=tabla,
            )
            despues = largo_de(ctx["origen"], tentativa,
                               cerrar=ctx["cerrar"], tabla=tabla)
            # El costo es lo que CRECE la ruta, más un empujón por carga para
            # que el reparto quede parejo y no todo con el más cercano.
            costo = (despues - antes) + len(ctx["paradas"]) * 250
            if mejor_costo is None or costo < mejor_costo:
                mejor, mejor_costo = ctx, costo
        if mejor is None:
            sobrantes.append(parada)  # todos llenos
            continue
        mejor["paradas"].append(parada)

    for ctx in contextos.values():
        ctx["paradas"] = _ordenar_con_citas(
            ctx["origen"], ctx["paradas"], cerrar=ctx["cerrar"], tabla=tabla,
        )
    return sobrantes


# ── Guardar el plan ───────────────────────────────────────────────────────────

def tirar_borradores(fecha) -> int:
    """Borra los borradores del día para poder rehacer el reparto desde cero.

    SÓLO borradores: una ruta despachada ya está en manos de alguien —y le llegó
    por correo—, así que borrarla sería quitarle el trabajo sin avisar. Las
    paradas se van en cascada.

    Existe porque `candidatos_del_dia` excluye a propósito lo que ya está
    ruteado: sin esto, un reparto que salió mal no se podía rehacer más que
    cancelando cada ruta a mano.
    """
    from apps.el_pizarron.models.ruta import Ruta
    borradores = list(Ruta.objects.filter(fecha=fecha, estado="borrador"))
    for ruta in borradores:
        ruta.delete()
    return len(borradores)


def planear_dia(fecha, *, origen_modo: str = "sede_redonda", sede=None,
                runners=None, actor=None, rehacer: bool = False) -> dict:
    """Arma (o rearma) las rutas del día y las guarda.

    Devuelve `{rutas, sobrantes, sin_ubicar, sin_runner, sin_permiso}`. No lanza:
    si algo falla al ubicar una parada, ésa queda fuera y las demás se planean
    igual.

    **Manda el runner que ya trae el mandado a mano** (decisión de Oscar,
    2026-08-23): su parada va a SU ruta aunque no tenga el permiso de recibir
    mandados, y el reparto no se la quita. Lo que se reparte entre los elegibles es sólo lo que
    va sin dueño — y a eso sí se le ESCRIBE el runner en la tarea, para que la
    lista de Mandados y el planeador no digan cosas distintas. Antes el planeador
    ignoraba al dueño y armaba la ruta a nombre de otro sin tocar la tarea: dos
    verdades sobre quién hace la entrega.

    Idempotente por diseño: los mandados que ya están en una ruta viva no se
    vuelven a repartir (`candidatos_del_dia` los excluye), así que replanear el
    mismo día agrega lo nuevo en vez de duplicar lo que ya se despachó. Con
    `rehacer=True` se tiran primero los borradores y el día se arma de cero.
    """
    from django.db import transaction

    from lib.permisos import usuarios_runner

    if rehacer:
        tirar_borradores(fecha)

    elegibles = list(runners) if runners else usuarios_runner()
    pks_elegibles = {u.pk for u in elegibles}

    candidatos = [_candidato(m) for m in candidatos_del_dia(fecha)]
    sin_ubicar = [c for c in candidatos if not _pt(c)]
    ubicables = [c for c in candidatos if _pt(c)]

    cerrar = origen_modo == "sede_redonda"
    contextos = {}

    def _contexto(runner) -> dict:
        ctx = contextos.get(runner.pk)
        if ctx is None:
            origen, etiqueta = _origen_para(runner, origen_modo, sede)
            ctx = contextos[runner.pk] = {
                "runner": runner, "origen": origen, "etiqueta": etiqueta,
                # `acepta`: a quién se le puede CARGAR trabajo nuevo. Al dueño de
                # un mandado se le respeta el suyo aunque no sea elegible, pero
                # no se le encarga nada más.
                "cerrar": cerrar, "paradas": [], "acepta": runner.pk in pks_elegibles,
            }
        return ctx

    for runner in elegibles:
        _contexto(runner)

    libres, sin_permiso = [], []
    for parada in ubicables:
        dueno = parada.get("runner")
        if dueno is None:
            libres.append(parada)
            continue
        ctx = _contexto(dueno)
        ctx["paradas"].append(parada)
        if not ctx["acepta"] and dueno not in sin_permiso:
            sin_permiso.append(dueno)

    if not contextos:
        # Nadie elegible y ningún mandado con dueño: no hay nada que planear.
        return {"rutas": [], "sobrantes": [], "sin_ubicar": sin_ubicar,
                "sin_runner": True, "sin_permiso": []}

    # UNA matriz para el día entero: los orígenes de cada runner y todas las
    # paradas. De aquí en adelante nadie vuelve a pegarle al mapa.
    tabla = tabla_de(
        [ctx["origen"] for ctx in contextos.values()] + [_pt(c) for c in ubicables]
    )

    sobrantes = _repartir(libres, contextos, tabla=tabla)

    rutas = []
    with transaction.atomic():
        for ctx in contextos.values():
            if not ctx["paradas"]:
                continue
            # Una sola verdad: lo que el reparto colocó queda escrito en la
            # tarea, que es la fuente única del runner.
            for parada in ctx["paradas"]:
                if parada.get("runner") is None:
                    asignar_runner(parada["mandado"].tarea, ctx["runner"],
                                   actor=actor, auto=True)
                    parada["runner"] = ctx["runner"]
            ruta = _ruta_viva(fecha, ctx["runner"], origen_modo, sede, actor)
            ruta.origen_lat = ctx["origen"][0] if ctx["origen"] else None
            ruta.origen_lng = ctx["origen"][1] if ctx["origen"] else None
            ruta.origen_etiqueta = ctx["etiqueta"][:200]
            ruta.save(update_fields=["origen_lat", "origen_lng", "origen_etiqueta"])
            _persistir(ruta, ctx["paradas"], tabla=tabla)
            rutas.append(ruta)

    _emitir("ruta.planeada", {
        "fecha": str(fecha), "rutas": len(rutas),
        "paradas": sum(r.total_paradas for r in rutas),
        "sin_ubicar": len(sin_ubicar), "sobrantes": len(sobrantes),
        "sin_permiso": [u.pk for u in sin_permiso],
        "fuente": tabla.fuente,
    })
    return {
        "rutas": rutas, "sobrantes": sobrantes,
        "sin_ubicar": sin_ubicar, "sin_runner": False,
        "sin_permiso": sin_permiso,
        # `calles` o `recta`: la pantalla lo dice, porque de ahí depende si las
        # horas que verá el runner son de calle o a vuelo de pájaro.
        "por_calles": tabla.por_calles,
    }


def _ruta_viva(fecha, runner, origen_modo, sede, actor):
    """La ruta viva de ese runner ese día, o una nueva. Respeta el candado de la
    base: sólo puede haber una."""
    from apps.el_pizarron.models.ruta import ESTADOS_RUTA_VIVOS, Ruta
    ruta = Ruta.objects.filter(
        fecha=fecha, runner=runner, estado__in=ESTADOS_RUTA_VIVOS,
    ).first()
    if ruta is not None:
        return ruta
    return Ruta.objects.create(
        fecha=fecha, runner=runner, estado="borrador",
        origen_modo=origen_modo, sede=sede, creado_por=actor,
    )


def _persistir(ruta, secuencia, *, tabla=None):
    """Escribe las paradas de la ruta en su orden y recalcula tiempos.

    Las que ya existían se actualizan (no se borran y se recrean): si se borraran
    se perdería el histórico de la parada y su pk, que es lo que apunta el
    arrastre de la pantalla.
    """
    from apps.el_pizarron.models.ruta import ParadaRuta

    origen = ruta.origen_punto
    if tabla is None:
        tabla = tabla_de([origen] + [_pt(p) for p in secuencia])
    estimadas = estimar_horas(origen, secuencia, tabla=tabla)
    for i, (parada, hora, metros) in enumerate(estimadas, start=1):
        mandado = parada["mandado"]
        ParadaRuta.objects.update_or_create(
            ruta=ruta, mandado=mandado,
            defaults={
                "orden": i,
                "lat": parada.get("lat"), "lng": parada.get("lng"),
                "etiqueta": (parada.get("etiqueta") or "")[:200],
                "hora_cita": parada.get("hora"),
                "anclada": bool(parada.get("hora")),
                "llegada_estimada": hora,
                "distancia_desde_anterior_m": metros,
            },
        )
    ruta.distancia_m = int(largo_de(origen, secuencia,
                                    cerrar=ruta.es_redonda, tabla=tabla))
    ruta.save(update_fields=["distancia_m"])
    return ruta


def recalcular(ruta):
    """Vuelve a calcular distancias y horas con el orden que tiene AHORA.

    Se llama después de que alguien arrastra una parada: el orden lo decidió una
    persona y no se toca — sólo se recalculan los números que dependen de él.
    """
    paradas = list(ruta.paradas.select_related("mandado", "mandado__tarea"))
    secuencia = [{
        "mandado": p.mandado, "lat": p.lat, "lng": p.lng,
        "etiqueta": p.etiqueta, "hora": p.hora_cita,
    } for p in paradas]
    origen = ruta.origen_punto
    tabla = tabla_de([origen] + [_pt(p) for p in secuencia])
    estimadas = estimar_horas(origen, secuencia, tabla=tabla)
    for parada, (_, hora, metros) in zip(paradas, estimadas, strict=False):
        parada.llegada_estimada = hora
        parada.distancia_desde_anterior_m = metros
        parada.save(update_fields=["llegada_estimada", "distancia_desde_anterior_m"])
    ruta.distancia_m = int(largo_de(origen, secuencia,
                                    cerrar=ruta.es_redonda, tabla=tabla))
    ruta.save(update_fields=["distancia_m"])
    return ruta


def reordenar(ruta, orden_pks: list[int]):
    """Aplica el orden que dejó el arrastre. Acotado a las paradas de la ruta."""
    from django.db import transaction
    propias = {p.pk: p for p in ruta.paradas.all()}
    with transaction.atomic():
        for i, pk in enumerate(orden_pks, start=1):
            parada = propias.get(int(pk))
            if parada is not None and parada.orden != i:
                parada.orden = i
                parada.save(update_fields=["orden"])
    return recalcular(ruta)


def mover_parada(parada, ruta_destino, *, posicion: int | None = None):
    """Pasa una parada de una ruta a otra (arrastrar entre runners).

    Devuelve `(ruta_origen, ruta_destino)` ya recalculadas. Si la parada ya está
    en esa ruta, sólo reacomoda.
    """
    from apps.el_pizarron.models.ruta import ParadaRuta
    from django.db import transaction
    origen = parada.ruta
    if origen.pk == ruta_destino.pk:
        return origen, origen
    if ParadaRuta.objects.filter(ruta=ruta_destino, mandado=parada.mandado).exists():
        # Ya la trae el destino: mover sería duplicarla. Se quita del origen.
        parada.delete()
        return recalcular(origen), ruta_destino

    ultimo = ruta_destino.paradas.count()
    with transaction.atomic():
        parada.ruta = ruta_destino
        parada.orden = posicion if posicion is not None else ultimo + 1
        parada.save(update_fields=["ruta", "orden"])
    _emitir("ruta.parada_movida", {
        "parada": parada.pk, "de": origen.pk, "a": ruta_destino.pk,
    })
    return recalcular(origen), recalcular(ruta_destino)


# ── Transiciones ──────────────────────────────────────────────────────────────

def despachar(ruta, *, actor=None, mandar_correo: bool = True):
    """Publica la ruta: el runner ya puede seguirla, y le llega por correo.

    El correo va por su cuenta (best-effort): si el Cartero está mal configurado
    la ruta queda despachada igual — dejar de despachar por un correo sería
    peor que un correo que no salió.
    """
    from django.utils import timezone
    if ruta.estado not in ("borrador", "despachada"):
        raise ValueError("Sólo se despacha una ruta en borrador.")
    ruta.estado = "despachada"
    if not ruta.despachada_en:
        ruta.despachada_en = timezone.now()
    ruta.save(update_fields=["estado", "despachada_en"])
    _emitir("ruta.despachada", {
        "ruta": ruta.pk, "runner": ruta.runner_id, "paradas": ruta.total_paradas,
    })
    if mandar_correo:
        from apps.el_pizarron import rutas_correo
        rutas_correo.avisar_ruta_al_runner(ruta, actor=actor)
    return ruta


def cerrar(ruta):
    from django.utils import timezone
    ruta.estado = "cerrada"
    ruta.cerrada_en = timezone.now()
    ruta.save(update_fields=["estado", "cerrada_en"])
    return ruta


def cancelar(ruta, *, motivo: str = ""):
    from django.utils import timezone
    ruta.estado = "cancelada"
    ruta.cancelada_en = timezone.now()
    if motivo:
        ruta.notas = f"{ruta.notas}\nCancelada: {motivo}".strip()
    ruta.save(update_fields=["estado", "cancelada_en", "notas"])
    return ruta


# ── Llevarla al teléfono (reusa los enlaces de V1) ────────────────────────────

def enlaces_de(ruta) -> dict:
    """Los enlaces a Waze / Google Maps / Apple Maps para esta ruta guardada.

    Reusa `ruta.py` (V1) para que exista UNA sola implementación de cada enlace:
    esto es lo que Oscar pidió desde el principio — «un botón para exportarla a
    Waze o Google Maps o Apple Maps».
    """
    from apps.el_pizarron.ruta import url_apple, url_google, url_waze
    paradas = [
        {"lat": p.lat, "lng": p.lng}
        for p in ruta.paradas.all() if p.lat is not None and p.lng is not None
    ]
    origen = ruta.origen_punto
    primera = paradas[0] if paradas else None
    return {
        "google": url_google(paradas, origen),
        "apple": url_apple(paradas, origen),
        "waze": url_waze(primera["lat"], primera["lng"]) if primera else "",
    }


def _emitir(tipo: str, payload: dict) -> None:
    """Evento del Portavoz, best-effort: nunca tumba una ruta."""
    import contextlib
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        emitir(tipo, payload)
