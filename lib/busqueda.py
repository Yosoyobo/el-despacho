"""Búsquedas que no se tropiezan con los acentos (LC 2026-08-18, Oscar).

«Busqué *numeros* buscando *Números Rojos* y no me lo mostró.» Un `icontains`
compara letra por letra, y para la base de datos la `ú` y la `u` son dos letras
distintas. Escribir el acento tampoco es la solución: nadie lo teclea al buscar,
y hay nombres capturados sin él.

La forma barata de arreglarlo sin tocar el esquema es buscar con una **expresión
regular** en la que cada vocal admite sus variantes: `numeros` se convierte en
`n[uúùüû]m[eéèëê]r[oóòöô]s`, que empata con «Numeros» y con «Números». Como el
texto que escribe el usuario también se despoja de acentos antes de armar el
patrón, funciona en los dos sentidos: buscar «Números» encuentra «Numeros».

**Por qué `iregex` y no la extensión `unaccent` de Postgres.** `unaccent` sería
más rápido, pero las pruebas del repo corren en SQLite y ahí no existe; el
`iregex` de Django funciona en los dos motores (en SQLite Django registra la
función REGEXP con el módulo `re` de Python). Con los volúmenes de Learning
Center la diferencia de velocidad no se nota: son listas de cientos de filas,
no de millones. Si algún día una tabla crece de verdad, el cambio a `unaccent`
se hace aquí dentro sin tocar a los que llaman.
"""

from __future__ import annotations

import re
import unicodedata

from django.db.models import Q

# Cada letra base con sus variantes acentuadas. La `ñ` entra en la clase de la
# `n` a propósito: quien busca «munecos» espera encontrar «muñecos».
_VARIANTES = {
    "a": "aáàäâãå",
    "e": "eéèëê",
    "i": "iíìïî",
    "o": "oóòöôõ",
    "u": "uúùüû",
    "n": "nñ",
    "c": "cç",
    "y": "yý",
}

# Tope defensivo: un patrón enorme no ayuda a nadie y sí castiga a la base.
MAX_TEXTO = 120


def sin_acentos(texto) -> str:
    """El texto en minúsculas y sin acentos («Números» → «numeros»)."""
    crudo = "" if texto is None else str(texto)
    plano = unicodedata.normalize("NFD", crudo)
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", plano).lower()


def patron(texto) -> str:
    """Expresión regular que empata el texto con o sin acentos.

    Devuelve "" si no hay nada que buscar. El texto se escapa antes de armar el
    patrón: quien busque «C++» o «(3 colores)» no debe romper la consulta.
    """
    base = sin_acentos(texto).strip()[:MAX_TEXTO]
    if not base:
        return ""
    piezas = []
    for letra in base:
        variantes = _VARIANTES.get(letra)
        piezas.append(f"[{variantes}]" if variantes else re.escape(letra))
    return "".join(piezas)


def q_texto(texto, *campos) -> Q:
    """`Q` que busca el texto —ignorando acentos— en cualquiera de los campos.

        qs.filter(q_texto(q, "nombre", "cliente__razon_social"))

    Con texto vacío o sin campos devuelve un `Q()` neutro, que no filtra nada:
    así el que llama puede usarlo sin envolverlo en un `if`.
    """
    pat = patron(texto)
    if not pat or not campos:
        return Q()
    filtro = Q()
    for campo in campos:
        filtro |= Q(**{f"{campo}__iregex": pat})
    return filtro


def contiene(texto, aguja) -> bool:
    """¿`aguja` aparece en `texto`, ignorando acentos y mayúsculas?

    La versión en Python de la misma regla, para filtrar listas ya cargadas en
    memoria (donde no hay consulta que hacer).
    """
    return sin_acentos(aguja).strip() in sin_acentos(texto)


__all__ = ["MAX_TEXTO", "contiene", "patron", "q_texto", "sin_acentos"]
