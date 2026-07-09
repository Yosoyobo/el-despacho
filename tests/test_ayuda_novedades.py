"""Candado: cada release debe traer su bloque de Novedades en el manual.

Contexto (para que NO vuelva a pasar): en el sprint 2026.07.01 se actualizó el
CUERPO del manual (`docs/DOC_05_MANUAL_USUARIO.md`, después de `## Bienvenida`)
pero se olvidó agregar el bloque `## Novedades — … (fecha)` al inicio, que es lo
que alimenta la sección **Ayuda → Novedades** y el badge del sidebar. Resultado:
la sección de Ayuda se veía "sin cambios" aunque el manual sí estaba al día.

Este test falla en CI si se bumpea `lib.version.VERSION_FECHA` a una fecha que
NO tiene su bloque de Novedades hasta arriba del manual. Arreglo = agregar el
bloque (regla §10 de CLAUDE.md). Es la última barrera antes del deploy.
"""

from __future__ import annotations

import re
from pathlib import Path

from lib.version import VERSION_FECHA

_DOC = Path(__file__).resolve().parents[1] / "docs" / "DOC_05_MANUAL_USUARIO.md"
# Captura la ÚLTIMA fecha entre paréntesis de cada encabezado `## Novedades …`.
_RE_NOVEDAD = re.compile(r"^##\s+Novedades\b.*\(([^()]+)\)\s*$", re.MULTILINE)


def _fechas_novedades() -> list[str]:
    texto = _DOC.read_text(encoding="utf-8")
    return [m.group(1).strip() for m in _RE_NOVEDAD.finditer(texto)]


def test_doc05_existe():
    assert _DOC.exists(), f"No se encontró el manual en {_DOC}"


def test_release_actual_tiene_bloque_de_novedades():
    fechas = _fechas_novedades()
    assert fechas, "DOC_05 no tiene ningún bloque `## Novedades — … (fecha)`."
    assert VERSION_FECHA in fechas, (
        f"VERSION_FECHA={VERSION_FECHA!r} no tiene un bloque de Novedades en el "
        f"manual. Antes de desplegar agrega, hasta arriba de DOC_05, un bloque "
        f"`## Novedades — <resumen en español llano> ({VERSION_FECHA})` "
        f"describiendo lo visible para el usuario (regla §10). "
        f"Fechas presentes: {fechas[:5]}"
    )


def test_bloque_mas_reciente_es_el_release_actual():
    """El bloque más nuevo (primero en el archivo) debe ser el release actual —
    el feed muestra 'más reciente primero'."""
    fechas = _fechas_novedades()
    primero = fechas[0] if fechas else "∅"
    assert primero == VERSION_FECHA, (
        f"El primer bloque de Novedades del manual es {primero!r} pero "
        f"VERSION_FECHA={VERSION_FECHA!r}. El release actual debe quedar hasta "
        f"arriba (más reciente primero)."
    )
