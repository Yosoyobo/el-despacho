"""El embudo de ventas contado como se debe — fuente única.

Dos cosas que este módulo arregla y que antes deformaban todos los números:

1. **Se cuenta por oportunidad, no por documento.** Una cotización que va en su
   versión 3 no son tres oportunidades: es una sola, y lo que vale es su última
   versión. De 47 documentos, Learning Center tiene 25 oportunidades reales.

2. **Se clasifica por FASE, no por el nombre del estado.** El despacho renombra
   y apaga estados a su gusto; la fase (armada · enviada · ganada · perdida) es
   lo que el estado significa, y se configura en Gerencia.

Todo lo que hable de conversión, pipeline u oportunidades perdidas debe salir de
aquí. Es sólo lectura y no lanza: si algo falla, devuelve el embudo en ceros.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

# Tope defensivo: el embudo recorre en Python para quedarse con la última
# versión de cada proyecto. Con miles de documentos habría que mover el
# desempate a una Subquery; hoy el conjunto es de decenas.
MAX_DOCUMENTOS = 5000


def _cfg():
    from ajustes.models import ConfiguracionAnalisis
    return ConfiguracionAnalisis.obtener()


def oportunidades(qs=None) -> list:
    """La última versión de cada proyecto (más las cotizaciones sueltas).

    Una oportunidad = un proyecto que se cotizó. Las versiones anteriores son
    historia de esa misma oportunidad, no oportunidades nuevas.
    """
    from apps.cotizaciones.models import Cotizacion

    if qs is None:
        qs = Cotizacion.objects.all()
    # El total de cada cotización se calcula de sus líneas e impuestos: sin
    # prefetch serían dos consultas por documento.
    docs = list(
        qs.select_related("cliente", "proyecto")
        .prefetch_related("items", "impuestos__tasa")
        .order_by("proyecto_id", "-version", "-pk")[:MAX_DOCUMENTOS]
    )
    ultimas: list = []
    visto: set[int] = set()
    for doc in docs:
        if doc.proyecto_id is None:
            ultimas.append(doc)  # cotización suelta: cada una es su oportunidad
            continue
        if doc.proyecto_id in visto:
            continue
        visto.add(doc.proyecto_id)
        ultimas.append(doc)
    return ultimas


def fase_efectiva(cot) -> str:
    """En qué fase está esta cotización, de verdad.

    Normalmente es la fase de su estado. La excepción: si ya se le mandó al
    cliente (tiene sello de envío) pero su estado sigue configurado como
    "armada", manda el hecho — se envió. Así el conteo no depende de que el
    catálogo esté perfectamente configurado.
    """
    from apps.cotizaciones.models import FASE_ARMADA, FASE_ENVIADA, fase_de

    fase = fase_de(cot.estado)
    if fase == FASE_ARMADA and getattr(cot, "enviada_en", None):
        return FASE_ENVIADA
    return fase


def slug_destino(fase: str, fallback: str) -> str:
    """El slug del estado ACTIVO que representa esta fase.

    Si el despacho no tiene ninguno configurado (lo apagó, o nunca lo creó), se
    usa el fallback histórico para no dejar la transición sin destino.
    """
    from apps.cotizaciones.models.estado_cotizacion import _estados_raw

    for estado in _estados_raw():
        if estado.get("activo") and (estado.get("fase") or "armada") == fase:
            return estado["slug"]
    return fallback


def _dias_quieta(cot, hoy: date) -> int:
    """Días desde el último movimiento relevante de la cotización."""
    referencia = None
    if cot.enviada_en:
        referencia = cot.enviada_en.date()
    elif cot.fecha_emision:
        referencia = cot.fecha_emision
    elif cot.creado_en:
        referencia = cot.creado_en.date()
    return (hoy - referencia).days if referencia else 0


def embudo(*, hoy: date | None = None) -> dict:
    """Cómo va el pipeline, contado por oportunidad y clasificado por fase."""
    from apps.cotizaciones.models import (
        FASE_ARMADA,
        FASE_ENVIADA,
        FASE_GANADA,
        FASE_PERDIDA,
    )

    hoy = hoy or date.today()
    try:
        cfg = _cfg()
        dias_silencio = cfg.dias_silencio_cotizacion or 0
    except Exception:  # noqa: BLE001
        dias_silencio = 45

    vacio = {
        "armadas": 0, "enviadas": 0, "ganadas": 0, "perdidas": 0,
        "vivas": 0, "total": 0,
        "monto_vivo": 0.0, "monto_ganado": 0.0, "monto_perdido": 0.0,
        "conversion_pct": 0.0, "cierre_pct": 0.0,
        "sin_enviar": [], "enfriadas": [],
        "dias_silencio": dias_silencio,
    }

    try:
        docs = oportunidades()
    except Exception:  # noqa: BLE001
        logger.warning("embudo: no se pudieron leer las oportunidades", exc_info=True)
        return vacio

    conteo = {FASE_ARMADA: 0, FASE_ENVIADA: 0, FASE_GANADA: 0, FASE_PERDIDA: 0}
    montos = {FASE_ARMADA: Decimal("0"), FASE_ENVIADA: Decimal("0"),
              FASE_GANADA: Decimal("0"), FASE_PERDIDA: Decimal("0")}
    sin_enviar: list[dict] = []
    enfriadas: list[dict] = []

    for cot in docs:
        fase = fase_efectiva(cot)
        conteo[fase] = conteo.get(fase, 0) + 1
        try:
            total = Decimal(str(cot.calcular_totales()["total"]))
        except Exception:  # noqa: BLE001
            total = Decimal("0")
        montos[fase] = montos.get(fase, Decimal("0")) + total

        dias = _dias_quieta(cot, hoy)
        fila = {
            "id": cot.pk, "codigo": cot.codigo,
            "proyecto": (cot.proyecto.nombre if cot.proyecto else cot.titulo) or cot.codigo,
            "proyecto_id": cot.proyecto_id,
            "cliente": cot.cliente.razon_social if cot.cliente else "—",
            "dias": dias, "monto": float(total), "version": cot.version,
        }
        if fase == FASE_ARMADA and dias >= 7:
            sin_enviar.append(fila)
        elif fase == FASE_ENVIADA and dias_silencio and dias >= dias_silencio:
            enfriadas.append(fila)

    ganadas, perdidas = conteo[FASE_GANADA], conteo[FASE_PERDIDA]
    resueltas = ganadas + perdidas
    total = sum(conteo.values())
    vivas = conteo[FASE_ARMADA] + conteo[FASE_ENVIADA]

    return {
        "armadas": conteo[FASE_ARMADA],
        "enviadas": conteo[FASE_ENVIADA],
        "ganadas": ganadas,
        "perdidas": perdidas,
        "vivas": vivas,
        "total": total,
        "monto_vivo": float(montos[FASE_ARMADA] + montos[FASE_ENVIADA]),
        "monto_ganado": float(montos[FASE_GANADA]),
        "monto_perdido": float(montos[FASE_PERDIDA]),
        # De las que ya se resolvieron, cuántas se ganaron.
        "conversion_pct": round(ganadas / resueltas * 100, 1) if resueltas else 0.0,
        # De TODO lo cotizado, cuánto se ha cerrado (incluye lo que sigue vivo).
        "cierre_pct": round(ganadas / total * 100, 1) if total else 0.0,
        "sin_enviar": sorted(sin_enviar, key=lambda f: -f["dias"]),
        "enfriadas": sorted(enfriadas, key=lambda f: -f["dias"]),
        "dias_silencio": dias_silencio,
    }


def perdidas_del_periodo(desde: date, hasta: date) -> list[dict]:
    """Oportunidades que se cayeron en el periodo, con su motivo si lo hay."""
    from apps.cotizaciones.models import FASE_PERDIDA

    filas: list[dict] = []
    for cot in oportunidades():
        if fase_efectiva(cot) != FASE_PERDIDA:
            continue
        cuando = cot.rechazada_en or cot.anulada_en or cot.actualizado_en
        dia = cuando.date() if hasattr(cuando, "date") else cuando
        if dia and not (desde <= dia <= hasta):
            continue
        try:
            total = float(cot.calcular_totales()["total"])
        except Exception:  # noqa: BLE001
            total = 0.0
        filas.append({
            "id": cot.pk, "codigo": cot.codigo,
            "proyecto": (cot.proyecto.nombre if cot.proyecto else cot.titulo),
            "cliente": cot.cliente.razon_social if cot.cliente else "—",
            "fecha": dia.isoformat() if dia else "",
            "monto": total,
            "motivo": (cot.motivo_rechazo or cot.motivo_anulacion or "").strip(),
        })
    return sorted(filas, key=lambda f: f["fecha"], reverse=True)


def dias_desde_envio(cot, hoy: date | None = None) -> int:
    """Cuántos días lleva esta cotización sin moverse."""
    return _dias_quieta(cot, hoy or date.today())


def esta_enfriada(cot, hoy: date | None = None) -> bool:
    """¿Ya pasó el plazo de silencio que se configuró en Gerencia?"""
    from apps.cotizaciones.models import FASE_ENVIADA

    if fase_efectiva(cot) != FASE_ENVIADA:
        return False
    try:
        limite = _cfg().dias_silencio_cotizacion or 0
    except Exception:  # noqa: BLE001
        limite = 45
    return bool(limite) and dias_desde_envio(cot, hoy) >= limite


def ventana_dias(dias: int) -> tuple[date, date]:
    """Rango [desde, hoy] — helper para los reportes por periodo."""
    hoy = date.today()
    return hoy - timedelta(days=dias), hoy
