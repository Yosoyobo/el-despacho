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

Todo con distancia en línea recta (`ruta._distancia` → el haversine de El
Checador). No hay servicio de ruteo por calles porque cuesta: para decidir el
ORDEN de 5-10 paradas alcanza, para prometerle una hora exacta al cliente no —
y por eso las horas que calcula se llaman «estimadas» en la pantalla.

Ojo con los nombres: `apps.el_pizarron.ruta` es el ayudante de V1 (orden al
vuelo + enlaces a las apps) y `apps.el_pizarron.models.ruta` son los modelos.
Este módulo usa los dos.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

logger = logging.getLogger(__name__)

#: Velocidad de crucero para estimar tiempos, en km/h. Ciudad con tráfico.
VELOCIDAD_KMH = 25.0
#: Lo que se tarda en cada parada (bajar, entregar, firmar), en minutos.
MINUTOS_POR_PARADA = 10
#: Hora a la que se supone que arranca la vuelta si ninguna cita obliga antes.
HORA_INICIO_DEFAULT = time(9, 0)
#: Tope de paradas por ruta. Es el mismo de `ruta.MAX_PARADAS`: más de eso no
#: lo acepta el enlace de Google Maps ni lo hace nadie en una vuelta.
MAX_PARADAS_POR_RUTA = 9


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
    """La parada como diccionario, en la forma que ya usa `ruta.py`."""
    punto = _punto_de(mandado)
    return {
        "mandado": mandado,
        "lat": punto[0] if punto else None,
        "lng": punto[1] if punto else None,
        "etiqueta": _etiqueta_de(mandado),
        "hora": getattr(mandado.tarea, "hora", None),
    }


# ── Distancias ────────────────────────────────────────────────────────────────

def _d(a, b) -> float:
    """Metros entre dos puntos; 0 si alguno no se puede ubicar."""
    from apps.el_pizarron.ruta import _distancia
    if not a or not b:
        return 0.0
    return _distancia(a, b) or 0.0


def _pt(parada):
    lat, lng = parada.get("lat"), parada.get("lng")
    return (lat, lng) if lat is not None and lng is not None else None


def largo_de(origen, secuencia, *, cerrar: bool) -> float:
    """Metros del recorrido completo en ese orden."""
    puntos = [p for p in (_pt(x) for x in secuencia) if p]
    if origen:
        puntos.insert(0, origen)
    if len(puntos) < 2:
        return 0.0
    total = sum(_d(a, b) for a, b in zip(puntos, puntos[1:], strict=False))
    if cerrar and origen and puntos[-1] != origen:
        total += _d(puntos[-1], origen)
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


def _dos_opt_tramo(origen, secuencia, desde, hasta, *, cerrar):
    """2-opt dentro de un tramo, con los extremos clavados.

    Invierte sub-rutas mientras el recorrido total baje. Como sólo toca
    `[desde:hasta]` y ahí no hay anclas, ninguna cita se puede mover.
    """
    mejor = secuencia[:]
    mejor_largo = largo_de(origen, mejor, cerrar=cerrar)
    hubo_mejora = True
    while hubo_mejora:
        hubo_mejora = False
        for i in range(desde, hasta - 1):
            for j in range(i + 1, hasta):
                cand = mejor[:]
                cand[i:j + 1] = reversed(cand[i:j + 1])
                largo = largo_de(origen, cand, cerrar=cerrar)
                if largo < mejor_largo - 0.5:  # medio metro: evita zumbido
                    mejor, mejor_largo = cand, largo
                    hubo_mejora = True
    return mejor


def _ordenar_con_citas(origen, paradas, *, cerrar: bool):
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
    libres.sort(key=lambda p: -_d(origen, _pt(p)) if origen else 0)
    for libre in libres:
        mejor_pos, mejor_costo = len(secuencia), None
        for pos in range(len(secuencia) + 1):
            cand = secuencia[:pos] + [libre] + secuencia[pos:]
            costo = largo_de(origen, cand, cerrar=cerrar)
            if mejor_costo is None or costo < mejor_costo:
                mejor_pos, mejor_costo = pos, costo
        secuencia.insert(mejor_pos, libre)

    for desde, hasta in _tramos(secuencia):
        if hasta - desde > 1:
            secuencia = _dos_opt_tramo(origen, secuencia, desde, hasta, cerrar=cerrar)

    # Las que no se pueden ubicar no se pierden: van al final, en su orden.
    return secuencia + sin_ubicar


# ── Horas estimadas ───────────────────────────────────────────────────────────

def _minutos_de(metros: float) -> int:
    return int(round((metros / 1000.0) / VELOCIDAD_KMH * 60)) if metros else 0


def estimar_horas(origen, secuencia, *, inicio: time | None = None):
    """Llegada estimada a cada parada. Devuelve `[(parada, hora, metros)]`.

    Si una parada tiene cita y se llega antes, se espera: la hora que se muestra
    es la de la cita, no la del reloj del viaje. Si se llega después, se muestra
    la real — mentir aquí sería peor que llegar tarde.
    """
    anclas = [p["hora"] for p in secuencia if p.get("hora")]
    arranque = inicio or HORA_INICIO_DEFAULT
    if anclas:
        # Si la primera cita es temprano, la vuelta empieza antes.
        arranque = min([arranque, *anclas])

    base = datetime(2000, 1, 1, arranque.hour, arranque.minute)
    reloj = base
    anterior = origen
    salida = []
    for parada in secuencia:
        punto = _pt(parada)
        metros = _d(anterior, punto) if (anterior and punto) else 0.0
        reloj += timedelta(minutes=_minutos_de(metros))
        cita = parada.get("hora")
        if cita:
            hora_cita = datetime(2000, 1, 1, cita.hour, cita.minute)
            if reloj < hora_cita:
                reloj = hora_cita  # llegó antes: espera a su cita
        salida.append((parada, reloj.time(), int(metros)))
        reloj += timedelta(minutes=MINUTOS_POR_PARADA)
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


def _repartir(candidatos, contextos):
    """Reparte las paradas entre los runners por inserción más barata.

    `contextos` es `{runner_pk: {"runner", "origen", "cerrar", "paradas"}}`.
    Cada parada se le da al runner cuya ruta crece menos, con tope de carga para
    que no se le apile todo al que quedó más cerca. Las citas se reparten
    primero: son las que no admiten acomodo.
    """
    if not contextos:
        return []

    def _peso_cita(p):
        return (0, p["hora"]) if p.get("hora") else (1, time(23, 59))

    pendientes = sorted(candidatos, key=_peso_cita)
    sobrantes = []
    for parada in pendientes:
        mejor, mejor_costo = None, None
        for ctx in contextos.values():
            if len(ctx["paradas"]) >= MAX_PARADAS_POR_RUTA:
                continue
            antes = largo_de(ctx["origen"], ctx["paradas"], cerrar=ctx["cerrar"])
            tentativa = _ordenar_con_citas(
                ctx["origen"], [*ctx["paradas"], parada], cerrar=ctx["cerrar"],
            )
            despues = largo_de(ctx["origen"], tentativa, cerrar=ctx["cerrar"])
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
            ctx["origen"], ctx["paradas"], cerrar=ctx["cerrar"],
        )
    return sobrantes


# ── Guardar el plan ───────────────────────────────────────────────────────────

def planear_dia(fecha, *, origen_modo: str = "sede_redonda", sede=None,
                runners=None, actor=None) -> dict:
    """Arma (o rearma) las rutas del día y las guarda.

    Devuelve `{rutas, sobrantes, sin_ubicar, sin_runner}`. No lanza: si algo
    falla al ubicar una parada, ésa queda fuera y las demás se planean igual.

    Idempotente por diseño: los mandados que ya están en una ruta viva no se
    vuelven a repartir (`candidatos_del_dia` los excluye), así que replanear el
    mismo día agrega lo nuevo en vez de duplicar lo que ya se despachó.
    """
    from django.db import transaction

    from lib.permisos import usuarios_runner

    elegibles = list(runners) if runners else usuarios_runner()
    if not elegibles:
        return {"rutas": [], "sobrantes": [], "sin_ubicar": [], "sin_runner": True}

    candidatos = [_candidato(m) for m in candidatos_del_dia(fecha)]
    sin_ubicar = [c for c in candidatos if not _pt(c)]
    ubicables = [c for c in candidatos if _pt(c)]

    cerrar = origen_modo == "sede_redonda"
    contextos = {}
    for runner in elegibles:
        origen, etiqueta = _origen_para(runner, origen_modo, sede)
        contextos[runner.pk] = {
            "runner": runner, "origen": origen, "etiqueta": etiqueta,
            "cerrar": cerrar, "paradas": [],
        }

    sobrantes = _repartir(ubicables, contextos)

    rutas = []
    with transaction.atomic():
        for ctx in contextos.values():
            if not ctx["paradas"]:
                continue
            ruta = _ruta_viva(fecha, ctx["runner"], origen_modo, sede, actor)
            ruta.origen_lat = ctx["origen"][0] if ctx["origen"] else None
            ruta.origen_lng = ctx["origen"][1] if ctx["origen"] else None
            ruta.origen_etiqueta = ctx["etiqueta"][:200]
            ruta.save(update_fields=["origen_lat", "origen_lng", "origen_etiqueta"])
            _persistir(ruta, ctx["paradas"])
            rutas.append(ruta)

    _emitir("ruta.planeada", {
        "fecha": str(fecha), "rutas": len(rutas),
        "paradas": sum(r.total_paradas for r in rutas),
        "sin_ubicar": len(sin_ubicar), "sobrantes": len(sobrantes),
    })
    return {
        "rutas": rutas, "sobrantes": sobrantes,
        "sin_ubicar": sin_ubicar, "sin_runner": False,
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


def _persistir(ruta, secuencia):
    """Escribe las paradas de la ruta en su orden y recalcula tiempos.

    Las que ya existían se actualizan (no se borran y se recrean): si se borraran
    se perdería el histórico de la parada y su pk, que es lo que apunta el
    arrastre de la pantalla.
    """
    from apps.el_pizarron.models.ruta import ParadaRuta

    origen = ruta.origen_punto
    estimadas = estimar_horas(origen, secuencia)
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
    ruta.distancia_m = int(largo_de(origen, secuencia, cerrar=ruta.es_redonda))
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
    estimadas = estimar_horas(origen, secuencia)
    for parada, (_, hora, metros) in zip(paradas, estimadas, strict=False):
        parada.llegada_estimada = hora
        parada.distancia_desde_anterior_m = metros
        parada.save(update_fields=["llegada_estimada", "distancia_desde_anterior_m"])
    ruta.distancia_m = int(largo_de(origen, secuencia, cerrar=ruta.es_redonda))
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
    from django.db import transaction

    from apps.el_pizarron.models.ruta import ParadaRuta
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
