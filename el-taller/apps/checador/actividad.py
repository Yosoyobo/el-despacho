"""El Checador por actividad (Oscar 2026-10-01).

Para quien tiene `Usuario.checador_por_actividad` prendido en El Directorio, la
jornada se arma sola: **de la primera a la última actividad del día en El
Taller**, y el día corta a las 23:59 (la fecha es la local de México: una
actividad a las 00:10 ya abre el día siguiente).

Decisiones de Oscar, literales de la conversación:

- **Actividad** = cualquier clic o pantalla de la persona, salvo los refrescos
  automáticos. No se inventa un criterio: se reusa el de la presencia
  (`lib.presencia`), que ya descarta el sondeo y escribe a lo más una vez por
  minuto. Su `_registrar` llama a `registrar_actividad` cuando escribe en El
  Taller.
- **Conviven con el checado a mano**: lo que se cheque a mano gana EN SU
  EXTREMO. Una entrada a mano reemplaza la que puso la actividad; una salida a
  mano cierra la jornada y la actividad posterior ya no la mueve.
- **Pausas**: segundo interruptor (`checador_descontar_pausas`). Apagado, se
  cuenta de corrido; prendido, todo hueco sin actividad mayor a
  `checador_pausa_min` se acumula en `Jornada.pausa_min` y se resta.
- **Ubicación**: se pide con la primera actividad y se vuelve a tomar en
  silencio (`static/js/checador_actividad.js`, cada 10 min a lo más). La primera
  es la de la entrada y se mide contra las sedes como cualquier checada; la
  última queda como la de la salida. Si la niega, la jornada cuenta igual y
  queda marcada sin ubicación.

La jornada abierta se cierra con su última actividad en
`services.cerrar_jornadas_vencidas` (cron poco después de medianoche).

Nada de aquí lanza hacia la petición: la presencia lo envuelve, y una actividad
que no se pudo anotar no puede tumbar la pantalla que la persona pidió.
"""

from __future__ import annotations

import datetime as _dt

from django.db import transaction
from django.utils import timezone

from .models import Jornada


def aplica(usuario) -> bool:
    return bool(getattr(usuario, "checador_por_actividad", False))


def _umbral_pausa(usuario) -> _dt.timedelta | None:
    if not getattr(usuario, "checador_descontar_pausas", False):
        return None
    minutos = getattr(usuario, "checador_pausa_min", 0) or 0
    return _dt.timedelta(minutes=max(5, minutos))


def registrar_actividad(usuario, ahora=None) -> Jornada | None:
    """Anota una actividad de la persona en su jornada del día.

    Sin jornada → la abre con entrada por actividad (y su retardo). Con la
    jornada cerrada a mano → no la toca (lo manual gana). Devuelve la jornada o
    None si no aplica.
    """
    if not aplica(usuario) or not getattr(usuario, "pk", None):
        return None
    from . import services

    ahora = ahora or timezone.now()
    fecha = timezone.localtime(ahora).date()
    nueva = False
    with transaction.atomic():
        jornada = (
            Jornada.objects.select_for_update().filter(usuario=usuario, fecha=fecha).first()
        )
        if jornada is None:
            jornada = Jornada(usuario=usuario, fecha=fecha)
        if jornada.salida_en:
            # Cerrada: si la cerró una checada a mano, gana; la actividad
            # posterior no reabre ni alarga nada. (Las cerradas por actividad
            # sólo se cierran al día siguiente, así que aquí no aparecen.)
            return jornada
        if not jornada.entrada_en:
            nueva = True
            jornada.entrada_en = ahora
            jornada.entrada_por_actividad = True
            jornada.entrada_sin_geo = True  # hasta que llegue la ubicación
            jornada.retardo_min = services.calcular_retardo(
                services.horario_vigente(usuario, fecha), ahora,
            )
            jornada.estado = "abierta"
        else:
            umbral = _umbral_pausa(usuario)
            # El hueco se mide desde lo último que cuenta del segmento en curso:
            # una re-entrada a mano deja atrás la pausa anterior (esa ya no
            # cuenta por la propia lógica de segmentos), no se descuenta dos veces.
            desde = max(filter(None, [jornada.actividad_ultima_en, jornada.entrada_en]))
            hueco = ahora - desde
            if umbral is not None and hueco > umbral:
                jornada.pausa_min = (jornada.pausa_min or 0) + int(hueco.total_seconds() // 60)
        if jornada.actividad_primera_en is None:
            jornada.actividad_primera_en = ahora
        if jornada.actividad_ultima_en is None or ahora > jornada.actividad_ultima_en:
            jornada.actividad_ultima_en = ahora
        jornada.save()

    if nueva:
        services._emitir("checador.entrada", actor=usuario, payload={
            "jornada_id": jornada.pk, "fecha": str(fecha), "por_actividad": True,
            "retardo_min": jornada.retardo_min, "sin_geo": True,
        })
        if jornada.retardo_min > 0:
            services._emitir("checador.retardo", actor=usuario, payload={
                "jornada_id": jornada.pk, "fecha": str(fecha),
                "retardo_min": jornada.retardo_min, "por_actividad": True,
            })
    return jornada


def registrar_ubicacion(usuario, *, lat, lng, precision=None, ahora=None) -> Jornada | None:
    """Ubicación tomada en silencio mientras la persona trabaja.

    Siempre queda como la última conocida (será la de la salida). Si la entrada
    la puso la actividad y aún no tenía ubicación, es la de la entrada y se mide
    contra las sedes como cualquier checada.
    """
    if not aplica(usuario) or lat is None or lng is None:
        return None
    from . import services

    ahora = ahora or timezone.now()
    fecha = timezone.localtime(ahora).date()
    medir = False
    with transaction.atomic():
        jornada = (
            Jornada.objects.select_for_update().filter(usuario=usuario, fecha=fecha).first()
        )
        if jornada is None or jornada.salida_en:
            return jornada
        jornada.actividad_lat = lat
        jornada.actividad_lng = lng
        jornada.actividad_precision = precision
        if jornada.entrada_por_actividad and jornada.entrada_lat is None:
            services._aplicar_geo(jornada, "entrada_", {"lat": lat, "lng": lng, "precision": precision})
            medir = True
        jornada.save()
    if medir:
        services._evaluar_geocerca(usuario, jornada)
    return jornada


def salida_de_actividad(jornada: Jornada) -> dict | None:
    """Con qué cerrar una jornada abierta que tuvo actividad: hora y ubicación
    de su última actividad. None si no hay actividad posterior a la entrada."""
    ultima = jornada.actividad_ultima_en
    if not ultima or not jornada.entrada_en or ultima <= jornada.entrada_en:
        return None
    return {
        "en": ultima,
        "geo": {
            "lat": jornada.actividad_lat, "lng": jornada.actividad_lng,
            "precision": jornada.actividad_precision,
        },
    }
