"""Capabilities que un Chalán declara soportar.

Los Analistas v1 asumían que todos hacen TEXTO. v2 agrega VISION (imágenes)
para OCR de recibos y FUNCTION_CALLING para extracciones estructuradas.
El Reemplazo salta Chalanes que no soportan la capacidad requerida.
"""

from __future__ import annotations

from enum import Enum


class Capability(str, Enum):
    TEXTO = "texto"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"


class SinCapacidad(Exception):
    """El Chalán no soporta lo que se le pidió (ej. visión)."""
