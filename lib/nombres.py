"""Comparar nombres de empresa como los diría una persona.

«MARKETING VEINTITRÉS GRADOS, S.A. DE C.V.» y «marketing veintitres grados»
son el mismo cliente. Aquí vive el criterio para decidir eso: sin acentos, sin
puntuación, sin la terminación mercantil, en minúsculas.

**Duplica a propósito el criterio de `el_dictado/ejecutores/basicos.py`.** Ese
módulo vive en una app de El Taller y La Gerencia no la instala (por eso
existen los shadow models de `chalanes/`), así que `papeleo/` —que es app
compartida— no puede importarlo. Unificarlos es lo correcto y está anotado
como deuda: se hace moviendo el de `basicos.py` a este archivo, con la suite
de los ejecutores del Chalán como red. No se hizo aquí para no meterle riesgo
a esos ejecutores en un sprint que ya toca cuatro frentes.
"""

from __future__ import annotations

import re
import unicodedata

#: Terminaciones que no distinguen a una empresa de otra.
SUFIJOS_MERCANTILES = (
    "s de rl de cv mi", "sapi de cv", "s a p i de c v", "sa de cv",
    "s a de c v", "sa de c v", "s de rl de cv", "s de r l de c v",
    "srl de cv", "s c", "sc", "ac", "a c", "sa", "s a", "sofom",
    "spr de rl", "s a s", "sas",
)


def normalizar(texto: str) -> str:
    """Deja un nombre comparable: sin acentos, sin puntuación, sin terminación
    mercantil y en minúsculas."""
    base = unicodedata.normalize("NFKD", str(texto or ""))
    base = "".join(c for c in base if not unicodedata.combining(c)).lower()
    base = re.sub(r"[^a-z0-9ñ ]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    for suf in SUFIJOS_MERCANTILES:
        if base.endswith(" " + suf):
            base = base[: -(len(suf) + 1)].strip()
            break
    return base


def compacto(texto: str) -> str:
    """El nombre normalizado y SIN espacios: «KARI KARI» → «karikari».

    Es la forma en que un humano lo dicta de corrido. `normalizar` es
    idempotente, así que sirve con el texto crudo o ya normalizado.
    """
    return normalizar(texto).replace(" ", "")


def menciona(texto_largo: str, nombre: str, minimo: int = 6) -> bool:
    """¿El texto largo menciona ese nombre?

    `minimo` es la salvaguarda que evita el falso positivo tonto: un nombre de
    tres letras aparece por casualidad dentro de cualquier palabra, y ligaría
    documentos que no son. Con nombres cortos, mejor no ligar nada.
    """
    aguja = normalizar(nombre)
    if len(aguja) < max(1, minimo):
        return False
    return aguja in normalizar(texto_largo)


__all__ = ["SUFIJOS_MERCANTILES", "compacto", "menciona", "normalizar"]
