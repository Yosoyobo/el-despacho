"""El color de cada tarjeta de producto del proyecto (LC 2026-08-18, Oscar).

«¿Por qué mis productos involucrados son todos verdes, azules, uno naranja aquí
o allá? Los necesito 100% variados y contrastados, y sólidamente ligados a cada
uno de sus productos. Si en el nombre o descripción se menciona un color, usar
ese.»

Tres reglas, en este orden:

1. **Si el nombre o la descripción dicen un color, ése es el color.** «Playera
   dry fit negra» sale en negro y «Bandana roja» en rojo, sin que nadie lo
   configure. Como se deriva del texto, renombrar la línea cambia su color al
   instante.
2. **Si no, se toma el siguiente color LIBRE de la lista**, en orden, y se
   **guarda** en la línea (`ProyectoProducto.color`). Guardarlo es lo que lo
   hace «sólidamente ligado»: no vuelve a moverse aunque la arrastres, la
   apagues, borres otra o agregues diez más. Es justo lo que se rompió en su
   momento con `{% cycle %}`, que repartía el color por POSICIÓN.
3. Una línea vieja que todavía no tenga color guardado cae a un color derivado
   de su nombre, para que nunca se vea sin identidad.

**Quién gana cuando hay varios colores en juego** (LC 2026-08-18 R2, Oscar:
«"Números Azules" se debería de pintar azul — seguir alias antes que nombre»).
Dos desempates, y los dos importan:

- **Entre TEXTOS manda el orden en que se pasan**: primero el alias del
  proyecto, luego el nombre del catálogo y al final la descripción. Antes los
  tres iban concatenados, así que una línea llamada «Números Azules» sobre un
  producto de catálogo «Playera Roja» salía ROJA: se buscaba color por color en
  el orden de esta lista, y el rojo está antes que el azul.
- **Dentro de un texto manda el que se menciona PRIMERO**, y a igual posición
  la frase más larga («azul marino» le gana a «azul»). Antes mandaba el orden de
  la lista de colores, que no tiene nada que ver con lo que dice el nombre.

La lista tiene 20 colores ordenados de modo que **dos consecutivos nunca sean
del mismo tono** — como se reparten en orden de captura, los productos de un
mismo proyecto salen siempre contrastados entre sí.

El color viaja como HEX y se pinta con `--ec` + `color-mix`, el mismo sistema
de las pastillas de estado (S-Estados-Color-HEX): un solo dato sirve para el
fondo tenue, el borde y el texto, en claro y en oscuro.
"""

from __future__ import annotations

import re
import unicodedata

# ── La lista, en orden de reparto ────────────────────────────────────────────
# Arranca con el azul de la casa (el que ya tenían todas las tarjetas) y de ahí
# salta de tono en tono. Son colores medios: al 14% dan un fondo tenue legible
# y al 78% un texto con contraste suficiente.
#
# LC 2026-08-18 R2 (Oscar: «amarillo (feo)»): el ámbar `#f59e0b` era el cuarto
# en repartirse, así que un proyecto de cuatro productos casi siempre lo sacaba.
# Los amarillos bajaron a la segunda mitad de la lista y su lugar lo tomaron
# tonos que se leen mejor en tarjeta (morado, naranja quemado, turquesa).
PALETA = (
    "#465fff",  # azul (el de siempre)
    "#e11d48",  # rojo
    "#059669",  # verde
    "#7c3aed",  # morado
    "#ea580c",  # naranja
    "#0891b2",  # turquesa
    "#db2777",  # rosa
    "#65a30d",  # olivo
    "#4338ca",  # índigo
    "#0284c7",  # azul cielo
    "#be123c",  # vino
    "#16a34a",  # verde pasto
    "#c026d3",  # fucsia
    "#0d9488",  # verde azulado
    "#ca8a04",  # mostaza
    "#9f1239",  # granate
    "#2563eb",  # azul rey
    "#a16207",  # bronce
    "#7e22ce",  # violeta
    "#57534e",  # piedra
)

COLOR_DEFAULT = PALETA[0]

# ── Colores nombrados ────────────────────────────────────────────────────────
# Se leen del nombre visible y de la descripción de la línea. Las combinaciones
# de dos palabras conviven con la palabra suelta: a igual posición en el texto
# gana la más larga, así «azul marino» no se resuelve como «azul» a secas (ver
# `_color_en`). El orden de esta lista ya NO decide nada — decide el texto.
#
# El negro y el blanco no se pintan de negro y blanco literales: uno daría un
# fondo sucio y el otro sería invisible. Se usan sus grises equivalentes, que es
# como se leen en un catálogo.
COLORES_NOMBRADOS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("azul marino", "marino", "azul rey"), "#1e3a8a"),
    (("azul cielo", "celeste", "cielo"), "#0284c7"),
    (("verde limon", "limon", "verde lima", "lima"), "#65a30d"),
    (("verde menta", "menta"), "#10b981"),
    (("verde militar", "militar", "olivo", "aceituna"), "#4d7c0f"),
    (("rojo", "roja", "rojos", "rojas", "escarlata"), "#e11d48"),
    (("azul", "azules", "azulado"), "#465fff"),
    (("verde", "verdes"), "#059669"),
    (("amarillo", "amarilla", "amarillos", "amarillas"), "#ca8a04"),
    (("mostaza",), "#ca8a04"),
    (("naranja", "anaranjado", "anaranjada"), "#ea580c"),
    (("morado", "morada", "lila", "violeta", "purpura", "uva"), "#7c3aed"),
    (("fucsia", "magenta"), "#c026d3"),
    (("rosa", "rosado", "rosada", "rosas", "pink"), "#db2777"),
    (("turquesa", "aqua", "cian"), "#0891b2"),
    (("vino", "guinda", "borgona", "burdeos"), "#9f1239"),
    (("coral", "salmon", "durazno"), "#fb7185"),
    (("cafe", "marron", "chocolate", "capuchino"), "#92400e"),
    (("dorado", "oro", "gold"), "#b45309"),
    (("bronce", "cobre", "caqui", "khaki"), "#a16207"),
    (("plata", "plateado", "plateada"), "#a1a1aa"),
    (("beige", "crema", "hueso", "arena", "nude"), "#a8a29e"),
    (("gris", "grises", "grafito"), "#64748b"),
    (("negro", "negra", "negros", "negras"), "#1f2937"),
    (("blanco", "blanca", "blancos", "blancas"), "#94a3b8"),
)

HEX_VALIDO = re.compile(r"^#[0-9a-fA-F]{6}$")


def _plano(texto) -> str:
    """Minúsculas y sin acentos, para poder buscar «marrón» escrito «marron»."""
    crudo = "" if texto is None else str(texto)
    desarmado = unicodedata.normalize("NFD", crudo)
    return "".join(c for c in desarmado if unicodedata.category(c) != "Mn").lower()


def _color_en(texto) -> str:
    """El color que menciona UN texto, o "" si no menciona ninguno.

    Gana el que aparece ANTES en el texto; a igual posición, la frase más larga
    («azul marino» sobre «azul»). Empata por palabra completa, así que «Bandana
    Roja» sí y «Carroza» no se confunde con «rosa».
    """
    plano = _plano(texto)
    if not plano.strip():
        return ""
    mejor_pos: int | None = None
    mejor_hex = ""
    mejor_largo = 0
    for palabras, hexa in COLORES_NOMBRADOS:
        for palabra in palabras:
            hallazgo = re.search(rf"(?<![\w]){re.escape(palabra)}(?![\w])", plano)
            if not hallazgo:
                continue
            pos, largo = hallazgo.start(), len(palabra)
            if mejor_pos is None or pos < mejor_pos or (pos == mejor_pos and largo > mejor_largo):
                mejor_pos, mejor_hex, mejor_largo = pos, hexa, largo
    return mejor_hex


def color_del_texto(*textos) -> str:
    """El color que mencionan los textos, o "" si ninguno menciona uno.

    Los textos se revisan **en el orden en que se pasan** y se devuelve el
    primero que dé color: quien llama decide la prioridad. Los consumidores del
    repo pasan alias → nombre del catálogo → descripción, que es la regla que
    pidió Oscar (2026-08-18 R2).
    """
    for texto in textos:
        hexa = _color_en(texto)
        if hexa:
            return hexa
    return ""


def color_estable(*textos) -> str:
    """Color derivado del texto — siempre el mismo para el mismo nombre.

    Es el paracaídas de las líneas viejas, que todavía no tienen color guardado.
    Determinista a propósito: nada de `hash()`, que cambia entre procesos.
    """
    plano = " ".join(_plano(t) for t in textos if t).strip()
    if not plano:
        return COLOR_DEFAULT
    semilla = 0
    for c in plano:
        semilla = (semilla * 31 + ord(c)) % 1_000_003
    return PALETA[semilla % len(PALETA)]


def elegir_color_libre(usados) -> str:
    """El primer color de la lista que no esté ocupado, en orden.

    `usados` es cualquier iterable de HEX. Si ya se agotaron los 20 (un proyecto
    con más de veinte productos), se vuelve a empezar por el principio: repetir
    un color es mejor que dejar la tarjeta sin identidad.
    """
    ocupados = {str(c).lower() for c in usados if c}
    for hexa in PALETA:
        if hexa not in ocupados:
            return hexa
    return PALETA[len(ocupados) % len(PALETA)]


def normalizar(valor) -> str:
    """HEX válido en minúsculas, o "" si no lo es. Nunca lanza."""
    crudo = str(valor or "").strip()
    return crudo.lower() if HEX_VALIDO.match(crudo) else ""


__all__ = [
    "COLORES_NOMBRADOS",
    "COLOR_DEFAULT",
    "PALETA",
    "color_del_texto",
    "color_estable",
    "elegir_color_libre",
    "normalizar",
]
