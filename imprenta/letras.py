"""El monto en letra, como se escribe en un recibo en México.

`monto_en_letra(Decimal("1250.50"))` → «MIL DOSCIENTOS CINCUENTA PESOS 50/100 M.N.»

Sin dependencias: son unas reglas que no cambian, y una librería para esto es
una pieza más que actualizar en tres imágenes.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_UNIDADES = ("", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE",
             "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISÉIS", "DIECISIETE",
             "DIECIOCHO", "DIECINUEVE", "VEINTE", "VEINTIUNO", "VEINTIDÓS", "VEINTITRÉS",
             "VEINTICUATRO", "VEINTICINCO", "VEINTISÉIS", "VEINTISIETE", "VEINTIOCHO",
             "VEINTINUEVE")
_DECENAS = ("", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA",
            "NOVENTA")
_CENTENAS = ("", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS",
             "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS")

_MONEDAS = {
    "MXN": ("PESO", "PESOS", "M.N."),
    "USD": ("DÓLAR", "DÓLARES", "USD"),
    "EUR": ("EURO", "EUROS", "EUR"),
}


def _menor_de_mil(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    c, resto = divmod(n, 100)
    partes = [_CENTENAS[c]] if c else []
    if resto < 30:
        partes.append(_UNIDADES[resto])
    else:
        d, u = divmod(resto, 10)
        partes.append(_DECENAS[d] + (f" Y {_UNIDADES[u]}" if u else ""))
    return " ".join(p for p in partes if p)


def _apocope(texto: str) -> str:
    """«UNO» → «UN» delante de un sustantivo (MIL, MILLONES, PESOS)."""
    if texto.endswith("VEINTIUNO"):
        return texto[: -len("VEINTIUNO")] + "VEINTIÚN"
    if texto.endswith("UNO"):
        return texto[:-1]
    return texto


def _entero(n: int) -> str:
    """El número entero en letra (hasta cientos de miles de millones)."""
    if n == 0:
        return "CERO"
    millones, resto = divmod(n, 1_000_000)
    miles, unidades = divmod(resto, 1000)
    partes = []
    if millones:
        partes.append("UN MILLÓN" if millones == 1 else f"{_apocope(_entero(millones))} MILLONES")
    if miles:
        partes.append("MIL" if miles == 1 else f"{_apocope(_menor_de_mil(miles))} MIL")
    if unidades:
        partes.append(_menor_de_mil(unidades))
    return " ".join(partes)


def monto_en_letra(monto, moneda: str = "MXN") -> str:
    """«MIL DOSCIENTOS CINCUENTA PESOS 50/100 M.N.»

    Antes de «PESOS», «UNO» se apocopa («UN PESO», «VEINTIÚN PESOS»), y los
    millones exactos llevan «DE» («UN MILLÓN DE PESOS»), como en un cheque.
    """
    valor = Decimal(str(monto or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negativo = valor < 0
    valor = abs(valor)
    enteros = int(valor)
    centavos = int((valor - enteros) * 100)
    singular, plural, sufijo = _MONEDAS.get((moneda or "MXN").upper(), _MONEDAS["MXN"])
    texto = _apocope(_entero(enteros))
    if enteros and enteros % 1_000_000 == 0:
        texto += " DE"
    nombre = singular if enteros == 1 else plural
    resultado = f"{texto} {nombre} {centavos:02d}/100 {sufijo}"
    return f"MENOS {resultado}" if negativo else resultado


__all__ = ["monto_en_letra"]
