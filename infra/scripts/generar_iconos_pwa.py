"""Genera iconos PWA para El Taller desde un placeholder.

Salida en `el-taller/static/icons/`:
  - icon-192.png       (purpose: any)
  - icon-512.png       (purpose: any)
  - icon-mask-192.png  (purpose: maskable — con padding seguro)
  - icon-mask-512.png  (purpose: maskable)

Si más adelante hay un SVG de marca real, se puede reemplazar la lógica
de dibujo por una conversión SVG→PNG (cairosvg) sin tocar el resto.

Idempotente — siempre sobreescribe.
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "el-taller" / "static" / "icons"

# Colores Tailwind (amber-700, amber-100)
FONDO = (180, 83, 9)
LETRA = (254, 243, 199)


def _fuente(tam: int):
    candidatos = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/local/share/fonts/DejaVuSans-Bold.ttf",
    ]
    for ruta in candidatos:
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tam)
    return ImageFont.load_default()


def generar_icono(size: int, *, maskable: bool, ruta: Path) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Maskable: la zona segura es el círculo interno (~80% del lienzo).
    # Para "any", llenamos un cuadrado redondeado más grande.
    padding = int(size * 0.10) if maskable else int(size * 0.04)
    radio = int(size * 0.20)
    box = (padding, padding, size - padding, size - padding)
    d.rounded_rectangle(box, radius=radio, fill=FONDO)

    fuente = _fuente(int(size * 0.55))
    texto = "D"
    bbox = d.textbbox((0, 0), texto, font=fuente)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    d.text((x, y), texto, font=fuente, fill=LETRA)

    img.save(ruta, "PNG", optimize=True)
    print(f"  → {ruta.relative_to(RAIZ)} ({size}×{size})")


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    print("Generando iconos PWA de El Taller…")
    generar_icono(192, maskable=False, ruta=DESTINO / "icon-192.png")
    generar_icono(512, maskable=False, ruta=DESTINO / "icon-512.png")
    generar_icono(192, maskable=True, ruta=DESTINO / "icon-mask-192.png")
    generar_icono(512, maskable=True, ruta=DESTINO / "icon-mask-512.png")
    print("Listo.")


if __name__ == "__main__":
    main()
