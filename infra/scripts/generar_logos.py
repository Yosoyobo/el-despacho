"""Genera los assets de marca de cada app Django desde un solo master.

Lee el master `static/branding/Logo_LC.png` (raíz del repo) y escribe dos
familias de variantes a `<app>/static/branding/` en los 2 apps que tienen
`STATICFILES_DIRS` configurado (La Gerencia y El Taller). La Recepción no
recibe assets — es stub.

1. `Logo_LC-<size>.png` — logo TRANSPARENTE para uso DENTRO del app
   (sidebar, login, páginas de error). Idéntico en ambas apps.

2. `Icono_LC-<size>.png` — ÍCONO DE APP con el logo horneado sobre un
   cuadro de color de marca POR APP (favicon, apple-touch, íconos PWA).
   Aquí vive la diferenciación de marca pedida por Learning Center:
     - El Taller   → azul brand   #465fff
     - La Gerencia → verde LC     #3E9E4F
   El color del cuadro coincide con el `theme_color`/`background_color`
   del `manifest.json` de cada app, de modo que el ícono instalado, la
   barra de la PWA y el splash de arranque combinan.

Reproducible: corre este script cuando cambies el master o los colores
para regenerar todas las variantes. Idempotente.

Uso:
    python infra/scripts/generar_logos.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / "static" / "branding" / "Logo_LC.png"

# Color de fondo del ícono de app por proyecto (RGB). Mantener sincronizado
# con `theme_color`/`background_color` de cada `manifest.json` y con el
# `<meta name="theme-color">` de cada `base.html`.
COLOR_ICONO = {
    "el-taller": (0x46, 0x5F, 0xFF),    # #465fff — azul brand
    "la-gerencia": (0x3E, 0x9E, 0x4F),  # #3E9E4F — verde Learning Center
}

# El logo ocupa este % del cuadro; el resto es margen del color de marca.
# Deja la zona segura (~80% central) holgada para máscaras circulares de PWA.
ESCALA_LOGO = 0.86

TAMANOS = [32, 64, 128, 192, 256, 512]


def _recolorear_disco(src: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    """Tiñe el disco azul del master con el color de marca de la app.

    El master es una insignia con disco azul royal (#1E4399), sol amarillo,
    texto blanco y rostro negro. Queremos un ícono PLANO del color de la app
    (sol + texto sobre el color sólido), así que reemplazamos sólo los píxeles
    azules y preservamos amarillo/blanco/negro.

    Peso por píxel = qué tan "azul de disco" es (canal B dominando R y G). Los
    bordes anti-aliasing quedan con peso intermedio → la mezcla luce natural.
    El sol, el texto blanco y el rostro negro tienen peso 0 → intactos.
    """
    src = src.convert("RGBA")
    tr, tg, tb = color
    pixeles = []
    for r, g, b, a in src.getdata():
        w = (b - max(r, g)) / 40.0
        w = 0.0 if w < 0 else (1.0 if w > 1 else w)
        pixeles.append(
            (
                round(r * (1 - w) + tr * w),
                round(g * (1 - w) + tg * w),
                round(b * (1 - w) + tb * w),
                a,
            )
        )
    teñido = Image.new("RGBA", src.size)
    teñido.putdata(pixeles)
    return teñido


def _icono(disco: Image.Image, size: int, color: tuple[int, int, int]) -> Image.Image:
    """Disco teñido centrado sobre un cuadro opaco del mismo color de marca.

    Como el disco ya quedó del color de la app, el margen del cuadro se funde
    con él: el resultado es un ícono plano del color de marca con el sol y el
    texto encima, igual al render aprobado por Learning Center.
    """
    fondo = Image.new("RGBA", (size, size), (*color, 255))
    interno = max(1, round(size * ESCALA_LOGO))
    logo = disco.resize((interno, interno), Image.LANCZOS)
    off = (size - interno) // 2
    fondo.alpha_composite(logo, (off, off))
    return fondo.convert("RGB")


def main() -> None:
    if not ORIGEN.exists():
        raise SystemExit(f"No existe {ORIGEN}")

    src = Image.open(ORIGEN)
    if src.mode != "RGBA":
        src = src.convert("RGBA")

    for app, color in COLOR_ICONO.items():
        destino = RAIZ / app / "static" / "branding"
        destino.mkdir(parents=True, exist_ok=True)

        # 1. Logo transparente (uso dentro del app).
        src.save(destino / "Logo_LC.png", optimize=True)
        for size in TAMANOS:
            src.resize((size, size), Image.LANCZOS).save(
                destino / f"Logo_LC-{size}.png", optimize=True
            )

        # 2. Ícono de app con disco teñido del color de marca (favicon / PWA).
        disco = _recolorear_disco(src, color)
        for size in TAMANOS:
            _icono(disco, size, color).save(
                destino / f"Icono_LC-{size}.png", optimize=True
            )

        total = (len(TAMANOS) + 1) + len(TAMANOS)
        print(
            f"✓ {app}: {total} archivos en {destino.relative_to(RAIZ)} "
            f"(ícono #{''.join(f'{c:02x}' for c in color)})"
        )


if __name__ == "__main__":
    main()
