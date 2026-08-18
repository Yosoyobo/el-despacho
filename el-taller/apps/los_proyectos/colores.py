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
PALETA = (
    "#465fff",  # azul (el de siempre)
    "#e11d48",  # rojo
    "#059669",  # verde
    "#f59e0b",  # ámbar
    "#7c3aed",  # morado
    "#0891b2",  # turquesa
    "#db2777",  # rosa
    "#65a30d",  # olivo
    "#ea580c",  # naranja
    "#2563eb",  # azul rey
    "#be123c",  # vino
    "#0d9488",  # verde azulado
    "#c026d3",  # fucsia
    "#ca8a04",  # mostaza
    "#4338ca",  # índigo
    "#16a34a",  # verde pasto
    "#9f1239",  # granate
    "#0284c7",  # azul cielo
    "#a16207",  # bronce
    "#57534e",  # piedra
)

COLOR_DEFAULT = PALETA[0]

# ── Colores nombrados ────────────────────────────────────────────────────────
# Se leen del nombre visible y de la descripción de la línea. El orden importa:
# las combinaciones de dos palabras van ANTES que la palabra suelta, o «azul
# marino» se resolvería como «azul» a secas.
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


def color_del_texto(*textos) -> str:
    """El color que menciona el texto, o "" si no menciona ninguno.

    Empata por PALABRA COMPLETA: «Bandana Roja» sí, «Rojas Hermanas S.A.» sí
    (es la palabra), pero «Carroza» no se confunde con «rosa».
    """
    plano = " ".join(_plano(t) for t in textos if t)
    if not plano:
        return ""
    for palabras, hexa in COLORES_NOMBRADOS:
        for palabra in palabras:
            if re.search(rf"(?<![\w]){re.escape(palabra)}(?![\w])", plano):
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
