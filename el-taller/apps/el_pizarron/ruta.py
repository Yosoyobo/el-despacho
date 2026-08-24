"""La ruta del día del runner, y cómo mandarla a su app de mapas.

Oscar (2026-08-22): «esto va a acabar en la planeación de rutas y un botón para
exportarla a Waze o Google Maps o Apple Maps».

Dos piezas, las dos sin costo:

- **El orden.** Se resuelve con el vecino más cercano: se arranca donde está el
  runner y cada vez se va a la parada más próxima de las que faltan. No es la
  ruta matemáticamente perfecta —eso es un problema caro de resolver y necesita
  un servicio de rutas de paga—, pero para cinco o diez paradas queda muy cerca
  de lo óptimo y se calcula al instante. La regla del despacho es que las cosas
  salgan gratis o no se hacen.
- **La exportación.** Las tres apps abren una ruta con una simple dirección web,
  sin llave ni cuenta: se arma el enlace y el teléfono hace el resto.

La distancia es en línea recta (la misma que ya se guarda al cerrar un mandado),
así que el orden puede no coincidir con el tráfico real. Para decidir en qué
orden salir es suficiente; para prometerle una hora al cliente, no.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Más paradas de las que Google acepta en un enlace, y más de las que alguien
# hace en una vuelta.
MAX_PARADAS = 9


def _distancia(a, b) -> float | None:
    from apps.checador.models.sede import distancia_m

    return distancia_m(a[0], a[1], b[0], b[1])


def ordenar_por_cercania(paradas: list[dict], origen: tuple | None = None) -> list[dict]:
    """Ordena las paradas empezando por la más cercana al origen.

    Cada parada es {lat, lng, ...}. Las que no traen coordenadas se van al final
    con su orden original: no se pueden ubicar, pero tampoco se pierden.
    """
    ubicables = [p for p in paradas if p.get("lat") is not None and p.get("lng") is not None]
    sin_ubicar = [p for p in paradas if p not in ubicables]
    if not ubicables:
        return list(paradas)

    pendientes = list(ubicables)
    actual = origen
    if actual is None:
        # Sin saber dónde está el runner, se arranca por la primera y desde ahí
        # se encadena: el orden relativo sigue siendo útil.
        primera = pendientes.pop(0)
        ruta = [primera]
        actual = (primera["lat"], primera["lng"])
    else:
        ruta = []

    while pendientes:
        mas_cerca, mejor = None, None
        for p in pendientes:
            d = _distancia(actual, (p["lat"], p["lng"]))
            if d is None:
                continue
            if mejor is None or d < mejor:
                mas_cerca, mejor = p, d
        if mas_cerca is None:
            break
        ruta.append(mas_cerca)
        pendientes.remove(mas_cerca)
        actual = (mas_cerca["lat"], mas_cerca["lng"])

    return ruta + pendientes + sin_ubicar


def distancia_total_m(paradas: list[dict], origen: tuple | None = None) -> int | None:
    """Cuánto se recorre siguiendo ese orden, en línea recta."""
    puntos = [(p["lat"], p["lng"]) for p in paradas
              if p.get("lat") is not None and p.get("lng") is not None]
    if origen:
        puntos.insert(0, origen)
    if len(puntos) < 2:
        return None
    total = 0.0
    for a, b in zip(puntos, puntos[1:], strict=False):
        d = _distancia(a, b)
        if d:
            total += d
    return int(total)


# ── Llevarla al teléfono ─────────────────────────────────────────────────

def url_waze(lat, lng) -> str:
    """Waze navega a UN destino a la vez: se le manda la primera parada."""
    return f"https://waze.com/ul?ll={lat}%2C{lng}&navigate=yes"


def url_google(paradas: list[dict], origen: tuple | None = None) -> str:
    """Google Maps sí acepta la ruta completa, con paradas intermedias."""
    ubicables = [p for p in paradas
                 if p.get("lat") is not None and p.get("lng") is not None][:MAX_PARADAS]
    if not ubicables:
        return ""
    destino = ubicables[-1]
    intermedias = ubicables[:-1]
    url = "https://www.google.com/maps/dir/?api=1"
    if origen:
        url += f"&origin={origen[0]}%2C{origen[1]}"
    url += f"&destination={destino['lat']}%2C{destino['lng']}"
    if intermedias:
        puntos = "|".join(f"{p['lat']},{p['lng']}" for p in intermedias)
        url += f"&waypoints={quote(puntos)}"
    return url + "&travelmode=driving"


def url_apple(paradas: list[dict], origen: tuple | None = None) -> str:
    """Apple Maps: destino y, si se sabe, de dónde sale."""
    ubicables = [p for p in paradas
                 if p.get("lat") is not None and p.get("lng") is not None]
    if not ubicables:
        return ""
    destino = ubicables[-1]
    url = f"https://maps.apple.com/?daddr={destino['lat']}%2C{destino['lng']}&dirflg=d"
    if origen:
        url += f"&saddr={origen[0]}%2C{origen[1]}"
    return url


# ── La ruta de hoy de una persona ────────────────────────────────────────

def ruta_de(usuario) -> dict:
    """Los mandados de HOY del runner, ya ordenados, con sus enlaces.

    «De hoy» significa: abiertos, no archivados, y con compromiso para hoy o
    antes — lo de ayer que sigue pendiente hay que hacerlo, lo de la semana que
    entra no. Sin esa acotación la pantalla traía todos los mandados abiertos del
    runner de cualquier fecha y aunque su tarea estuviera archivada: la vuelta de
    Alex arrancaba con dos entregas archivadas del 29 de junio.
    """
    from apps.el_pizarron.mandados import mandados_visibles
    from apps.el_pizarron.runners import ubicacion_actual_de
    from django.db.models import Q
    from django.utils import timezone

    try:
        hoy = timezone.localdate()
        abiertos = [
            m for m in mandados_visibles(usuario).exclude(
                estado__in=("entregado", "cancelado"),
            ).filter(
                tarea__archivada=False,
            ).filter(
                # Sin fecha = trabajo que espera turno: se muestra, porque si no
                # no aparecería en ninguna vuelta.
                Q(tarea__fecha_compromiso__lte=hoy)
                | Q(tarea__fecha_compromiso__isnull=True),
            ).select_related("tarea", "tarea__proyecto", "tarea__proyecto__cliente")
            if m.runner_id == usuario.pk
        ]
    except Exception:  # noqa: BLE001
        logger.warning("no se pudo armar la ruta", exc_info=True)
        return {"paradas": [], "total_km": None, "origen": None}

    paradas = []
    for m in abiertos:
        tarea = m.tarea
        paradas.append({
            "id": m.pk,
            "titulo": tarea.titulo,
            "lugar": getattr(tarea, "destino_etiqueta", "") or "",
            "cliente": (
                tarea.proyecto.cliente.razon_social
                if tarea.proyecto_id and tarea.proyecto.cliente_id else ""
            ),
            "lat": getattr(tarea, "destino_lat", None),
            "lng": getattr(tarea, "destino_lng", None),
            "estado": m.estado,
        })

    origen = None
    try:
        pos = ubicacion_actual_de(usuario)
        if pos:
            origen = (pos[0], pos[1])
    except Exception:  # noqa: BLE001
        origen = None

    ordenadas = ordenar_por_cercania(paradas, origen)
    metros = distancia_total_m(ordenadas, origen)
    return {
        "paradas": ordenadas,
        "origen": origen,
        "total_km": round(metros / 1000, 1) if metros else None,
        "sin_ubicar": sum(1 for p in ordenadas if p["lat"] is None),
        "url_google": url_google(ordenadas, origen),
        "url_apple": url_apple(ordenadas, origen),
        "url_waze": (
            url_waze(ordenadas[0]["lat"], ordenadas[0]["lng"])
            if ordenadas and ordenadas[0]["lat"] is not None else ""
        ),
    }
