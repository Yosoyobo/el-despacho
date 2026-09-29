"""El pin del mapa de un proveedor sigue a su dirección (deuda Sep28).

**El problema.** El pin (`Proveedor.lat/lng`) sólo se movía si en la ficha se
elegía una sugerencia del buscador o se arrastraba. Quien corregía la dirección
a mano —o se la dictaba a El Chalán— dejaba el pin en el lugar viejo, y el
reparto llegaba a la dirección anterior.

**Qué se hace.** Al guardar una dirección distinta SIN que el pin se haya movido
en ese mismo guardado, se vuelve a ubicar en el fondo (`lib.tareas_fondo`, tras
el `commit`): Nominatim tarda segundos y a veces no contesta, y nada de eso
debe hacer esperar al guardado.

**Un pin puesto A MANO no se pisa.** La base no guarda cómo se puso el pin, así
que se averigua: se ubica la dirección ANTERIOR y, si el pin guardado está
donde el buscador la pone (a menos de `UMBRAL_M`), el pin venía del buscador y
se puede mover con la dirección. Si está en otro lado, alguien lo arrastró, lo
fijó picando el mapa o escogió otra sugerencia: se deja y se dice. Sin pin
previo no hay nada que cuidar. Es el mismo criterio cobarde del resto del
sistema: un pin viejo se arregla en diez segundos; uno bueno pisado por una
suposición, no se nota hasta que el repartidor llega a otra calle.

**Nunca rompe.** Si el buscador no contesta o no encuentra la dirección, el pin
se queda donde estaba y la ficha lo avisa la siguiente vez que se abre
(`aviso_pendiente`). Si mientras tanto alguien movió el pin o volvió a cambiar
la dirección, la escritura no pasa (se compara contra lo que había al pedirla).

**La ficha abierta no choca consigo misma.** La ficha se autoguarda y lleva el
pin en campos ocultos: tras moverlo aquí, su siguiente autoguardado mandaría el
pin VIEJO, y el testigo de edición pisada (`lib/edicion.py`) lo tomaría por un
choque con «alguien más». `corregir_post` reconoce ese caso —mandan justo el pin
que este módulo reemplazó— y lo cambia por el nuevo antes de armar el
formulario. Si la persona movió el pin a otro lado, eso manda.

**El alta también** (`programar_alta`). Un proveedor nuevo con dirección y sin
pin se ubica igual, en el fondo: la pantalla de alta, las altas rápidas (ficha
de producto, gasto desde un CFDI) y `crear_proveedor` de El Chalán. Es el mismo
recálculo con «antes» vacío: no hay pin previo que cuidar, y si el alta ya trae
uno (se eligió una sugerencia del buscador) manda ése.

**La ficha abierta se entera.** El recálculo deja su estado en el caché
(`pendiente` mientras corre, luego lo que pasó). Mientras está pendiente, la
ficha sondea `estado_ficha` cada 2 s; al terminar recibe el pin nuevo, mueve el
marcador SIN disparar el autoguardado, pone el pin en sus ocultos y actualiza en
su testigo SÓLO la huella del pin (`testigo_al_dia`): así, si luego la persona
arrastra el pin, no le sale un «choque» con el sistema. El sondeo se apaga solo
al terminar y, si el trabajo del fondo se muere sin avisar, al vencer el estado
(`_ESTADO_TTL_PENDIENTE`).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: A cuántos metros de la dirección anterior tiene que estar el pin para creer
#: que lo puso el buscador. El buscador contesta lo mismo a la misma dirección
#: (y lo cachea), así que un pin suyo queda a 0 m; 100 da holgura a que el mapa
#: de OpenStreetMap se haya corregido un poco entre una vez y otra.
UMBRAL_M = 100

_AVISO_TTL = 7 * 24 * 3600
_CLAVE_AVISO = "catalogo:pin-aviso:{pk}"
#: Lo que el recálculo movió, para que la ficha que quedó abierta no lo devuelva.
_MOVIDO_TTL = 24 * 3600
_CLAVE_MOVIDO = "catalogo:pin-movido:{pk}"
#: En qué va el recálculo, para la ficha abierta: `pendiente` mientras corre y,
#: al terminar, lo que pasó. Si el hilo muere sin terminar, `pendiente` vence
#: solo y el sondeo de la ficha se apaga (a lo más ~60 peticiones).
_CLAVE_ESTADO = "catalogo:pin-estado:{pk}"
_ESTADO_TTL_PENDIENTE = 120
_ESTADO_TTL_FINAL = 10 * 60
PENDIENTE = "pendiente"


def _clave(pk) -> str:
    return _CLAVE_AVISO.format(pk=pk)


def _avisar(pk, texto: str) -> None:
    try:
        from django.core.cache import cache

        cache.set(_clave(pk), texto, _AVISO_TTL)
    except Exception:  # noqa: BLE001 — sin caché no hay aviso, el pin igual quedó bien
        logger.debug("ubicacion: no pude dejar el aviso del pin", exc_info=True)


def aviso_pendiente(pk) -> str:
    """Lo que la ficha tiene que decir del último recálculo (y se olvida)."""
    try:
        from django.core.cache import cache

        texto = cache.get(_clave(pk)) or ""
        if texto:
            cache.delete(_clave(pk))
        return texto
    except Exception:  # noqa: BLE001
        return ""


def _distancia_m(lat1, lng1, lat2, lng2) -> float | None:
    from math import asin, cos, radians, sin, sqrt

    if None in (lat1, lng1, lat2, lng2):
        return None
    la1, lo1, la2, lo2 = map(radians, (float(lat1), float(lng1), float(lat2), float(lng2)))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000.0 * asin(sqrt(h))


def toca_recalcular(antes: dict, despues) -> bool:
    """¿Cambió la dirección y el pin se quedó igual en ESTE guardado?

    `antes` son `direccion`, `lat` y `lng` capturados ANTES de validar el
    formulario (§14 Bug D). Si el pin también cambió, quien guardó lo acaba de
    poner (sugerencia elegida o arrastre): manda eso.
    """
    nueva = (getattr(despues, "direccion", "") or "").strip()
    if not nueva or nueva == (antes.get("direccion") or "").strip():
        return False
    return (despues.lat, despues.lng) == (antes.get("lat"), antes.get("lng"))


AVISO_A_MANO = ("Cambió la dirección, pero el pin del mapa no se movió: no está donde el "
                "buscador pone la dirección anterior, así que parece puesto a mano. Si el "
                "lugar también cambió, fíjalo en el mapa.")
AVISO_SIN_RESULTADO = ("No se pudo ubicar la dirección nueva en el mapa (el buscador no la "
                       "encontró o no contestó). El pin se quedó donde estaba: fíjalo en el "
                       "mapa si hace falta.")

MENSAJE_ALTA = ("El pin del mapa se ubica solo con su dirección en unos segundos (si no "
                "se encuentra, se avisa aquí).")
MENSAJE_PROGRAMADO = ("La dirección cambió: el pin del mapa se acomoda solo en unos "
                      "segundos (si no se encuentra, se queda donde estaba y se avisa aquí).")


def _poner_estado(pk, datos: dict, ttl: int) -> None:
    try:
        from django.core.cache import cache

        cache.set(_CLAVE_ESTADO.format(pk=pk), datos, ttl)
    except Exception:  # noqa: BLE001 — sin caché la ficha no se entera sola; el dato igual queda
        logger.debug("ubicacion: no pude anotar el estado del pin", exc_info=True)


def estado(pk) -> dict | None:
    """En qué va el último recálculo del pin (None si no hay nada reciente)."""
    try:
        from django.core.cache import cache

        datos = cache.get(_CLAVE_ESTADO.format(pk=pk))
    except Exception:  # noqa: BLE001
        return None
    return datos if isinstance(datos, dict) else None


def pendiente(pk) -> bool:
    return (estado(pk) or {}).get("estado") == PENDIENTE


def _lanzar(args) -> None:
    from lib.tareas_fondo import ejecutar_en_fondo

    _poner_estado(args[0], {"estado": PENDIENTE}, _ESTADO_TTL_PENDIENTE)
    ejecutar_en_fondo(recalcular, *args)


def programar(prov, antes: dict) -> bool:
    """Si toca, deja el recálculo para después del `commit`. True si lo dejó."""
    if not toca_recalcular(antes, prov):
        return False
    from django.db import transaction

    args = (prov.pk, antes.get("direccion") or "", prov.direccion, prov.lat, prov.lng)
    transaction.on_commit(lambda: _lanzar(args))
    return True


def programar_alta(prov) -> bool:
    """El alta de un proveedor: si trae dirección y no trae pin, se ubica solo.

    Un alta que ya trae pin (se eligió una sugerencia del buscador en la
    pantalla de alta) no se toca: `toca_recalcular` ve que el pin «cambió»."""
    return programar(prov, {"direccion": "", "lat": None, "lng": None})


def recalcular(pk, direccion_anterior: str, direccion_nueva: str, lat0, lng0) -> str:
    """Ubica la dirección nueva y mueve el pin si se puede. Devuelve qué pasó
    (`movido`, `a_mano`, `sin_resultado`, `cambio_despues`).

    Pase lo que pase —incluso si el buscador revienta— deja el estado final
    para la ficha abierta, que así deja de preguntar."""
    final = {"estado": "error"}
    try:
        final["estado"] = _recalcular(pk, direccion_anterior, direccion_nueva, lat0, lng0, final)
        return final["estado"]
    except Exception:
        _avisar(pk, AVISO_SIN_RESULTADO)
        raise
    finally:
        _poner_estado(pk, final, _ESTADO_TTL_FINAL)


def _recalcular(pk, direccion_anterior, direccion_nueva, lat0, lng0, final: dict) -> str:
    from apps.el_catalogo.models import Proveedor

    from lib.geocoding import primer_resultado

    if lat0 is not None and lng0 is not None:
        viejo = primer_resultado(direccion_anterior) if direccion_anterior.strip() else None
        d = _distancia_m(lat0, lng0, viejo and viejo["lat"], viejo and viejo["lng"])
        if d is None or d > UMBRAL_M:
            _avisar(pk, AVISO_A_MANO)
            return "a_mano"

    nuevo = primer_resultado(direccion_nueva)
    if not nuevo:
        _avisar(pk, AVISO_SIN_RESULTADO)
        return "sin_resultado"

    filtro = {"pk": pk, "direccion": direccion_nueva}
    filtro.update({"lat__isnull": True} if lat0 is None else {"lat": lat0})
    filtro.update({"lng__isnull": True} if lng0 is None else {"lng": lng0})
    # `update` directo: no toca `actualizado_en` ni la firma del testigo de
    # edición — el pin no es algo que alguien haya escrito en la ficha.
    if not Proveedor.objects.filter(**filtro).update(lat=nuevo["lat"], lng=nuevo["lng"]):
        return "cambio_despues"
    movido = {"de": [lat0, lng0], "a": [nuevo["lat"], nuevo["lng"]]}
    final.update(movido)
    try:
        from django.core.cache import cache

        cache.set(_CLAVE_MOVIDO.format(pk=pk), movido, _MOVIDO_TTL)
    except Exception:  # noqa: BLE001 — sin esto, la ficha abierta avisaría un choque
        logger.debug("ubicacion: no pude anotar el pin movido", exc_info=True)
    return "movido"


def _flotante(texto):
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return "no-numero"


def corregir_post(post, prov):
    """El POST de la ficha con el pin nuevo si trae el que este módulo reemplazó.

    Devuelve el mismo `post` si no hay nada que corregir (lo normal)."""
    if "lat" not in post and "lng" not in post:
        return post
    try:
        from django.core.cache import cache

        movido = cache.get(_CLAVE_MOVIDO.format(pk=prov.pk))
    except Exception:  # noqa: BLE001
        return post
    if not movido:
        return post
    de, a = list(movido.get("de") or []), list(movido.get("a") or [])
    if [prov.lat, prov.lng] != a:
        return post  # el pin ya es otro: no es el caso
    if [_flotante(post.get("lat")), _flotante(post.get("lng"))] != de:
        return post  # la persona puso otro pin: manda eso
    corregido = post.copy()
    corregido["lat"], corregido["lng"] = str(a[0]), str(a[1])
    return corregido


def testigo_al_dia(crudo, prov, de) -> str:
    """El testigo de la ficha abierta con la huella del pin NUEVO. "" si no toca.

    Sólo se cambian `lat`/`lng`, y sólo si la ventana los abrió con el pin que
    el recálculo reemplazó (`de`): el sistema movió el pin y la ventana ya lo
    sabe, así que arrastrarlo después no es pisar a «alguien más». El resto del
    testigo queda como llegó — lo que otra persona haya cambiado sigue avisando.
    """
    import json

    from lib import edicion

    from .forms import ProveedorForm

    datos = edicion.leer_testigo(crudo)
    if datos is None or not isinstance(datos.get("f"), dict):
        return ""
    form = ProveedorForm(instance=prov, inline=True)
    huellas = datos["f"]
    cambio = False
    for nombre, viejo in zip(("lat", "lng"), list(de or [None, None])[:2], strict=False):
        campo = form.fields.get(nombre)
        if campo is None or nombre not in huellas:
            continue
        if huellas[nombre] != edicion.huella(campo.prepare_value(viejo)):
            continue
        huellas[nombre] = edicion.huella(campo.prepare_value(form[nombre].initial))
        cambio = True
    if not cambio:
        return ""
    return json.dumps(datos, ensure_ascii=False, separators=(",", ":"))


def para_ficha(prov, testigo_crudo: str = "") -> dict | None:
    """Lo que la ficha abierta tiene que saber del recálculo. None = sigue en eso.

    `pin` = {de, a, testigo} si el pin se movió y sigue ahí; `aviso` = el texto
    si no se pudo (y se da por dicho: la ficha no lo repite al volver a abrir).
    """
    datos = estado(prov.pk) or {}
    if datos.get("estado") == PENDIENTE:
        return None
    info = {"estado": datos.get("estado") or "", "pin": None, "aviso": ""}
    a = list(datos.get("a") or [])
    if info["estado"] == "movido" and [prov.lat, prov.lng] == a:
        de = list(datos.get("de") or [None, None])
        info["pin"] = {"de": de, "a": a, "testigo": testigo_al_dia(testigo_crudo, prov, de)}
    elif info["estado"] in ("a_mano", "sin_resultado", "error"):
        info["aviso"] = aviso_pendiente(prov.pk) or (
            AVISO_A_MANO if info["estado"] == "a_mano" else AVISO_SIN_RESULTADO)
    return info


def antes_de(prov) -> dict:
    """Lo que `programar` necesita, capturado antes de validar."""
    return {"direccion": prov.direccion, "lat": prov.lat, "lng": prov.lng}


__all__ = ["AVISO_A_MANO", "AVISO_SIN_RESULTADO", "MENSAJE_ALTA", "PENDIENTE", "UMBRAL_M", "antes_de",
           "aviso_pendiente", "corregir_post", "estado", "para_ficha", "pendiente", "programar",
           "programar_alta", "recalcular", "testigo_al_dia", "toca_recalcular"]
