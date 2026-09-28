#!/usr/bin/env python3
"""Exporta cada flujo de n8n a un JSON en el repo — su historia y su plan B.

Los flujos viven en la base de n8n, y esa base ya entra al respaldo
(`archivo.sh`). Esto es otra cosa: una copia **legible y versionada** de cada
flujo, para ver en `git log` qué cambió y cuándo, y para poder rehacer uno
aunque la base se pierda.

Se corre desde cualquier máquina del tailnet (HAL, normalmente) después de
armar o cambiar una automatización:

    N8N_API_KEY=… python3 infra/n8n/exportar_flujos.py

y el resultado se commitea. Sólo usa la librería estándar a propósito: tiene
que correr sin Django y sin el entorno virtual del repo.

**Qué NO viaja al JSON**, y por qué:

- nada secreto: n8n guarda las credenciales aparte y cifradas; en un flujo sólo
  aparece el nombre y el id de la credencial que usa cada nodo;
- lo que cambia solo (`updatedAt`, `versionId`, `staticData`, …): si viajara,
  cada exportación ensuciaría el diff aunque nadie hubiera tocado nada.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

URL_DEFAULT = "https://nuc-learning-center.tailedd04d.ts.net"
DESTINO_DEFAULT = Path(__file__).resolve().parent / "flujos"

#: Campos del flujo que se conservan. Todo lo demás se descarta.
CAMPOS_FLUJO = ("id", "name", "description", "active", "nodes", "connections", "settings")

#: Campos de nodo que cambian sin que nadie toque el flujo.
CAMPOS_NODO_VOLATILES = ("notesInFlow",)


def _pedir(url: str, llave: str, ruta: str) -> dict:
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/v1{ruta}",
        headers={"X-N8N-API-KEY": llave, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or b"{}")


def listar(url: str, llave: str) -> list[dict]:
    """Todos los flujos no archivados, recorriendo las páginas."""
    flujos: list[dict] = []
    cursor = ""
    while True:
        ruta = "/workflows?limit=100" + (f"&cursor={cursor}" if cursor else "")
        datos = _pedir(url, llave, ruta)
        flujos.extend(w for w in datos.get("data") or [] if not w.get("isArchived"))
        cursor = datos.get("nextCursor") or ""
        if not cursor:
            return flujos


def normalizar(w: dict) -> dict:
    """El flujo en la forma que se guarda: sólo lo que define qué hace."""
    limpio = {k: w[k] for k in CAMPOS_FLUJO if k in w}
    limpio["nodes"] = [
        {k: v for k, v in n.items() if k not in CAMPOS_NODO_VOLATILES}
        for n in (w.get("nodes") or [])
    ]
    # Las etiquetas se guardan por nombre: su id cambia de una instancia a otra.
    limpio["tags"] = sorted(t.get("name", "") for t in (w.get("tags") or []))
    return limpio


def nombre_archivo(w: dict) -> str:
    """`<nombre-en-minúsculas>-<id>.json`. El id va al final para que renombrar
    un flujo reemplace su archivo en vez de dejar uno viejo al lado."""
    base = unicodedata.normalize("NFKD", w.get("name") or "flujo")
    base = base.encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "flujo"
    return f"{base[:60]}-{w['id']}.json"


def escribir(flujos: list[dict], destino: Path) -> dict:
    """Escribe los flujos y retira los archivos de los que ya no existen."""
    destino.mkdir(parents=True, exist_ok=True)
    vigentes = set()
    for w in flujos:
        nombre = nombre_archivo(w)
        vigentes.add(nombre)
        texto = json.dumps(normalizar(w), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        (destino / nombre).write_text(texto, encoding="utf-8")
    retirados = []
    for viejo in destino.glob("*.json"):
        if viejo.name not in vigentes:
            viejo.unlink()
            retirados.append(viejo.name)
    return {"escritos": sorted(vigentes), "retirados": sorted(retirados)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default=os.environ.get("N8N_URL_PUBLICA", URL_DEFAULT))
    ap.add_argument("--destino", type=Path, default=DESTINO_DEFAULT)
    args = ap.parse_args(argv)

    llave = (os.environ.get("N8N_API_KEY") or "").strip()
    if not llave:
        print("Falta N8N_API_KEY (la llave de la API de n8n).", file=sys.stderr)
        return 2
    try:
        detalles = [_pedir(args.url, llave, f"/workflows/{w['id']}") for w in listar(args.url, llave)]
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"n8n no contestó en {args.url}: {exc}", file=sys.stderr)
        return 1
    r = escribir(detalles, args.destino)
    print(f"{len(r['escritos'])} flujo(s) en {args.destino}")
    for n in r["retirados"]:
        print(f"  retirado: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
