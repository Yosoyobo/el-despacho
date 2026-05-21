"""Filtros para presentar partidas en lenguaje no-contable.

Traducen el par cargo/abono + naturaleza de la cuenta a una sola
columna "Movimiento" con dirección "Entra"/"Sale". El código sigue
diciendo cargo/abono — esto es estrictamente UI.
"""

from django import template

register = template.Library()


@register.filter
def direccion_partida(partida):
    """'Entra' o 'Sale' según naturaleza de cuenta y cargo/abono.

    Cargo en deudora = Entra (sube el saldo).
    Cargo en acreedora = Sale (baja el saldo).
    Abono en deudora = Sale.
    Abono en acreedora = Entra.
    """
    if partida.cargo > 0:
        return "Entra" if partida.cuenta.naturaleza == "deudora" else "Sale"
    return "Sale" if partida.cuenta.naturaleza == "deudora" else "Entra"


@register.filter
def monto_partida(partida):
    """El monto > 0 sin importar de qué lado."""
    return partida.cargo if partida.cargo > 0 else partida.abono
