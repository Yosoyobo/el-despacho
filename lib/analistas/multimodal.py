"""Formato de imágenes para Los Analistas con visión (Fase C, S-Chalán-Scope-OCR).

Una imagen se pasa a `analizar(..., imagenes=[...])` como un dict canónico:

    {"base64": "<datos base64 sin prefijo data:>", "media_type": "image/jpeg"}

Cada adapter con visión la traduce al formato de su API vía los builders de
aquí. Adapters sin visión la ignoran (el Reemplazo los salta cuando se pide
`requiere={Capability.VISION}`).
"""

from __future__ import annotations

# Tamaño/cantidad razonable para OCR de recibos. El caller ya valida MIME y
# peso (lib.adjuntos); esto es un tope defensivo del lado del adapter.
MAX_IMAGENES = 8


def normalizar_imagenes(imagenes) -> list[dict]:
    """Valida y normaliza la lista. Acepta `base64`/`data` y
    `media_type`/`mime_type`. Descarta items sin datos."""
    if not imagenes:
        return []
    out: list[dict] = []
    for img in imagenes:
        if not isinstance(img, dict):
            continue
        b64 = img.get("base64") or img.get("data")
        media = (img.get("media_type") or img.get("mime_type") or "image/jpeg").lower()
        if b64:
            out.append({"base64": b64, "media_type": media})
        if len(out) >= MAX_IMAGENES:
            break
    return out


def contenido_anthropic(prompt: str, imagenes: list[dict]) -> list[dict]:
    """Bloques `content` de la Messages API: imágenes primero, texto al final."""
    bloques = [
        {"type": "image",
         "source": {"type": "base64", "media_type": i["media_type"], "data": i["base64"]}}
        for i in imagenes
    ]
    bloques.append({"type": "text", "text": prompt})
    return bloques


def partes_gemini(prompt: str, imagenes: list[dict]) -> list[dict]:
    """`parts` de generateContent: inline_data por imagen + texto."""
    partes = [
        {"inline_data": {"mime_type": i["media_type"], "data": i["base64"]}}
        for i in imagenes
    ]
    partes.append({"text": prompt})
    return partes


def contenido_openai(prompt: str, imagenes: list[dict]) -> list[dict]:
    """`content` array estilo OpenAI/MiMo (chat/completions) con data-URLs."""
    contenido = [
        {"type": "image_url",
         "image_url": {"url": f"data:{i['media_type']};base64,{i['base64']}"}}
        for i in imagenes
    ]
    contenido.append({"type": "text", "text": prompt})
    return contenido


__all__ = [
    "MAX_IMAGENES",
    "normalizar_imagenes",
    "contenido_anthropic",
    "partes_gemini",
    "contenido_openai",
]
