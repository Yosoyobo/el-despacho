"""«Generar» la descripción de un producto (LC 2026-10-14, ticket 13 de Oscar).

    «En el campo de descripción me encantaría un botón de “generar” que tome la
    info disponible, legible, y la escriba siguiendo el formato que siempre uso.»

El formato de siempre es el de `descripcion.py`:

    105 pz
    Gorras de gabardina 100% algodón deslavado
    Color: Beige
    Con bordado
    Frontal: Mantarraya - 4.5 - 5 cm de ancho

Este módulo arma ese texto **sólo con lo que el sistema sabe**: piezas, la
especificación del catálogo (o el nombre), la variación elegida y la impresión.
Es una plantilla determinista, sin IA — la misma entrada da siempre la misma
salida y no puede inventar nada. Lo que NO sabe (medidas, posición del bordado,
motivo) no se escribe: `faltantes()` lo dice, para que la persona lo complete.

Puro y sin base de datos: recibe objetos ya cargados (o cualquier cosa con esos
atributos), así que sirve igual para una tarjeta recién agregada que aún no se
guarda — la vista sólo resuelve los ids.

**Nunca pisa lo escrito.** `completar()` conserva el texto de la persona y le
suma lo que falte; reemplazar es una decisión de ella, no del sistema.
"""

from __future__ import annotations

import re
import unicodedata

from .descripcion import _RE_PIEZAS

# Lo que parece una medida: «4.5 cm», «30 x 40», «7 x 4», «12mm», «2 m».
_RE_MEDIDA = re.compile(r"\d+(?:[.,]\d+)?\s*(?:cm|mm|mts?|m|pulg)\b|\d+(?:[.,]\d+)?\s*[x×]\s*\d",
                        re.IGNORECASE)
_RE_NUMEROS = re.compile(r"\d+(?:[.,]\d+)?")


def _norm(texto: str) -> str:
    """Para comparar renglones: sin acentos, minúsculas y sin espacios ni signos."""
    plano = "".join(c for c in unicodedata.normalize("NFD", texto or "")
                    if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "", plano)


def _renglones(texto: str) -> list[str]:
    return [r.strip() for r in (texto or "").splitlines() if r.strip()]


def _colores_en(texto: str) -> list[str]:
    """Los colores que NOMBRA el texto, tal como están escritos (sin repetir).

    Usa la misma lista de colores nombrados que pinta las tarjetas
    (`los_proyectos.colores`) y compara sin acentos, pero devuelve la palabra
    original: «Azul Marino» sale «Azul Marino», no un código.
    """
    from apps.los_proyectos.colores import COLORES_NOMBRADOS

    texto = texto or ""
    # Texto «plano» (sin acentos, minúsculas) conservando el índice del original.
    plano, indice = [], []
    for i, ch in enumerate(texto):
        for c in unicodedata.normalize("NFD", ch):
            if unicodedata.category(c) != "Mn":
                plano.append(c.lower())
                indice.append(i)
    plano_s = "".join(plano)
    hallazgos: list[tuple[int, int, str]] = []
    for palabras, _hex in COLORES_NOMBRADOS:
        for palabra in palabras:
            for m in re.finditer(rf"(?<![\w]){re.escape(palabra)}(?![\w])", plano_s):
                ini, fin = indice[m.start()], indice[m.end() - 1] + 1
                hallazgos.append((ini, fin, texto[ini:fin]))
    # Gana la frase más larga si se encima («azul marino» sobre «azul»).
    hallazgos.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    salida, hasta = [], -1
    for ini, fin, palabra in hallazgos:
        if ini < hasta:
            continue
        hasta = fin
        if _norm(palabra) not in {_norm(s) for s in salida}:
            salida.append(palabra)
    return salida


def _mayus(texto: str) -> str:
    return texto[:1].upper() + texto[1:] if texto else texto


def _tecnicas(proveedor) -> list[str]:
    """Las técnicas que hace el proveedor de impresión, desde sus subcategorías
    del catálogo («Bordado», «Serigrafía»), en minúsculas. Vacío si no tiene."""
    if proveedor is None:
        return []
    try:
        subs = [s.nombre.strip() for s in proveedor.subcategorias.all() if s.nombre.strip()]
    except Exception:  # noqa: BLE001 — un proveedor sin guardar no tiene M2M
        return []
    return [s.lower() for s in subs]


def sugerir(*, cantidad: int, nombre: str = "", servicio=None, variacion=None,
            impresion_proveedor=None) -> str:
    """La descripción en el formato de siempre, con lo que se sabe.

    - Renglón 1: `N pz`.
    - Qué es: la especificación del catálogo; si no tiene, el nombre del producto.
    - La variación elegida (tela, talla, tamaño…) y, si nombra un color, el
      renglón `Color: …`.
    - Si lleva impresión: `Con <técnica>` (la del proveedor, o «impresión» si no
      se sabe) y el detalle que la variación tenga anotado (tintas, posición).

    Los procesos operativos (viáticos, clavos…) y los de venta NO entran: son
    costos internos, o ya salen como su propio renglón en la cotización.
    """
    lineas: list[str] = [f"{max(int(cantidad or 0), 0)} pz"]

    spec = _renglones(getattr(servicio, "descripcion_default", "") or "") if servicio else []
    if spec and _RE_PIEZAS.match(spec[0]):
        spec = spec[1:]  # el conteo es el de ESTA línea, no el del catálogo
    if spec:
        lineas += spec
    elif (nombre or "").strip():
        lineas.append(nombre.strip())

    imp_detalle = ""
    if variacion is not None:
        v_nombre = (getattr(variacion, "nombre", "") or "").strip()
        v_desc = (getattr(variacion, "descripcion", "") or "").strip()
        if v_nombre:
            lineas.append(", ".join(p.strip() for p in v_nombre.split("·") if p.strip()))
        if v_desc and _norm(v_desc) != _norm(v_nombre):
            lineas.append(v_desc)
        colores = _colores_en(f"{v_nombre} {v_desc}")
        if colores:
            lineas.append("Color: " + " / ".join(_mayus(c) for c in colores))
        if getattr(variacion, "impresion_activa", False):
            imp_detalle = (getattr(variacion, "impresion_descripcion", "") or "").strip()

    con_impresion = impresion_proveedor is not None or bool(imp_detalle)
    if con_impresion:
        tecnicas = _tecnicas(impresion_proveedor)
        lineas.append("Con " + (" y ".join(tecnicas) if tecnicas else "impresión"))
        if imp_detalle:
            lineas.append(_mayus(imp_detalle))

    # Sin repetidos (el catálogo y la variación suelen decir lo mismo).
    vistos, salida = set(), []
    for r in lineas:
        k = _norm(r)
        if k and k not in vistos:
            vistos.add(k)
            salida.append(r)
    return "\n".join(salida)


def faltantes(texto: str) -> list[str]:
    """Lo que el formato de siempre suele llevar y este texto no trae.

    Sirve para decirle a la persona «esto lo completas tú»: el sistema no lo
    sabe y NO lo inventa.
    """
    renglones = _renglones(texto)
    falta = []
    if not any(_norm(r).startswith("color") for r in renglones):
        falta.append("color")
    if not _RE_MEDIDA.search(texto or ""):
        falta.append("medidas")
    return falta


def completar(existente: str, sugerida: str) -> str:
    """Lo escrito por la persona + lo que le faltaba, sin pisar nada.

    El texto de ella se conserva tal cual (su primer renglón de piezas sólo se
    actualiza en el número, igual que hace la cotización al heredar); de la
    sugerencia se suman los renglones que no estén ya dichos, en el orden en que
    vienen.
    """
    mios = _renglones(existente)
    suyas = _renglones(sugerida)
    if not mios:
        return "\n".join(suyas)
    if not suyas:
        return "\n".join(mios)

    piezas_nuevas = suyas[0] if _RE_PIEZAS.match(suyas[0]) else ""
    if piezas_nuevas:
        n = _RE_PIEZAS.match(piezas_nuevas).group(2)
        if _RE_PIEZAS.match(mios[0]):
            mios[0] = _RE_PIEZAS.sub(rf"\g<1>{n}\g<3>", mios[0], count=1)
        else:
            mios.insert(0, piezas_nuevas)
        suyas = suyas[1:]

    ya = [_norm(r) for r in mios]
    for r in suyas:
        k = _norm(r)
        # «Ya dicho» incluye que mi renglón lo contenga o él contenga al mío.
        if any(k in y or y in k for y in ya if y):
            continue
        mios.append(r)
        ya.append(k)
    return "\n".join(mios)


def numeros_de(texto: str) -> set[str]:
    """Las cifras que aparecen en un texto, normalizadas («4,5» = «4.5»)."""
    return {n.replace(",", ".") for n in _RE_NUMEROS.findall(texto or "")}


def sin_cifras_inventadas(salida: str, *fuentes: str) -> bool:
    """True si TODA cifra de `salida` ya estaba en alguna de las fuentes.

    Es la red de seguridad del camino con IA: un modelo que «redacta» puede
    meter una medida o una cantidad que nadie le dio. No se puede verificar todo
    lo que dice, pero un número que no viene de los datos es la mentira más
    cara en una cotización — ésa sí se caza.
    """
    permitidas: set[str] = set()
    for f in fuentes:
        permitidas |= numeros_de(f)
    return numeros_de(salida) <= permitidas


__all__ = ["sugerir", "faltantes", "completar", "numeros_de", "sin_cifras_inventadas"]
