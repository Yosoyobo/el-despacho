"""El número detrás de lo que enseña un KPI.

Muchos indicadores devuelven su valor ya formateado para la tarjeta
(`"$12,345"`, `"32%"`). Eso está bien para pintarlo, pero todo lo que JUZGA
—la foto diaria, las metas, los umbrales, las rarezas— necesita el número.
Hasta 2026-09-29 la foto diaria se saltaba cualquier valor de texto, así que
ningún KPI de dinero tenía historia: la tendencia, la comparación y las metas
propuestas del dinero nunca funcionaron.

`numero_de()` es la única forma de sacar ese número. Si el resultado trae la
llave `numero`, manda ésa; si no, se interpreta `valor`.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

# Lo que un KPI pinta cuando no tiene número: no es un cero.
_SIN_NUMERO = {"", "—", "-", "?", "n/d", "s/d"}


def numero_de(valor) -> float | None:
    """`12`, `12.5`, `Decimal`, `"$12,345"`, `"$-5"`, `"32%"`, `"1.5 h"` → float.

    Devuelve `None` (no 0) cuando el valor no es un número: un «—» significa
    «no se pudo medir», y convertirlo en cero haría que la meta y la foto
    diaria mintieran.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int | float | Decimal):
        return float(valor)
    if not isinstance(valor, str):
        return None
    texto = valor.strip().lower()
    if texto in _SIN_NUMERO:
        return None
    limpio = (
        texto.replace("$", "").replace(",", "").replace("%", "")
        .replace("mxn", "").replace("usd", "").strip()
    )
    # «1.5 h», «12 días»: el número va primero.
    primero = limpio.split()[0] if limpio else ""
    try:
        return float(Decimal(primero))
    except (InvalidOperation, ValueError):
        return None


def numero_del_resultado(resultado: dict | None) -> float | None:
    """El número de un `{valor, nota, link[, numero]}` de `KPI.calcular()`."""
    if not resultado:
        return None
    if resultado.get("numero") is not None:
        return numero_de(resultado["numero"])
    return numero_de(resultado.get("valor"))


def formatear(numero: float | None, formato: str) -> str:
    """El número en la forma en que se lee ese KPI (para metas y umbrales)."""
    if numero is None:
        return "—"
    if formato == "dinero":
        return f"${numero:,.0f}"
    if formato == "pct":
        return f"{numero:,.1f}%".replace(".0%", "%")
    if formato == "dias":
        return f"{numero:,.1f} días".replace(".0 días", " días")
    if formato == "horas":
        return f"{numero:,.1f} h".replace(".0 h", " h")
    if formato == "minutos":
        return f"{numero:,.0f} min"
    if formato == "km":
        return f"{numero:,.1f} km".replace(".0 km", " km")
    if float(numero).is_integer():
        return f"{int(numero):,}"
    return f"{numero:,.2f}"
