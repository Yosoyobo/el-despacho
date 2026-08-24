"""Los servicios que corren en el NUC junto a El Despacho.

Existe para que no haya piezas invisibles (Oscar, 2026-08-24: «todo lo que
estamos integrando debe tener su GUI y sus ajustes en el sidebar»). Un servicio
que corre pero no se ve desde la interfaz es peor que uno que no está: nadie
sabe si funciona, nadie puede apagarlo, y el día que falle nadie sabe por dónde
empezar.

Cada uno se sondea de verdad —no se supone que está en pie porque el compose lo
declare— y se dice **para qué sirve en una frase**, porque quien abra esta
pantalla no tiene por qué saber qué es Gotenberg.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

TIMEOUT = 2.0

#: Cada pieza: cómo se llama para quien mira, qué hace, cómo se comprueba y por
#: dónde se entra. La URL de entrada es None cuando no tiene pantalla propia:
#: sólo le habla El Despacho.
PIEZAS: tuple[dict[str, Any], ...] = (
    {
        "clave": "gotenberg",
        "nombre": "Gotenberg",
        "oficio": "Arma los PDF de cotizaciones y facturas.",
        "detalle": (
            "Antes se los pedíamos a Google. Ahora se hacen aquí: salen al "
            "instante, con los márgenes que se le piden y las páginas numeradas "
            "de verdad."
        ),
        "sonda": lambda: _http(f"{os.environ.get('GOTENBERG_URL', 'http://gotenberg:3000')}/health"),
        "entrada": None,
        "ajustes": "ajustes-documentos",
    },
    {
        "clave": "osrm",
        "nombre": "El mapa (OSRM)",
        "oficio": "Mide las rutas de los mandados por calles reales.",
        "detalle": (
            "Tiene cargado el mapa de México. Sin él, el planeador mide en línea "
            "recta y las horas que ve el runner quedan cortas."
        ),
        "sonda": lambda: _http(
            f"{os.environ.get('OSRM_URL', 'http://osrm:5000')}"
            "/route/v1/driving/-99.1332,19.4326;-99.1332,19.4326?overview=false"),
        "entrada": None,
        "ajustes": "ajustes-rutas",
    },
    {
        "clave": "n8n",
        "nombre": "n8n",
        "oficio": "Hace tareas solas, sin que nadie las pida.",
        "detalle": (
            "La primera: leer el buzón de facturas y archivar los CFDI que llegan. "
            "Se entra sólo desde la red privada porque guarda contraseñas."
        ),
        "sonda": lambda: _http("http://n8n:5678/healthz"),
        "entrada": "http://100.121.244.5:5678",
        "ajustes": None,
    },
    {
        "clave": "paperless",
        "nombre": "Paperless",
        "oficio": "Archiva papeleo y lo deja buscable por su texto.",
        "detalle": (
            "Contratos, remisiones, comprobantes. Se escanea o se reenvía por "
            "correo una vez y se encuentra para siempre, aunque sea una foto."
        ),
        "sonda": lambda: _http("http://paperless:8000/api/", ok_hasta=500),
        "entrada": "http://100.121.244.5:8204",
        "ajustes": None,
    },
)


def _http(url: str, *, ok_hasta: int = 500) -> bool:
    """¿Contesta? Un 4xx cuenta como sí: respondió, aunque sea para negarse."""
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return r.status < ok_hasta
    except Exception as exc:  # noqa: BLE001 — no responder es la respuesta
        # Un 401/403 llega como excepción y significa que el servicio SÍ está:
        # sólo que pide credencial, que es justo lo que se espera de n8n.
        codigo = getattr(exc, "code", None)
        if codigo and 400 <= codigo < ok_hasta:
            return True
        logger.debug("servicios: %s no responde: %s", url, exc)
        return False


def estado() -> list[dict[str, Any]]:
    """Cada pieza con su veredicto. Nunca lanza."""
    salida = []
    for p in PIEZAS:
        try:
            vivo = bool(p["sonda"]())
        except Exception:  # noqa: BLE001
            vivo = False
        salida.append({
            "clave": p["clave"],
            "nombre": p["nombre"],
            "oficio": p["oficio"],
            "detalle": p["detalle"],
            "entrada": p["entrada"],
            "ajustes": p["ajustes"],
            "vivo": vivo,
        })
    return salida


def resumen(lista: list[dict] | None = None) -> dict:
    lista = lista if lista is not None else estado()
    vivos = sum(1 for p in lista if p["vivo"])
    return {"vivos": vivos, "total": len(lista), "todos": vivos == len(lista)}


__all__ = ["PIEZAS", "estado", "resumen"]
