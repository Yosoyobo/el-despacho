"""Cuánto cuesta el tiempo que el equipo le metió a cada proyecto.

El cronómetro por proyecto existe pero casi no se usa: en tres meses hay seis
sesiones y todas en un mismo proyecto. Así que con el puro timer la mano de
obra sería una columna vacía. Por eso se cuentan dos cosas:

- **Medido**: las horas del cronómetro. Exactas.
- **Estimado**: las horas de la jornada que no están en ningún cronómetro, se
  reparten EN PARTES IGUALES entre los proyectos que la persona tocó ese día
  (decisión de Oscar). Cada resultado viene marcado como estimado para que
  nadie lo lea como si fuera medición.

"Tocó" un proyecto = le movió algo ese día: cronómetro, actividad registrada en
el proyecto, o una visita ligada a él.

El costo por hora sale de la tarifa del rol (Gerencia → Ajustes → El Análisis).
Una persona con varios roles cuesta lo que su rol más caro: al costear conviene
no quedarse corto. Sin tarifa, se usa la tarifa general; si tampoco hay, esa
persona no suma costo y se dice.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

# Tope defensivo de jornadas a recorrer en una corrida.
MAX_JORNADAS = 4000


def _cfg():
    from ajustes.models import ConfiguracionAnalisis
    return ConfiguracionAnalisis.obtener()


def costo_hora_de(usuario, cfg=None) -> Decimal:
    """Cuánto cuesta una hora de esta persona."""
    from ajustes.models import TarifaRol

    cfg = cfg or _cfg()
    try:
        claves = {r.pk for r in usuario.roles_extra.all()}
        tarifas = TarifaRol.objects.filter(rol_id__in=claves, activo=True) if claves else []
        montos = [t.costo_hora for t in tarifas if t.costo_hora and t.costo_hora > 0]
        if montos:
            return max(montos)
    except Exception:  # noqa: BLE001
        logger.warning("costo_hora_de: no se pudo leer la tarifa por rol", exc_info=True)
    return cfg.tarifa_hora_default or Decimal("0.00")


def _proyectos_tocados(usuario_id: int, dia: date) -> set[int]:
    """Los proyectos a los que esta persona les movió algo ese día."""
    from apps.los_proyectos.models import ActividadProyecto

    tocados: set[int] = set()
    try:
        tocados.update(
            ActividadProyecto.objects.filter(
                actor_id=usuario_id, creado_en__date=dia,
            ).values_list("proyecto_id", flat=True)
        )
    except Exception:  # noqa: BLE001
        logger.warning("no se pudo leer la actividad del día", exc_info=True)
    try:
        from apps.checador.models import Visita

        tocados.update(
            Visita.objects.filter(usuario_id=usuario_id, registrado_en__date=dia)
            .exclude(tarea__isnull=True)
            .values_list("tarea__proyecto_id", flat=True)
        )
    except Exception:  # noqa: BLE001
        pass
    tocados.discard(None)
    return tocados


def horas_por_proyecto(desde: date, hasta: date) -> dict[int, dict]:
    """Horas y costo de mano de obra por proyecto en el periodo.

    Devuelve {proyecto_id: {horas_medidas, horas_estimadas, horas, costo,
    estimado}} — `estimado` es True si alguna hora vino del reparto.
    """
    from apps.checador.models import Jornada, SesionProyecto

    cfg = _cfg()
    acumulado: dict[int, dict] = defaultdict(
        lambda: {"horas_medidas": 0.0, "horas_estimadas": 0.0, "costo": Decimal("0.00")}
    )
    costo_cache: dict[int, Decimal] = {}

    def costo_de(usuario) -> Decimal:
        if usuario.pk not in costo_cache:
            costo_cache[usuario.pk] = costo_hora_de(usuario, cfg)
        return costo_cache[usuario.pk]

    # 1) Lo medido: cronómetro por proyecto.
    medidas: dict[tuple[int, date], dict[int, float]] = defaultdict(dict)
    try:
        sesiones = SesionProyecto.objects.filter(
            inicio__date__gte=desde, inicio__date__lte=hasta,
            duracion_min__isnull=False,
        ).select_related("usuario")
        for s in sesiones:
            horas = (s.duracion_min or 0) / 60
            if horas <= 0 or not s.proyecto_id:
                continue
            dia = s.inicio.date()
            medidas[(s.usuario_id, dia)][s.proyecto_id] = (
                medidas[(s.usuario_id, dia)].get(s.proyecto_id, 0.0) + horas
            )
            acumulado[s.proyecto_id]["horas_medidas"] += horas
            acumulado[s.proyecto_id]["costo"] += Decimal(str(round(horas, 4))) * costo_de(s.usuario)
    except Exception:  # noqa: BLE001
        logger.warning("horas_por_proyecto: falló la lectura de cronómetros", exc_info=True)

    if not cfg.prorratear_jornada:
        return {pid: _cerrar(datos) for pid, datos in acumulado.items()}

    # 2) Lo estimado: el resto de la jornada, repartido en partes iguales.
    try:
        jornadas = (
            Jornada.objects.filter(fecha__gte=desde, fecha__lte=hasta)
            .select_related("usuario")[:MAX_JORNADAS]
        )
        tope = float(cfg.horas_jornada_tope or 12)
        for j in jornadas:
            horas_dia = j.horas_trabajadas
            if not horas_dia or horas_dia <= 0:
                continue
            horas_dia = min(horas_dia, tope)
            ya_medidas = medidas.get((j.usuario_id, j.fecha), {})
            restante = horas_dia - sum(ya_medidas.values())
            if restante <= 0:
                continue
            tocados = _proyectos_tocados(j.usuario_id, j.fecha) - set(ya_medidas)
            if not tocados:
                continue  # trabajó, pero no en algo que se pueda imputar
            parte = restante / len(tocados)
            costo_h = costo_de(j.usuario)
            for pid in tocados:
                acumulado[pid]["horas_estimadas"] += parte
                acumulado[pid]["costo"] += Decimal(str(round(parte, 4))) * costo_h
    except Exception:  # noqa: BLE001
        logger.warning("horas_por_proyecto: falló el reparto de jornadas", exc_info=True)

    return {pid: _cerrar(datos) for pid, datos in acumulado.items()}


def _cerrar(datos: dict) -> dict:
    medidas = round(datos["horas_medidas"], 2)
    estimadas = round(datos["horas_estimadas"], 2)
    return {
        "horas_medidas": medidas,
        "horas_estimadas": estimadas,
        "horas": round(medidas + estimadas, 2),
        "costo": float(datos["costo"].quantize(Decimal("0.01"))),
        "estimado": estimadas > 0,
    }


def hay_tarifas_configuradas() -> bool:
    """¿Se puede costear la mano de obra, o falta capturar las tarifas?"""
    from ajustes.models import TarifaRol

    try:
        cfg = _cfg()
        if cfg.tarifa_hora_default and cfg.tarifa_hora_default > 0:
            return True
        return TarifaRol.objects.filter(activo=True, costo_hora__gt=0).exists()
    except Exception:  # noqa: BLE001
        return False
