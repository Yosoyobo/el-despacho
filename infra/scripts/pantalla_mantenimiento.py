"""Arma la pantalla de mantenimiento CON ROADMAP de un despliegue (§4 #23).

La corre el job `mudanza` de El Mensajero en el RUNNER, antes de hacer SSH a La
Sede, y el HTML viaja al Droplet en una variable (base64). Se arma aquí y no en La
Sede porque el checkout de La Sede lo pone al día el job `ventana`, que corre EN
PARALELO: cuando la mudanza arranca, ese checkout todavía puede ser el del commit
anterior, y la pantalla anunciaría la versión que se está yendo.

Sólo biblioteca estándar: en el runner no hay Django ni las dependencias del
repo, y no hacen falta.

Lo que dice la pantalla, en español llano y sin nada sensible (todo sale de lo
que el equipo ya ve en Ayuda → Novedades):

- qué versión entra (`lib/version.py`),
- qué trae: el título del primer bloque `## Novedades — … (fecha)` de
  `docs/DOC_05_MANUAL_USUARIO.md`,
- para qué sirve: las frases en negritas con que abren los párrafos de ese bloque,
- qué falta: los pasos del deploy con una barra que avanza por tiempo esperado.

**La variante del portal de clientes va SIN el video** (decisión de Oscar,
2026-09-29: el video es para el equipo, no para los clientes). No es otra
plantilla: es la MISMA con el bloque entre los comentarios `<!-- video -->` y
`<!-- /video -->` quitado (`sin_video`), así las dos no pueden divergir. El
Portero sirve la variante en `recepcion.` (ver `(lc_failover)` del Caddyfile).

Uso:
  python3 infra/scripts/pantalla_mantenimiento.py --commit <sha> > en-curso.html
  python3 infra/scripts/pantalla_mantenimiento.py --commit <sha> --sin-video > en-curso-portal.html
  # la corta del portal, que va commiteada (un candado exige que esté al día):
  python3 infra/scripts/pantalla_mantenimiento.py --corta --sin-video > infra/mantenimiento/index-portal.html
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PLANTILLA = RAIZ / "infra" / "mantenimiento" / "en-curso.plantilla.html"
CORTA = RAIZ / "infra" / "mantenimiento" / "index.html"
VIDEO_ABRE = "  <!-- video -->\n"
VIDEO_CIERRA = "  <!-- /video -->\n"
VERSION_PY = RAIZ / "lib" / "version.py"
DOC_05 = RAIZ / "docs" / "DOC_05_MANUAL_USUARIO.md"

MAX_PUNTOS = 4
MAX_LARGO = 180
_TITULO = re.compile(r"^## Novedades\s*[—–-]\s*(.+?)\s*(?:\(([^()]*)\))?\s*$")


def version(texto_version_py: str) -> str:
    """`VERSION = "2026.09.04"` → `2026.09.04` (sin importar el módulo)."""
    m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', texto_version_py, re.M)
    if not m:
        raise ValueError("lib/version.py no declara VERSION")
    return m.group(1)


def _llano(texto: str) -> str:
    """Quita el marcado de Markdown que no se lee bien fuera del manual."""
    texto = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", texto)  # [enlace](url) → enlace
    texto = texto.replace("**", "").replace("`", "")
    texto = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) > MAX_LARGO:
        texto = texto[: MAX_LARGO - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return texto


def novedad_reciente(texto_doc05: str) -> tuple[str, list[str]]:
    """El título y los puntos del PRIMER bloque de Novedades del manual.

    Los puntos son las frases en negritas con que abren sus párrafos (así están
    escritas las Novedades: «**Lo que cambió.** El detalle…»). Si un bloque no
    trae ninguna, cae a la primera oración de cada párrafo.
    """
    lineas = texto_doc05.splitlines()
    encontrado = next(
        ((n, m) for n, linea in enumerate(lineas) if (m := _TITULO.match(linea))), None
    )
    if encontrado is None:
        return "", []
    i, m = encontrado
    titulo = _llano(m.group(1))

    cuerpo: list[str] = []
    for linea in lineas[i + 1 :]:
        if linea.startswith("## "):
            break
        cuerpo.append(linea)
    parrafos = [
        re.sub(r"\s+", " ", p).strip()
        for p in re.split(r"\n\s*\n", "\n".join(cuerpo))
        if p.strip() and not p.lstrip().startswith(("#", ">", "|", "```"))
    ]
    puntos = []
    for p in parrafos:
        p = re.sub(r"^[-*]\s+", "", p)  # un párrafo que es viñeta
        negrita = re.match(r"\*\*(.+?)\*\*", p)
        puntos.append(negrita.group(1) if negrita else re.split(r"(?<=[.!?])\s", p, maxsplit=1)[0])
    puntos = [_llano(p).rstrip(":") for p in puntos]
    return titulo, [p for p in puntos if p][:MAX_PUNTOS]


def sin_video(pagina: str) -> str:
    """La misma pantalla sin el video: quita el bloque entre sus comentarios.

    Si la página perdió las marcas, truena en vez de devolverla con video: la
    variante del portal nunca debe llevarlo."""
    if pagina.count(VIDEO_ABRE) != 1 or pagina.count(VIDEO_CIERRA) != 1:
        raise ValueError("La pantalla perdió las marcas <!-- video --> / <!-- /video -->")
    ini = pagina.index(VIDEO_ABRE)
    fin = pagina.index(VIDEO_CIERRA) + len(VIDEO_CIERRA)
    if fin <= ini:
        raise ValueError("Las marcas del video están al revés")
    return pagina[:ini] + pagina[fin:]


def armar(*, version: str, titulo: str, puntos: list[str], commit: str, inicio: int,
          video: bool = True) -> str:
    """Llena la plantilla. Todo lo que entra se escapa: sale de un Markdown."""
    titulo = titulo or "Mejoras al sistema"
    lis = "".join(f"<li>{html.escape(p)}</li>" for p in puntos) or (
        "<li>Mejoras y arreglos para el trabajo de todos los días.</li>"
    )
    commit_corto = re.sub(r"[^0-9a-f]", "", commit.lower())[:8] or "sin-commit"
    valores = {
        "__MARCA__": f"en-curso-{commit_corto}-{int(inicio)}",
        "__INICIO__": str(int(inicio)),
        "__VERSION__": html.escape(version),
        "__TITULO__": html.escape(titulo),
        "__PUNTOS__": lis,
    }
    pagina = PLANTILLA.read_text(encoding="utf-8")
    if not video:
        pagina = sin_video(pagina)
    for marcador in valores:
        if marcador not in pagina:
            raise ValueError(f"La plantilla perdió el marcador {marcador}")
    # Una sola pasada: un título que dijera «__PUNTOS__» no se vuelve a sustituir.
    return re.sub("|".join(valores), lambda m: valores[m.group(0)], pagina)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--commit", default="", help="SHA que se despliega")
    p.add_argument("--inicio", type=int, default=None, help="epoch del arranque (default: ahora)")
    p.add_argument("--sin-video", action="store_true",
                   help="la variante del portal de clientes (recepcion.)")
    p.add_argument("--corta", action="store_true",
                   help="escribe la pantalla corta (index.html) en vez del roadmap")
    args = p.parse_args(argv)
    if args.corta:
        corta = CORTA.read_text(encoding="utf-8")
        sys.stdout.write(sin_video(corta) if args.sin_video else corta)
        return 0
    titulo, puntos = novedad_reciente(DOC_05.read_text(encoding="utf-8"))
    sys.stdout.write(
        armar(
            version=version(VERSION_PY.read_text(encoding="utf-8")),
            titulo=titulo,
            puntos=puntos,
            commit=args.commit,
            inicio=args.inicio if args.inicio is not None else int(time.time()),
            video=not args.sin_video,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
