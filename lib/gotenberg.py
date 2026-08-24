"""Gotenberg — convierte HTML a PDF con Chromium, aquí en el NUC.

Reemplaza el camino que pasaba por Google Docs (§8 hasta 2026-08-24). No es
una librería local de las prohibidas: es un servicio aparte al que se le habla
por HTTP, igual que se le hablaba a Google — sólo que corre en la misma
máquina, sin OAuth que caducar ni cuota que agotar.

**Qué arregla, en concreto.** La conversión de Google tiene caprichos que
costaron varias rondas de trabajo y quedaron documentados como deuda:

- el pie decía «1/1» aunque el documento tuviera tres hojas, porque la API de
  Documentos **no tiene** petición para insertar un número de página que
  avance. Chromium sí: `<span class="pageNumber">`;
- el margen superior se le pedía y **lo ignoraba** («desistamos por ahora»,
  2026-08-18). Aquí es un parámetro y se respeta;
- `page-break-inside: avoid` se ignoraba, así que hubo que envolver cada
  bloque en una tabla de una celda y encima blindar sus filas con
  `preventOverflow` por la API. Chromium respeta el CSS;
- y la conversión tardaba segundos, lo que además ocupaba un hilo de gunicorn
  todo ese rato.

**Fallback gracioso, como todo lo de afuera en este repo.** Si el servicio no
responde, nada aquí lanza: `disponible()` devuelve False y quien llama sigue
por el camino de Google. Un PDF que no sale no puede tumbar el flujo de
«enviar cotización».
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

#: Dónde vive el servicio. En el NUC es el nombre del contenedor en la red de
#: Docker; en local se puede apuntar a otro lado sin tocar código.
BASE_URL = os.environ.get("GOTENBERG_URL", "http://gotenberg:3000")

TIMEOUT_SALUD = 2.0
TIMEOUT_CONVERSION = 60.0

#: Cuánto dura el veredicto de `disponible()`. Sin esto se sondearía el
#: servicio en cada PDF; con esto, una vez por minuto.
TTL_SALUD = 60.0

#: Carta, en pulgadas. Es el tamaño con el que trabaja el despacho.
ANCHO_CARTA_IN = 8.5
ALTO_CARTA_IN = 11.0

_PT_POR_PULGADA = 72.0

_salud: tuple[float, bool] | None = None


def _pt_a_pulgadas(pt: float | int | None, default: float) -> float:
    """Los `PAGINA_DOCUMENTO` del repo hablan en puntos; Chromium en pulgadas."""
    if pt is None:
        return default
    try:
        return round(float(pt) / _PT_POR_PULGADA, 4)
    except (TypeError, ValueError):
        return default


def disponible(*, forzar: bool = False) -> bool:
    """¿Contesta el servicio? Cacheado `TTL_SALUD` segundos.

    `forzar=True` salta el caché — útil en pruebas y en el arranque.
    """
    global _salud
    ahora = time.monotonic()
    if not forzar and _salud is not None:
        visto_en, veredicto = _salud
        if ahora - visto_en < TTL_SALUD:
            return veredicto
    veredicto = _sondear()
    _salud = (ahora, veredicto)
    return veredicto


def _sondear() -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=TIMEOUT_SALUD) as r:
            return r.status == 200
    except Exception as exc:  # noqa: BLE001 — no responder es la respuesta
        logger.info("gotenberg no disponible (%s): %s", BASE_URL, exc)
        return False


def _pie_html(texto: str) -> str:
    """Pie con numeración REAL de páginas.

    Chromium sustituye `pageNumber` y `totalPages` al imprimir. Es justo lo
    que la API de Documentos no podía hacer, y el motivo de que el pie de las
    cotizaciones dijera «1/1» en documentos de varias hojas.

    El `font-size` va en el estilo del propio pie porque Chromium no hereda
    los estilos del documento en el encabezado ni en el pie.
    """
    izq = (texto or "").strip()
    return (
        "<html><head><style>"
        "body{margin:0;font-family:Arial,Helvetica,sans-serif;font-size:8pt;color:#666}"
        ".fila{display:flex;justify-content:space-between;width:100%;padding:0 .55in}"
        "</style></head><body><div class='fila'>"
        f"<span>{izq}</span>"
        "<span><span class='pageNumber'></span>/<span class='totalPages'></span></span>"
        "</div></body></html>"
    )


def html_a_pdf(html: str, *, pagina: dict | None = None) -> bytes:
    """Convierte `html` y devuelve los bytes del PDF. **Lanza** si falla.

    A diferencia del resto del módulo, esta función sí lanza: quien la llama
    (`lib.documentos`) ya tiene el `try` que decide si cae al camino de Google.
    Tragarse el error aquí dejaría un PDF vacío pasando por bueno.

    `pagina` acepta el mismo diccionario que se le pasaba a Google
    (`PAGINA_DOCUMENTO`): márgenes en puntos y un texto de pie.
    """
    pagina = pagina or {}
    partes: list[tuple[str, str, bytes, str]] = [
        ("files", "index.html", html.encode("utf-8"), "text/html"),
    ]

    campos = {
        "paperWidth": str(ANCHO_CARTA_IN),
        "paperHeight": str(ALTO_CARTA_IN),
        "marginTop": str(_pt_a_pulgadas(pagina.get("margen_superior_pt"), 1.0)),
        "marginBottom": str(_pt_a_pulgadas(pagina.get("margen_inferior_pt"), 1.0)),
        "marginLeft": str(_pt_a_pulgadas(pagina.get("margen_izquierdo_pt"), 1.0)),
        "marginRight": str(_pt_a_pulgadas(pagina.get("margen_derecho_pt"), 1.0)),
        # Sin esto, los fondos y los bordes de las tablas no se imprimen: el
        # documento saldría sin el sombreado de los encabezados.
        "printBackground": "true",
        # Que el CSS no dependa de si Chromium se cree pantalla o papel.
        "emulatedMediaType": "print",
    }

    pie = (pagina.get("pie_texto") or "").strip()
    if pie or pagina.get("numerar_paginas", True):
        partes.append(("files", "footer.html", _pie_html(pie).encode("utf-8"), "text/html"))

    cuerpo, content_type = _multipart(campos, partes)

    import urllib.request

    req = urllib.request.Request(
        f"{BASE_URL}/forms/chromium/convert/html",
        data=cuerpo,
        headers={"Content-Type": content_type},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_CONVERSION) as r:
        if r.status != 200:
            raise RuntimeError(f"gotenberg respondió {r.status}")
        return r.read()


def _multipart(campos: dict[str, str], archivos: list[tuple[str, str, bytes, str]]):
    """Arma el cuerpo multipart a mano.

    Se hace a mano en vez de traer `requests` porque este módulo vive en
    `lib/`, que es código sin Django y sin dependencias propias, y porque son
    veinte líneas contra una dependencia más en las tres imágenes.
    """
    import secrets

    frontera = "----ElDespacho" + secrets.token_hex(16)
    sep = f"--{frontera}\r\n".encode()
    partes: list[bytes] = []

    for nombre, valor in campos.items():
        partes.append(sep)
        partes.append(f'Content-Disposition: form-data; name="{nombre}"\r\n\r\n'.encode())
        partes.append(f"{valor}\r\n".encode())

    for nombre, archivo, contenido, tipo in archivos:
        partes.append(sep)
        partes.append(
            f'Content-Disposition: form-data; name="{nombre}"; filename="{archivo}"\r\n'.encode()
        )
        partes.append(f"Content-Type: {tipo}\r\n\r\n".encode())
        partes.append(contenido)
        partes.append(b"\r\n")

    partes.append(f"--{frontera}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={frontera}"


def olvidar_salud() -> None:
    """Tira el caché del sondeo. Para pruebas y para después de un despliegue."""
    global _salud
    _salud = None


__all__ = [
    "BASE_URL",
    "disponible",
    "html_a_pdf",
    "olvidar_salud",
]
