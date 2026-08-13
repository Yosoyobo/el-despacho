"""Poner en plural el nombre de un producto.

LC 2026-08-12 (Oscar): «cuando hay 1 producto, el título es Producción de
[Producto], en plural siempre». Así el documento de una cotización de un solo
elemento dice «Producción de Bandanas Rojas» y no «Producción de elementos
para proyecto 'Bandanas Rojas'», que no significa nada.

Reglas del español, aplicadas a la CABEZA del nombre: se pluraliza la primera
palabra y se sigue mientras la siguiente parezca un adjetivo en español (acaba
en vocal, `r`, `l` o `n`); a la primera que no lo parezca se detiene. Con eso
«Bandana Roja» → «Bandanas Rojas» y «Playera Dry Fit» → «Playeras Dry Fit»,
sin inventar «Drys Fits».

No es infalible con nombres de marca en inglés, y no pretende serlo: el título
del documento se puede escribir a mano en la página de la cotización, que es la
red para los casos raros.
"""

from __future__ import annotations

import re

VOCALES = "aeiou"
VOCALES_ACENTUADAS = "áéíóú"
# Terminaciones que en español delatan un adjetivo o sustantivo pluralizable.
FINALES_CONTINUABLES = VOCALES + VOCALES_ACENTUADAS + "rln"

# Palabras que nunca cambian (artículos, preposiciones y conjunciones que
# pueden aparecer dentro de un nombre: «Playera de Algodón»).
INVARIABLES = {"de", "del", "la", "las", "el", "los", "y", "e", "con", "para", "a", "en"}


def _es_plural(palabra: str) -> bool:
    """¿Ya viene en plural? («Bandanas», «Rojas»). También cubre invariables
    tipo «lunes» o «tórax», que se quedan igual."""
    bajo = palabra.lower()
    return len(bajo) > 2 and bajo[-1] in "sx"


def _pluralizar_palabra(palabra: str) -> str:
    """Una palabra en plural, conservando mayúsculas y puntuación de alrededor."""
    m = re.match(r"^(\W*)(.*?)(\W*)$", palabra, flags=re.UNICODE)
    if not m:
        return palabra
    izq, cuerpo, der = m.groups()
    if not cuerpo or _es_plural(cuerpo) or cuerpo.lower() in INVARIABLES:
        return palabra
    bajo = cuerpo.lower()
    if bajo[-1] in VOCALES:
        nuevo = cuerpo + "s"
    elif bajo[-1] == "z":
        nuevo = cuerpo[:-1] + ("Ces" if cuerpo[-1].isupper() else "ces")
    elif bajo[-1] in VOCALES_ACENTUADAS:
        nuevo = cuerpo + "es"
    else:
        nuevo = cuerpo + "es"
    return f"{izq}{nuevo}{der}"


def _continuable(palabra: str) -> bool:
    """¿La siguiente palabra se pluraliza junto con la cabeza?

    Sí si parece española (acaba en vocal, `r`, `l` o `n`) y no es una marca
    escrita en mayúsculas ni algo entre comillas — «NIKE RUN» o «'NIKE RUN'»
    se quedan tal cual.
    """
    limpia = re.sub(r"^\W+|\W+$", "", palabra, flags=re.UNICODE)
    if not limpia or limpia.isupper() or any(c.isdigit() for c in limpia):
        return False
    if limpia.lower() in INVARIABLES:
        return False
    return limpia[-1].lower() in FINALES_CONTINUABLES


def pluralizar(nombre: str) -> str:
    """El nombre de un producto en plural. Cadena vacía si no hay nombre."""
    texto = (nombre or "").strip()
    if not texto:
        return ""
    palabras = texto.split()
    salida: list[str] = []
    for i, palabra in enumerate(palabras):
        if i == 0:
            salida.append(_pluralizar_palabra(palabra))
            continue
        # Se sigue pluralizando mientras la palabra acompañe a la cabeza; en
        # cuanto aparece una marca, un número o algo que no es español, el
        # resto del nombre se copia tal cual.
        if _continuable(palabra) and all(_continuable(p) for p in palabras[1:i] or [palabra]):
            salida.append(_pluralizar_palabra(palabra))
        else:
            salida.extend(palabras[i:])
            break
    return " ".join(salida)
