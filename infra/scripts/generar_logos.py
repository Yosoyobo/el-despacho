"""Genera los tamaños del logo Learning Center para cada app Django.

Lee el master `static/branding/Logo_LC.png` (raíz del repo) y escribe las
variantes a `<app>/static/branding/Logo_LC-<size>.png` en los 2 apps que
tienen `STATICFILES_DIRS` configurado (La Gerencia y El Taller). La
Recepción no recibe assets — es stub.

Reproducible: corre este script cuando cambies el master para regenerar
todas las variantes. Idempotente.

Uso:
    python infra/scripts/generar_logos.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / "static" / "branding" / "Logo_LC.png"

APPS_CON_STATIC = ["el-taller", "la-gerencia"]
TAMANOS = [32, 64, 128, 192, 256, 512]


def main() -> None:
    if not ORIGEN.exists():
        raise SystemExit(f"No existe {ORIGEN}")

    src = Image.open(ORIGEN)
    if src.mode != "RGBA":
        src = src.convert("RGBA")

    for app in APPS_CON_STATIC:
        destino = RAIZ / app / "static" / "branding"
        destino.mkdir(parents=True, exist_ok=True)
        # Master sin redimensionar
        src.save(destino / "Logo_LC.png", optimize=True)
        for size in TAMANOS:
            img = src.resize((size, size), Image.LANCZOS)
            img.save(destino / f"Logo_LC-{size}.png", optimize=True)
        print(f"✓ {app}: {len(TAMANOS) + 1} archivos en {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
