"""Qué hacer con la memoria de los indicadores: tendencia, comparación y rarezas.

Tres preguntas que un tablero no puede contestar y un analista sí:

- **¿Cómo viene?** La serie de los últimos días, para verla de un vistazo.
- **¿Mejor o peor que antes?** El valor de este periodo contra el anterior.
- **¿Esto es normal?** Si el número de hoy se sale de lo que suele ser.

Lo de las rarezas se hace **sin IA**: se compara contra la mediana de la propia
historia del indicador. La mediana y no el promedio a propósito — un solo día
raro mueve mucho el promedio y entonces el detector deja de detectar justo
después de la primera rareza, que es cuando más falta hace.

Todo es sólo lectura y defensivo: si no hay historia, se dice que no hay, en vez
de inventar una tendencia con dos puntos.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

# Cuántas muestras se necesitan para hablar de "lo normal". Con menos, cualquier
# cosa parece una anomalía y el aviso se vuelve ruido.
MINIMO_PARA_JUZGAR = 7
# Cuánto se puede desviar de su mediana antes de llamarlo raro.
DESVIACION_RARA = Decimal("0.40")   # 40%


def _cfg():
    from ajustes.models import ConfiguracionAnalisis
    return ConfiguracionAnalisis.obtener()


# ── Guardar ──────────────────────────────────────────────────────────────

def guardar(kpi_slug: str, valor, *, dia: date | None = None, nota: str = "") -> bool:
    """Anota el valor de hoy. Idempotente: repetir el mismo día actualiza."""
    from apps.taller_home.models import SnapshotKPI

    dia = dia or date.today()
    try:
        numero = Decimal(str(valor if valor is not None else 0))
    except Exception:  # noqa: BLE001 — un KPI que no da número no se guarda
        return False
    try:
        SnapshotKPI.objects.update_or_create(
            kpi_slug=kpi_slug, fecha=dia,
            defaults={"valor": numero, "nota": (nota or "")[:200]},
        )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("no se pudo guardar la foto de %s", kpi_slug, exc_info=True)
        return False


# ── Leer ─────────────────────────────────────────────────────────────────

def serie(kpi_slug: str, *, dias: int = 30) -> list[dict]:
    """Los últimos N días de un indicador, del más viejo al más nuevo."""
    from apps.taller_home.models import SnapshotKPI

    desde = date.today() - timedelta(days=dias)
    filas = SnapshotKPI.objects.filter(
        kpi_slug=kpi_slug, fecha__gte=desde,
    ).order_by("fecha").values("fecha", "valor", "nota")
    return [
        {"fecha": f["fecha"].isoformat(), "valor": float(f["valor"]), "nota": f["nota"]}
        for f in filas
    ]


def _valores(kpi_slug: str, desde: date, hasta: date) -> list[Decimal]:
    from apps.taller_home.models import SnapshotKPI

    return list(
        SnapshotKPI.objects.filter(
            kpi_slug=kpi_slug, fecha__gte=desde, fecha__lte=hasta,
        ).order_by("fecha").values_list("valor", flat=True)
    )


def _mediana(valores: list[Decimal]) -> Decimal | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    mitad = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[mitad]
    return (ordenados[mitad - 1] + ordenados[mitad]) / 2


def comparar(kpi_slug: str, *, dias: int = 30) -> dict:
    """Este periodo contra el anterior del mismo largo.

    Devuelve `{hay_datos, actual, anterior, cambio_pct, direccion}`. Si no hay
    con qué comparar lo dice — no se inventa un 0%.
    """
    hoy = date.today()
    ini_actual = hoy - timedelta(days=dias - 1)
    ini_previo = ini_actual - timedelta(days=dias)
    fin_previo = ini_actual - timedelta(days=1)

    actual = _valores(kpi_slug, ini_actual, hoy)
    previo = _valores(kpi_slug, ini_previo, fin_previo)
    if not actual or not previo:
        return {"hay_datos": False, "actual": None, "anterior": None,
                "cambio_pct": None, "direccion": "sin_datos"}

    # El último valor del periodo representa al periodo para los acumulados
    # (ingresos del mes); para los que oscilan, la mediana es más justa. Se usa
    # la mediana en ambos: es la lectura conservadora.
    a, p = _mediana(actual), _mediana(previo)
    if p in (None, 0):
        return {"hay_datos": True, "actual": float(a or 0), "anterior": float(p or 0),
                "cambio_pct": None, "direccion": "sin_base"}
    cambio = (a - p) / abs(p) * 100
    return {
        "hay_datos": True,
        "actual": float(a), "anterior": float(p),
        "cambio_pct": round(float(cambio), 1),
        "direccion": "subio" if cambio > 0 else ("bajo" if cambio < 0 else "igual"),
    }


def tendencia(kpi_slug: str, *, dias: int = 14) -> str:
    """subiendo | bajando | estable | sin_datos — mirando la primera mitad
    contra la segunda, que aguanta mejor un día raro que una recta ajustada."""
    hoy = date.today()
    valores = _valores(kpi_slug, hoy - timedelta(days=dias - 1), hoy)
    if len(valores) < 4:
        return "sin_datos"
    mitad = len(valores) // 2
    vieja, nueva = _mediana(valores[:mitad]), _mediana(valores[mitad:])
    if vieja in (None, 0) or nueva is None:
        return "sin_datos"
    cambio = (nueva - vieja) / abs(vieja)
    if cambio > Decimal("0.10"):
        return "subiendo"
    if cambio < Decimal("-0.10"):
        return "bajando"
    return "estable"


def es_raro(kpi_slug: str, valor_hoy, *, dias: int = 30) -> dict:
    """¿El número de hoy se salió de lo normal para este indicador?

    Compara contra la MEDIANA de su propia historia. Sin suficientes muestras
    no opina: con tres días, todo parece una anomalía.
    """
    hoy = date.today()
    historia = _valores(kpi_slug, hoy - timedelta(days=dias), hoy - timedelta(days=1))
    if len(historia) < MINIMO_PARA_JUZGAR:
        return {"raro": False, "motivo": "poca_historia", "muestras": len(historia)}

    base = _mediana(historia)
    if base is None or base == 0:
        return {"raro": False, "motivo": "sin_base", "muestras": len(historia)}
    try:
        actual = Decimal(str(valor_hoy if valor_hoy is not None else 0))
    except Exception:  # noqa: BLE001
        return {"raro": False, "motivo": "sin_valor", "muestras": len(historia)}

    desviacion = (actual - base) / abs(base)
    limite = DESVIACION_RARA
    if abs(desviacion) < limite:
        return {"raro": False, "motivo": "normal", "muestras": len(historia),
                "mediana": float(base), "desviacion_pct": round(float(desviacion * 100), 1)}
    return {
        "raro": True,
        "motivo": "arriba" if desviacion > 0 else "abajo",
        "muestras": len(historia),
        "mediana": float(base),
        "actual": float(actual),
        "desviacion_pct": round(float(desviacion * 100), 1),
    }


def meta_sugerida(kpi_slug: str, *, dias: int = 90) -> dict:
    """Una meta realista a partir de lo que de verdad se ha hecho.

    Se apoya en la mediana de los últimos meses y le pide un poco más (10%).
    Es un punto de partida para que alguien decida, no una imposición: la meta
    la aprueba una persona.
    """
    hoy = date.today()
    historia = _valores(kpi_slug, hoy - timedelta(days=dias), hoy)
    if len(historia) < MINIMO_PARA_JUZGAR:
        return {"hay_datos": False, "muestras": len(historia)}
    base = _mediana(historia)
    if base is None:
        return {"hay_datos": False, "muestras": len(historia)}
    return {
        "hay_datos": True,
        "muestras": len(historia),
        "tipico": float(base),
        "sugerida": float((base * Decimal("1.10")).quantize(Decimal("0.01"))),
        "mejor": float(max(historia)),
        "peor": float(min(historia)),
    }


def resumen(kpi_slug: str, valor_actual=None) -> dict:
    """Todo lo que se sabe de un indicador: cómo viene, contra qué, y si es raro."""
    return {
        "slug": kpi_slug,
        "serie": serie(kpi_slug, dias=30),
        "tendencia": tendencia(kpi_slug),
        "comparacion": comparar(kpi_slug),
        "anomalia": es_raro(kpi_slug, valor_actual) if valor_actual is not None else None,
    }
