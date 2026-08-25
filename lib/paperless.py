"""Hablarle a Paperless desde El Despacho — el archivo del papeleo, buscable.

Paperless guarda el papeleo que hoy no tiene lugar en el sistema: contratos,
remisiones firmadas, comprobantes de proveedor sin CFDI, cotizaciones que
manda alguien más. Se escanea o se reenvía una vez, su OCR lo lee (en español,
`PAPERLESS_OCR_LANGUAGE=spa`) y desde entonces se encuentra por lo que dice
adentro, no por cómo se llamó el archivo.

**Los CFDI no pasan por aquí, a propósito.** Ya tienen su camino
(`lib/cfdi.py` + `apps/facturacion/ingesta_cfdi.py`), que los liga a su
factura y les saca el UUID. Meterlos también en Paperless los duplicaría y
dejaría dos versiones de la verdad sobre el mismo comprobante.

**Dos direcciones, y no son la misma.** El contenedor le habla por la red de
Docker (`http://paperless:8000`); el navegador de quien lo mira necesita la
del tailnet (`http://100.121.244.5:8204`). Confundirlas da el bug obvio: todo
funciona del lado del servidor y el enlace no abre. La primera es `BASE_URL`,
la segunda vive en la configuración (`ConfiguracionPapeleo.url_publica`).

**La llave.** La API pide `Authorization: Token …`. El token se genera dentro
de Paperless, pero la pantalla de Gerencia también sabe canjear usuario y
contraseña por uno (`canjear_token`) para no mandar a nadie a buscarlo a otra
app. Se guarda en La Bóveda (§4 #3); la contraseña no se guarda nunca.

Sin llave todo esto se apaga solo: `esta_configurado()` da False, las
capacidades desaparecen del catálogo del Chalán y las pantallas lo dicen, en
vez de fallar cuando alguien las use.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

#: Cómo lo alcanza el contenedor (red de Docker). NO sirve para un enlace.
BASE_URL = os.environ.get("PAPERLESS_URL", "http://paperless:8000").rstrip("/")

SLOT_LLAVE = "paperless_token"
ENV_LLAVE = "PAPERLESS_TOKEN"

TIMEOUT = 8.0
#: Subir es otra cosa: el archivo viaja y Paperless lo encola para su OCR.
TIMEOUT_SUBIR = 30.0

#: Tope de lo que se entrega de una vez, al modelo o a una pantalla. Una lista
#: larga de resultados no ayuda a nadie y gasta contexto.
TOPE = 20

#: El texto del OCR de un contrato son miles de caracteres. Se recorta aquí,
#: no en quien llama, para que ningún consumidor lo reciba entero por descuido.
TOPE_TEXTO = 1500


def llave() -> str:
    """El token, de La Bóveda o del entorno. Vacío = no configurado."""
    try:
        from ajustes.models.credencial import Credencial

        v = (Credencial.obtener(SLOT_LLAVE) or "").strip()
        if v:
            return v
    except Exception:  # noqa: BLE001 — sin base, queda la del entorno
        pass
    return (os.environ.get(ENV_LLAVE) or "").strip()


def esta_configurado() -> bool:
    return bool(llave())


def _pedir(ruta: str, *, metodo: str = "GET", cuerpo: dict | None = None) -> Any:
    """Llama a la API. Devuelve el JSON, o None si algo salió mal.

    Nunca lanza: quien llama es una capacidad del Chalán o una pantalla, y una
    traza no le sirve ni al modelo ni a quien está mirando.
    """
    k = llave()
    if not k:
        return None
    try:
        import urllib.request

        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(
            f"{BASE_URL}{ruta}", data=datos, method=metodo,
            headers={"Authorization": f"Token {k}",
                     "Content-Type": "application/json",
                     "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            crudo = r.read()
            return json.loads(crudo) if crudo else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("paperless: %s %s falló: %s", metodo, ruta, exc)
        return None


def disponible() -> bool:
    """¿Hay llave Y contesta la API?"""
    return _pedir("/api/documents/?page_size=1") is not None


# ── Leer ───────────────────────────────────────────────────────────────────


def _resumir(d: dict) -> dict:
    """Un documento, en lo que sirve para reconocerlo sin abrirlo."""
    return {
        "id": int(d.get("id") or 0),
        # Paperless titula con el nombre del archivo cuando nadie lo tituló.
        "titulo": (d.get("title") or "(sin título)")[:160],
        "creado": (d.get("created") or d.get("added") or "")[:10],
        "etiquetas": list(d.get("tags") or []),
        "paginas": d.get("page_count") or None,
    }


def buscar(texto: str, limite: int = 10) -> list[dict] | None:
    """Busca por el TEXTO de adentro (el que sacó el OCR), no por el nombre.

    Es la diferencia que justifica el servicio entero: «la remisión donde firmó
    Optimist» se encuentra aunque el archivo se llame `scan_0042.pdf`.
    """
    texto = (texto or "").strip()
    if not texto:
        return []
    from urllib.parse import quote

    try:
        limite = max(1, min(int(limite), TOPE))
    except (TypeError, ValueError):
        limite = 10
    datos = _pedir(
        f"/api/documents/?query={quote(texto)}&page_size={limite}&ordering=-created"
    )
    if datos is None:
        return None
    return [_resumir(d) for d in (datos.get("results") or [])]


def listar(limite: int = TOPE) -> list[dict] | None:
    """Lo último que entró, sin tener que buscar nada.

    Existe porque una pantalla de archivo que sólo contesta si le escribes algo
    no deja **ver** lo que hay: obliga a adivinar una palabra para descubrir que
    el documento existe. Los más recientes primero, que es lo que uno busca.
    """
    try:
        limite = max(1, min(int(limite), TOPE))
    except (TypeError, ValueError):
        limite = TOPE
    datos = _pedir(f"/api/documents/?ordering=-created&page_size={limite}")
    if datos is None:
        return None
    return [_resumir(d) for d in (datos.get("results") or [])]


def cuantos() -> int | None:
    """Cuántos documentos hay archivados en total. None = no contestó."""
    datos = _pedir("/api/documents/?page_size=1")
    return None if datos is None else datos.get("count")


#: Las tres caras de un documento. `preview` y `download` son el archivo (un PDF
#: casi siempre); `thumb` es la imagen chica para las tarjetas.
CARAS = ("preview", "thumb", "download")


def archivo(doc_id: int | str, cara: str = "preview") -> tuple[bytes, str] | None:
    """Los BYTES de un documento, para servirlos desde El Despacho.

    Se pasa por aquí en vez de mandar al usuario a Paperless por dos razones:
    su dirección sólo existe dentro del tailnet (desde el celular en la calle no
    abre) y tiene su propia sesión. Con este proxy el documento se ve dentro del
    sistema, con el permiso que ya se comprobó.

    Devuelve `(contenido, tipo)` o None. Nunca lanza.
    """
    if cara not in CARAS:
        return None
    k = llave()
    if not k:
        return None
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{BASE_URL}/api/documents/{int(doc_id)}/{cara}/",
            headers={"Authorization": f"Token {k}"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read(), (r.headers.get("Content-Type") or "application/octet-stream")
    except (TypeError, ValueError):
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("paperless: no se pudo traer %s de %s: %s", cara, doc_id, exc)
        return None


def detalle(doc_id: int | str) -> dict | None:
    """Un documento con un pedazo de su texto. None si no existe o no contesta."""
    d = _pedir(f"/api/documents/{doc_id}/")
    if not d or not d.get("id"):
        return None
    salida = _resumir(d)
    contenido = (d.get("content") or "").strip()
    salida["texto"] = contenido[:TOPE_TEXTO]
    salida["texto_recortado"] = len(contenido) > TOPE_TEXTO
    return salida


def etiquetas() -> list[dict] | None:
    datos = _pedir(f"/api/tags/?page_size={TOPE}")
    if datos is None:
        return None
    return [{"id": t.get("id"), "nombre": t.get("name")}
            for t in (datos.get("results") or [])]


def id_de_etiqueta(nombre: str) -> int | None:
    """El id de una etiqueta por su nombre, creándola si no existe.

    Se crea sola porque la alternativa es que subir un documento falle por una
    etiqueta que nadie dio de alta — y entonces el papeleo se queda fuera del
    archivo por un detalle de catálogo.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        return None
    from urllib.parse import quote

    datos = _pedir(f"/api/tags/?name__iexact={quote(nombre)}")
    if datos is None:
        return None
    for t in datos.get("results") or []:
        return t.get("id")
    creada = _pedir("/api/tags/", metodo="POST", cuerpo={"name": nombre[:128]})
    return (creada or {}).get("id")


# ── Escribir ───────────────────────────────────────────────────────────────


def subir(contenido: bytes, nombre: str, *, titulo: str = "",
          etiquetas_ids: list[int] | None = None) -> str | None:
    """Deja un archivo en Paperless. Devuelve el id de la TAREA, no del documento.

    Paperless responde el uuid de la tarea de consumo: cuando la llamada
    regresa el documento **todavía no existe**, porque su OCR corre después y
    tarda (aquí con un solo trabajador, para no pelearle CPU al negocio). Quien
    suba tiene que decirlo así — prometer «ya quedó archivado» sería mentir por
    unos minutos.
    """
    k = llave()
    if not k or not contenido:
        return None
    try:
        import urllib.request

        campos: dict[str, str] = {}
        if (titulo or "").strip():
            campos["title"] = titulo.strip()[:160]
        cuerpo, tipo = _multipart(
            campos,
            [("document", nombre or "documento.pdf", contenido,
              "application/octet-stream")],
            [("tags", i) for i in (etiquetas_ids or [])],
        )
        req = urllib.request.Request(
            f"{BASE_URL}/api/documents/post_document/", data=cuerpo, method="POST",
            headers={"Authorization": f"Token {k}", "Content-Type": tipo},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SUBIR) as r:
            crudo = (r.read() or b"").decode(errors="replace").strip()
        return crudo.strip('"') or "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("paperless: no se pudo subir %s: %s", nombre, exc)
        return None


def canjear_token(usuario: str, contrasena: str) -> str | None:
    """Cambia usuario y contraseña por un token de API. La contraseña no se guarda.

    Existe para que nadie tenga que ir a otra app a buscar su token: se teclea
    una vez en la pantalla de Gerencia y lo que queda guardado es el token.
    """
    if not (usuario or "").strip() or not contrasena:
        return None
    try:
        import urllib.request

        datos = json.dumps({"username": usuario.strip(),
                            "password": contrasena}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/token/", data=datos, method="POST",
            headers={"Content-Type": "application/json",
                     "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return (json.loads(r.read()) or {}).get("token") or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("paperless: no se pudo canjear el token: %s", exc)
        return None


# ── Enlaces para el navegador ──────────────────────────────────────────────


def url_publica() -> str:
    """La dirección con la que un navegador SÍ alcanza Paperless.

    Sale de la configuración; si no está, del entorno. Nunca de `BASE_URL`:
    `http://paperless:8000` sólo existe dentro de la red de Docker y un enlace
    a esa dirección no abre en ninguna máquina.
    """
    try:
        from ajustes.models import ConfiguracionPapeleo

        v = (ConfiguracionPapeleo.obtener().url_publica or "").strip()
        if v:
            return v.rstrip("/")
    except Exception:  # noqa: BLE001 — sin base o sin migrar, queda el entorno
        pass
    return (os.environ.get("PAPERLESS_PUBLIC_URL") or "").rstrip("/")


def url_web(doc_id: int | str) -> str:
    """Para abrir el documento en Paperless. Vacío si no se sabe la dirección."""
    base = url_publica()
    return f"{base}/documents/{doc_id}/details" if base else ""


def _multipart(campos: dict[str, str], archivos: list, repetidos: list | None = None):
    """Arma el cuerpo multipart a mano.

    A mano y no con `requests` por lo mismo que en `lib/gotenberg.py`: este
    módulo vive en `lib/`, que no trae dependencias propias, y son veinte
    líneas contra una dependencia más en las tres imágenes. Si aparece un
    tercer consumidor, se extrae a un `lib/multipart.py` y ya.

    `repetidos` existe porque Paperless espera las etiquetas como el mismo
    campo varias veces (`tags=1`, `tags=2`), no como una lista.
    """
    import secrets

    frontera = "----ElDespacho" + secrets.token_hex(16)
    sep = f"--{frontera}\r\n".encode()
    partes: list[bytes] = []

    for nombre, valor in campos.items():
        partes.append(sep)
        partes.append(
            f'Content-Disposition: form-data; name="{nombre}"\r\n\r\n'.encode())
        partes.append(f"{valor}\r\n".encode())

    for nombre, valor in repetidos or []:
        partes.append(sep)
        partes.append(
            f'Content-Disposition: form-data; name="{nombre}"\r\n\r\n'.encode())
        partes.append(f"{valor}\r\n".encode())

    for nombre, archivo, contenido, tipo in archivos:
        partes.append(sep)
        partes.append(
            f'Content-Disposition: form-data; name="{nombre}"; '
            f'filename="{archivo}"\r\n'.encode()
        )
        partes.append(f"Content-Type: {tipo}\r\n\r\n".encode())
        partes.append(contenido)
        partes.append(b"\r\n")

    partes.append(f"--{frontera}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={frontera}"


__all__ = [
    "CARAS",
    "archivo",
    "cuantos",
    "listar",
    "BASE_URL",
    "ENV_LLAVE",
    "SLOT_LLAVE",
    "TOPE",
    "TOPE_TEXTO",
    "buscar",
    "canjear_token",
    "detalle",
    "disponible",
    "esta_configurado",
    "etiquetas",
    "id_de_etiqueta",
    "llave",
    "subir",
    "url_publica",
    "url_web",
]
