"""Cuánto se ganó (o se perdió) en cada proyecto, de verdad.

Dos columnas, como las pidió Oscar:

1. **Materiales** — lo que ya calcula el proyecto con lo capturado: producto,
   merma, impresión, procesos y sus egresos. Es EXACTO.
2. **Con mano de obra** — lo anterior más el costo del tiempo del equipo. Hoy
   ese tiempo es en buena parte estimado (ver `mano_obra.py`), y por eso viene
   marcado como tal. Si no hay tarifas capturadas, la columna se declara
   indisponible en vez de fingir un cero.

El umbral de lo que es un margen sano se configura en Gerencia; de ahí sale el
semáforo (verde, amarillo, rojo) que usa El Análisis para señalar proyectos.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

# Cuántos proyectos se analizan de una corrida.
MAX_PROYECTOS = 500


def _cfg():
    from ajustes.models import ConfiguracionAnalisis
    return ConfiguracionAnalisis.obtener()


def semaforo_margen(margen_pct: float | Decimal | None, cfg=None) -> str:
    """verde | amarillo | rojo | sin_datos."""
    if margen_pct is None:
        return "sin_datos"
    cfg = cfg or _cfg()
    valor = float(margen_pct)
    if valor <= float(cfg.margen_critico_pct):
        return "rojo"
    if valor < float(cfg.margen_sano_pct):
        return "amarillo"
    return "verde"


def rentabilidad_de(proyecto, horas: dict | None = None, cfg=None) -> dict:
    """La cuenta de un proyecto: ingreso, costos, utilidad y margen."""
    cfg = cfg or _cfg()
    horas = horas or {}

    ingreso = Decimal(str(proyecto.monto_calculado or 0))
    costo_mat = Decimal(str(proyecto.costo_produccion or 0))
    utilidad_mat = ingreso - costo_mat
    margen_mat = (
        float((utilidad_mat / ingreso * 100).quantize(Decimal("0.1"))) if ingreso > 0 else None
    )

    costo_mo = Decimal(str(horas.get("costo", 0) or 0))
    con_mo = costo_mo > 0
    costo_total = costo_mat + costo_mo
    utilidad_total = ingreso - costo_total
    margen_total = (
        float((utilidad_total / ingreso * 100).quantize(Decimal("0.1"))) if ingreso > 0 else None
    )

    return {
        "id": proyecto.pk,
        "codigo": proyecto.codigo,
        "nombre": proyecto.nombre or proyecto.codigo,
        "cliente": proyecto.cliente.razon_social if proyecto.cliente_id else "—",
        "estado": proyecto.estado,
        "ingreso": float(ingreso),
        "costo_materiales": float(costo_mat),
        "utilidad_materiales": float(utilidad_mat),
        "margen_materiales_pct": margen_mat,
        "semaforo": semaforo_margen(margen_mat, cfg),
        # Mano de obra (puede no estar disponible).
        "horas": horas.get("horas", 0.0),
        "horas_medidas": horas.get("horas_medidas", 0.0),
        "horas_estimadas": horas.get("horas_estimadas", 0.0),
        "costo_mano_obra": float(costo_mo),
        "horas_estimadas_flag": bool(horas.get("estimado")),
        "costo_total": float(costo_total) if con_mo else None,
        "utilidad_total": float(utilidad_total) if con_mo else None,
        "margen_total_pct": margen_total if con_mo else None,
        "semaforo_total": semaforo_margen(margen_total, cfg) if con_mo else "sin_datos",
    }


def _rango_por_defecto() -> tuple[date, date]:
    hoy = date.today()
    return hoy.replace(year=hoy.year - 1), hoy


def tabla(*, desde: date | None = None, hasta: date | None = None,
          incluir_terminados: bool = True) -> list[dict]:
    """La rentabilidad de todos los proyectos, del peor margen al mejor."""
    from apps.los_proyectos.mano_obra import horas_por_proyecto
    from apps.los_proyectos.models import Proyecto

    if desde is None or hasta is None:
        desde, hasta = _rango_por_defecto()
    cfg = _cfg()

    try:
        horas_map = horas_por_proyecto(desde, hasta)
    except Exception:  # noqa: BLE001
        logger.warning("rentabilidad: sin datos de mano de obra", exc_info=True)
        horas_map = {}

    qs = Proyecto.objects.select_related("cliente").filter(archivado=False)
    if not incluir_terminados:
        qs = qs.exclude(estado__in=("cancelado", "cerrado"))

    filas = []
    for p in qs[:MAX_PROYECTOS]:
        try:
            filas.append(rentabilidad_de(p, horas_map.get(p.pk), cfg))
        except Exception:  # noqa: BLE001
            logger.warning("rentabilidad: falló el proyecto %s", p.pk, exc_info=True)
    # Peor margen primero; los que no tienen ingreso al final.
    return sorted(
        filas,
        key=lambda f: (f["margen_materiales_pct"] is None, f["margen_materiales_pct"] or 0),
    )


def resumen(filas: list[dict] | None = None, cfg=None) -> dict:
    """Los números gruesos: cuánto se facturó, cuánto costó y quién está en rojo."""
    cfg = cfg or _cfg()
    filas = tabla() if filas is None else filas
    con_ingreso = [f for f in filas if f["ingreso"] > 0]

    ingreso = sum(f["ingreso"] for f in con_ingreso)
    costo_mat = sum(f["costo_materiales"] for f in con_ingreso)
    costo_mo = sum(f["costo_mano_obra"] for f in con_ingreso)
    utilidad = ingreso - costo_mat

    bajo_umbral = [f for f in con_ingreso if f["semaforo"] == "amarillo"]
    en_perdida = [f for f in con_ingreso if f["semaforo"] == "rojo"]

    return {
        "proyectos": len(con_ingreso),
        "ingreso": round(ingreso, 2),
        "costo_materiales": round(costo_mat, 2),
        "costo_mano_obra": round(costo_mo, 2),
        "utilidad": round(utilidad, 2),
        "margen_pct": round(utilidad / ingreso * 100, 1) if ingreso else 0.0,
        "utilidad_con_mano_obra": round(utilidad - costo_mo, 2),
        "margen_con_mano_obra_pct": (
            round((utilidad - costo_mo) / ingreso * 100, 1) if ingreso else 0.0
        ),
        "margen_sano_pct": float(cfg.margen_sano_pct),
        "bajo_umbral": bajo_umbral[:10],
        "en_perdida": en_perdida[:10],
        "n_bajo_umbral": len(bajo_umbral),
        "n_en_perdida": len(en_perdida),
    }
