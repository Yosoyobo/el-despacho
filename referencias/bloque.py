"""Bloque `[REFERENCIAS RESUELTAS]` para prompts de IA.

Resuelve los `@usuario/#proyecto/$cliente` de un texto a entidades reales y
arma un bloque legible para que el LLM sepa EXACTAMENTE a qué se refiere el
usuario. Sin esto el modelo recibe `#exte` a secas y pide "el código (LC-0001)"
aunque el usuario ya lo mencionó con `#`.

Fuente única usada por El Chalán (chat) y El Dictado (interpretación estándar +
clarificaciones) — un solo lugar que mantener si cambia el formato del bloque.
Reusa el parser/resolver de `referencias`. Nunca lanza: cualquier fallo
(parser, DB) devuelve "" para no tumbar el flujo de IA.
"""

from __future__ import annotations


def bloque_prompt(texto: str) -> str:
    """Devuelve el bloque `[REFERENCIAS RESUELTAS]` o "" si no hay tokens."""
    try:
        from .parser import extraer_tokens
        from .resolver import resolver_tokens
    except Exception:  # noqa: BLE001 — nunca tumbar el flujo de IA por esto
        return ""

    tokens = extraer_tokens(texto or "")
    if not tokens:
        return ""

    try:
        resuelto = resolver_tokens(tokens)
    except Exception:  # noqa: BLE001 — DB caída, etc.
        return ""

    lineas: list[str] = []
    vistos: set[tuple] = set()
    for t in tokens:
        clave = (t.tipo, t.slug)
        if clave in vistos:
            continue
        vistos.add(clave)
        obj = resuelto.get(clave)
        sig = f"{t.sigil}{t.slug}"
        if obj is None:
            lineas.append(f"{sig} → (no encontrado)")
        elif t.tipo == "proyecto":
            lineas.append(f"{sig} → proyecto {obj.codigo} «{obj.nombre}» (slug: {obj.slug})")
        elif t.tipo == "cliente":
            lineas.append(f"{sig} → cliente «{obj.razon_social}» (slug: {obj.slug})")
        elif t.tipo == "usuario":
            nombre = getattr(obj, "nombre_completo", "") or obj.email
            lineas.append(f"{sig} → usuario {nombre} (slug: {obj.slug})")

    if not lineas:
        return ""
    return (
        "\n\n[REFERENCIAS RESUELTAS — usa estos datos exactos para responder/actuar; "
        "NO pidas el código si aquí aparece]\n" + "\n".join(lineas)
    )
