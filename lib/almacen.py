"""El Almacén — los medios de El Despacho viven en disco, no en Drive.

**Por qué existe** (LC 2026-08-20). Hasta este sprint Drive era la fuente de
verdad Y el origen de cada lectura: El Despacho sólo guardaba el `file_id`, así
que cada vez que alguien veía una foto, un comprobante o un CFDI, el servidor le
pedía el archivo a Google (dos llamadas HTTP), lo redimensionaba con Pillow **en
el hilo del request** y lo dejaba en un Redis de 64 MB que comparte con la cola
del Portavoz, el rate-limiter y las sesiones. Una ficha de catálogo con 30
productos fríos eran 30 descargas y 30 redimensionados en serie, sobre un vCPU
con un worker. Y el PDF dependía de que Google alcanzara a bajar la foto antes de
rendirse.

**Cómo funciona ahora.** El archivo se guarda UNA vez, al subirlo:

    orig/<h:2>/<h:2>/<h>/archivo     los bytes tal cual · NUNCA los sirve Caddy
    orig/<h:2>/<h:2>/<h>/meta.json   mime, nombre, tamaño, ancho, alto, variantes
    pub/ <h:2>/<h:2>/<h>/w400.jpg    derivados que generamos NOSOTROS · esto sí lo sirve Caddy
    pub/ <h:2>/<h:2>/<h>/w1000.jpg

donde `h = sha256(clave)`. Se hashea **la llave** en lugar de usarla cruda por
tres razones: el APFS de HAL no distingue mayúsculas y dos ids de Drive que sólo
difirieran en eso colisionarían; uniforma el reparto en subcarpetas; y la ruta
pública no revela el id de Drive.

**Que Caddy sólo alcance `pub/` es la decisión de seguridad central**: nunca
sirve un archivo subido por un usuario, sólo derivados JPEG/PNG hechos por
nosotros. Eso cierra de golpe el riesgo de que un XML o un SVG se interpreten en
el origen de la aplicación. El nombre que escribió el usuario tampoco toca el
disco: el original siempre se llama `archivo`.

**La llave.** Es la cadena que ya vive en la base (`imagen_file_id`,
`drive_file_id`, `avatar_drive_id`, `pdf_file_id`, `xml_file_id`). Para lo que se
sube de hoy en adelante es el sha256 del contenido —así la misma foto en cinco
productos ocupa un solo archivo— y para lo que se importa de Drive es su id de
siempre, de modo que **la base no cambia y no hay migraciones**.

**Compatibilidad.** `leer()` tiene la misma firma que
`lib.google_drive.drive.descargar()` —`(contenido, mime, nombre)`— y si la llave
todavía no está en disco la baja de Drive y la deja guardada. Por eso el sistema
funciona completo mientras la importación avanza.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

# Los derivados que se generan al ingresar una imagen. `w400` es la miniatura de
# las fichas y las tarjetas (~30 KB); `w1000` es la que va en el documento y en
# su vista previa. Una foto de celular de 4000 px no aporta nada a 150 pt de
# ancho y sí hace lenta la descarga.
VARIANTES: dict[str, int] = {"w400": 400, "w1000": 1000}

# Calidad del JPEG de los derivados. 82 es el punto donde un bordado con texto
# todavía se lee bien; más abajo se ensucian los bordes.
CALIDAD_JPEG = 82

# Prefijo de las rutas públicas (el `root` de El Portero apunta a `pub/`).
PREFIJO_URL = "/medios"

_NOMBRE_ORIGINAL = "archivo"
_NOMBRE_META = "meta.json"

# meta.json es inmutable una vez escrito (el almacén está direccionado por
# contenido: nada muta, sólo se agrega), así que recordarlo en el proceso es
# correcto para siempre. Sólo se recuerda lo que EXISTE — si se guardara el
# "no está" en caché, una llave recién importada seguiría reportándose ausente.
_META_CACHE: dict[str, dict] = {}


class ArchivoNoDisponible(Exception):
    """No se pudo obtener el archivo (no está en el almacén ni en Drive)."""


# ── Rutas ────────────────────────────────────────────────────────────────────

def raiz() -> Path:
    """Carpeta del almacén. `MEDIOS_DIR` en los settings o en el entorno.

    Se resuelve en cada llamada (es un `os.environ`/`getattr`, no cuesta) para
    que las pruebas puedan apuntarla a un directorio temporal y para que mudar
    el almacén a otro disco sea cambiar una variable.
    """
    try:
        from django.conf import settings

        desde_settings = getattr(settings, "MEDIOS_DIR", "")
    except Exception:  # noqa: BLE001 — usable desde scripts sin Django configurado
        desde_settings = ""
    return Path(str(desde_settings or os.environ.get("MEDIOS_DIR") or "/app/medios"))


def _huella(clave: str) -> str:
    """`sha256` de la llave — es el nombre de la carpeta en disco."""
    return hashlib.sha256(str(clave).encode("utf-8")).hexdigest()


def _tramos(huella: str) -> tuple[str, str, str]:
    return huella[:2], huella[2:4], huella


def _dir_orig(clave: str) -> Path:
    a, b, h = _tramos(_huella(clave))
    return raiz() / "orig" / a / b / h


def _dir_pub(clave: str) -> Path:
    a, b, h = _tramos(_huella(clave))
    return raiz() / "pub" / a / b / h


def dir_pub_por_huella(huella: str) -> Path:
    """Carpeta pública a partir de la huella (la vista de respaldo sólo tiene
    eso: la ruta lleva el sha256, no la llave, y el sha256 no se puede invertir).
    Regenerar un derivado no necesita la llave; importar de Drive sí."""
    a, b, h = _tramos(huella)
    return raiz() / "pub" / a / b / h


def dir_orig_por_huella(huella: str) -> Path:
    a, b, h = _tramos(huella)
    return raiz() / "orig" / a / b / h


def clave_de_contenido(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


# ── Lectura de metadatos ─────────────────────────────────────────────────────

def existe(clave: str) -> bool:
    """¿El original de esta llave ya está en el almacén?"""
    if not clave:
        return False
    return (_dir_orig(clave) / _NOMBRE_ORIGINAL).is_file()


def meta(clave: str) -> dict | None:
    """Metadatos guardados junto al original, o `None` si no está. Nunca lanza."""
    if not clave:
        return None
    guardado = _META_CACHE.get(clave)
    if guardado is not None:
        return guardado
    ruta = _dir_orig(clave) / _NOMBRE_META
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — no está, o quedó a medio escribir
        return None
    if not isinstance(datos, dict):
        return None
    _META_CACHE[clave] = datos
    return datos


def olvidar_meta(clave: str = "") -> None:
    """Vacía el recuerdo en proceso (una llave o todo). La usan las pruebas y
    `derivar(forzar=True)`."""
    if clave:
        _META_CACHE.pop(clave, None)
    else:
        _META_CACHE.clear()


# ── Escritura ────────────────────────────────────────────────────────────────

def _escribir_meta(clave: str, datos: dict) -> None:
    destino = _dir_orig(clave) / _NOMBRE_META
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, destino)  # atómico: nadie lee un meta a medias
    _META_CACHE[clave] = datos


def guardar_fileobj(fileobj, *, mime: str = "", nombre: str = "archivo",
                    clave: str = "") -> dict:
    """Guarda un archivo en el almacén y devuelve sus metadatos.

    Se escribe **por trozos** a un temporal mientras se calcula el sha256, y al
    final se mueve con `os.replace` (atómico dentro del mismo sistema de
    archivos, de ahí que el temporal viva en `$MEDIOS_DIR/tmp`). Así una subida
    de 25 MB no se carga entera a memoria en un servidor de 1 GB, y nadie ve un
    archivo a medio escribir.

    Sin `clave` se usa el sha256 del contenido, con lo que la misma foto subida a
    cinco productos ocupa un solo archivo. Con `clave` (la importación de Drive)
    se respeta el id que ya está en la base.
    """
    base = raiz()
    tmp_dir = base / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    total = 0
    fd, tmp_nombre = tempfile.mkstemp(dir=tmp_dir, suffix=".subiendo")
    tmp_ruta = Path(tmp_nombre)
    try:
        with os.fdopen(fd, "wb") as salida:
            for trozo in _trozos(fileobj):
                digest.update(trozo)
                total += len(trozo)
                salida.write(trozo)
        sha = digest.hexdigest()
        clave_final = str(clave) if clave else sha
        destino_dir = _dir_orig(clave_final)
        destino = destino_dir / _NOMBRE_ORIGINAL

        if destino.is_file():
            # Ya estaba (misma foto, o reimportación): se descarta el temporal.
            existente = meta(clave_final) or {}
            return {**existente, "id": clave_final, "duplicado": True}

        destino_dir.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_ruta, destino)
        tmp_ruta = None  # ya se movió
    finally:
        if tmp_ruta is not None:
            with contextlib.suppress(Exception):
                tmp_ruta.unlink()

    datos = {
        "id": clave_final,
        "sha256": sha,
        "mime": (mime or "application/octet-stream"),
        "nombre": (nombre or "archivo"),
        "bytes": total,
        "variantes": {},
    }
    _escribir_meta(clave_final, datos)
    # Los derivados actualizan el meta con `variantes`, `ancho` y `alto`.
    derivar(clave_final)
    return meta(clave_final) or datos


def guardar_bytes(contenido: bytes, *, mime: str = "", nombre: str = "archivo",
                  clave: str = "") -> dict:
    """`guardar_fileobj` para bytes que ya están en memoria (la importación de
    Drive y las pruebas)."""
    import io

    return guardar_fileobj(io.BytesIO(contenido), mime=mime, nombre=nombre, clave=clave)


def _trozos(fileobj, tamano: int = 1024 * 512):
    """Itera el archivo en trozos, sirva `chunks()` (UploadedFile de Django) o
    `read()` (cualquier fileobj)."""
    if hasattr(fileobj, "chunks"):
        with contextlib.suppress(Exception):
            fileobj.seek(0)
        yield from fileobj.chunks(tamano)
        return
    with contextlib.suppress(Exception):
        fileobj.seek(0)
    while True:
        trozo = fileobj.read(tamano)
        if not trozo:
            break
        yield trozo


# ── Derivados ────────────────────────────────────────────────────────────────

def hay_decodificador_heic() -> bool:
    """¿Pillow puede abrir HEIC/HEIF? Sólo con `pillow-heif` instalado.

    Importa el registro de forma suave: el día que la dependencia se agregue a
    `requirements.txt`, el HEIC de un iPhone empieza a funcionar sin tocar código.
    Mientras no esté, `lib.adjuntos.validar` lo rechaza con un mensaje claro —
    que es mejor que aceptarlo y dejar una imagen que el navegador no pinta.
    """
    try:
        import pillow_heif  # type: ignore[import-not-found]

        pillow_heif.register_heif_opener()
        return True
    except Exception:  # noqa: BLE001 — no está instalado, o no se pudo registrar
        return False


def derivar(clave: str, *, forzar: bool = False) -> dict[str, str]:
    """Genera los derivados de una imagen y los anota en su meta.

    Devuelve `{variante: nombre_de_archivo}` (vacío si el archivo no es imagen o
    si Pillow no pudo con él — un PDF, un XML o una imagen corrupta). Ese
    diccionario es la fuente de verdad de `url()`: si está vacío, la imagen se
    sirve por el proxy de Django como siempre, nunca por Caddy.

    Nunca lanza. Al ingresar se aplica `exif_transpose`, que es lo que endereza
    las fotos de iPhone acostadas (antes de este sprint salían de lado).
    """
    datos = meta(clave)
    if datos is None:
        return {}
    if datos.get("variantes") and not forzar:
        return dict(datos["variantes"])
    if not str(datos.get("mime", "")).startswith("image/"):
        return {}

    origen = _dir_orig(clave) / _NOMBRE_ORIGINAL
    if not origen.is_file():
        return {}

    hay_decodificador_heic()  # HEIC sólo si la dependencia está instalada
    try:
        from PIL import Image, ImageOps

        with Image.open(origen) as img:
            img = ImageOps.exif_transpose(img) or img
            alfa = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            )
            ancho, alto = img.size
            destino_dir = _dir_pub(clave)
            destino_dir.mkdir(parents=True, exist_ok=True)
            hechas: dict[str, str] = {}
            for variante, lado in VARIANTES.items():
                copia = img.copy()
                copia.thumbnail((lado, lado), Image.LANCZOS)
                nombre = f"{variante}.png" if alfa else f"{variante}.jpg"
                if _escribir_derivado(copia, destino_dir / nombre, alfa):
                    hechas[variante] = nombre
    except Exception:  # noqa: BLE001 — formato raro, imagen corrupta, bomba
        return {}

    if not hechas:
        return {}
    _escribir_meta(clave, {**datos, "ancho": ancho, "alto": alto, "variantes": hechas})
    return hechas


def _escribir_derivado(img, destino: Path, alfa: bool) -> bool:
    """Escribe un derivado de forma atómica. `True` si quedó."""
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    try:
        if alfa:
            img.convert("RGBA").save(tmp, format="PNG", optimize=True)
        else:
            img.convert("RGB").save(tmp, format="JPEG", quality=CALIDAD_JPEG,
                                    optimize=True, progressive=True)
        os.replace(tmp, destino)
        return True
    except Exception:  # noqa: BLE001
        with contextlib.suppress(Exception):
            tmp.unlink()
        return False


def derivar_por_huella(huella: str, variante: str, extension: str) -> Path | None:
    """Regenera un derivado teniendo sólo la huella de la ruta.

    La usa la vista de respaldo cuando El Portero no encuentra el archivo (un
    `pub/` borrado a mano, un restore sin derivados). No necesita la llave porque
    el original ya está en disco; importar de Drive sí la necesita, y ése es el
    otro camino (el proxy de siempre).
    """
    if variante not in VARIANTES or extension not in ("jpg", "png"):
        return None
    origen = dir_orig_por_huella(huella) / _NOMBRE_ORIGINAL
    if not origen.is_file():
        return None
    hay_decodificador_heic()
    try:
        from PIL import Image, ImageOps

        with Image.open(origen) as img:
            img = ImageOps.exif_transpose(img) or img
            img.thumbnail((VARIANTES[variante], VARIANTES[variante]), Image.LANCZOS)
            destino_dir = dir_pub_por_huella(huella)
            destino_dir.mkdir(parents=True, exist_ok=True)
            destino = destino_dir / f"{variante}.{extension}"
            if _escribir_derivado(img, destino, extension == "png"):
                return destino
    except Exception:  # noqa: BLE001
        return None
    return None


# ── Servido ──────────────────────────────────────────────────────────────────

def ruta_variante(clave: str, variante: str = "w400") -> Path | None:
    """Ruta en disco del derivado, o `None` si esta llave no tiene esa variante."""
    datos = meta(clave)
    if not datos:
        return None
    nombre = (datos.get("variantes") or {}).get(variante)
    if not nombre:
        return None
    return _dir_pub(clave) / nombre


def url(clave: str, variante: str = "w400", *, absoluta: bool = False) -> str:
    """URL con la que se pinta una IMAGEN (los documentos no pasan por aquí: los
    sirve su propia vista con `abrir()`, detrás de su permiso).

    - Si el derivado existe → `/medios/…`, que sirve **El Portero directo del
      disco** con `public, immutable`: sin Python y sin Drive de por medio.
    - Si la llave todavía no está en el almacén, o el archivo no es una imagen
      derivable → el proxy autenticado de siempre, que la materializa al paso.
      Así la siguiente vez ya sale por el camino rápido: se cura solo.

    `absoluta=True` la devuelve con dominio, que es lo que necesita el documento
    de la cotización (Google baja las imágenes desde sus servidores).
    """
    if not clave:
        return ""
    datos = meta(clave)
    nombre = (datos.get("variantes") or {}).get(variante) if datos else ""
    if not nombre:
        # Sin derivado no hay ruta pública. En relativo se cae al proxy, que sí
        # puede servir el original; en absoluto se devuelve vacío a propósito —
        # el único que pide URL absoluta es Google al convertir el documento, y
        # el proxy exige sesión, así que un enlace ahí sólo dejaría el hueco.
        return "" if absoluta else _url_proxy(clave)
    a, b, h = _tramos(_huella(clave))
    ruta = f"{PREFIJO_URL}/{a}/{b}/{h}/{nombre}"
    return f"{base_publica()}{ruta}" if absoluta else ruta


def _url_proxy(clave: str) -> str:
    """El proxy autenticado del catálogo (camino frío / de compatibilidad)."""
    try:
        from django.urls import reverse

        return reverse("catalogo-imagen-producto", args=[clave])
    except Exception:  # noqa: BLE001 — urlconf sin la ruta (La Gerencia)
        return ""


def base_publica() -> str:
    """URL pública de El Taller, sin diagonal final."""
    try:
        from django.conf import settings

        base = getattr(settings, "TALLER_URL", "")
    except Exception:  # noqa: BLE001
        base = ""
    return str(base or os.environ.get("TALLER_URL")
               or "https://taller.learningcenter.mx/").rstrip("/")


def proporcion(clave: str) -> float:
    """Alto ÷ ancho de la imagen (0.0 si no se sabe).

    Sirve para acotar cuánto ocupa la foto en la hoja del documento: va con
    ancho fijo, así que su alto depende de la proporción. Antes se medía
    abriendo la imagen con Pillow y sólo si estaba en caché —cuando no lo
    estaba, el estimador la suponía cuadrada—; ahora sale del `meta.json`, que
    se escribió al ingresarla, así que es **exacta y gratis**.
    """
    datos = meta(clave) or {}
    ancho, alto = datos.get("ancho") or 0, datos.get("alto") or 0
    return (alto / ancho) if ancho and alto else 0.0


# ── Compatibilidad con `drive.descargar` ─────────────────────────────────────

def leer(clave: str) -> tuple[bytes, str, str]:
    """`(contenido, mime, nombre)` del original — misma firma que
    `lib.google_drive.drive.descargar()`.

    Del disco si está; si no, de Drive, y **se queda guardado** (la importación
    perezosa que permite desplegar antes de terminar el respaldo masivo).
    Lanza `ArchivoNoDisponible` si no hay de dónde, igual que hoy lanza Drive —
    los llamadores ya lo envuelven en `try/except` y responden 404.
    """
    if not clave:
        raise ArchivoNoDisponible("Sin llave de archivo.")
    ruta = _dir_orig(clave) / _NOMBRE_ORIGINAL
    if ruta.is_file():
        datos = meta(clave) or {}
        return (ruta.read_bytes(),
                datos.get("mime") or "application/octet-stream",
                datos.get("nombre") or "archivo")
    return _importar_de_drive(clave)


def abrir(clave: str):
    """`(fileobj, mime, nombre)` para `FileResponse` — sirve el documento en
    streaming, sin cargar 25 MB a memoria."""
    if not clave:
        raise ArchivoNoDisponible("Sin llave de archivo.")
    ruta = _dir_orig(clave) / _NOMBRE_ORIGINAL
    if not ruta.is_file():
        _importar_de_drive(clave)  # deja el archivo en disco
    if not ruta.is_file():
        raise ArchivoNoDisponible(f"No se pudo obtener «{clave}».")
    datos = meta(clave) or {}
    return (ruta.open("rb"),
            datos.get("mime") or "application/octet-stream",
            datos.get("nombre") or "archivo")


def _importar_de_drive(clave: str) -> tuple[bytes, str, str]:
    try:
        from lib.google_drive import drive

        contenido, mime, nombre = drive.descargar(clave)
    except Exception as exc:  # noqa: BLE001 — Drive caído, sin permisos, o ya no existe
        raise ArchivoNoDisponible(f"No se pudo obtener «{clave}»: {exc}") from exc
    if not contenido:
        raise ArchivoNoDisponible(f"«{clave}» llegó vacío de Drive.")
    with contextlib.suppress(Exception):
        guardar_bytes(contenido, mime=mime, nombre=nombre, clave=clave)
    return contenido, mime or "application/octet-stream", nombre or "archivo"


# ── Borrado ──────────────────────────────────────────────────────────────────

def borrar(clave: str, *, espejo: bool = False) -> None:
    """Quita el archivo y sus derivados del almacén. Nunca lanza.

    `espejo=True` además lo borra de Drive — sólo donde hoy ya se borra (el
    reemplazo del CFDI). Para las fotos de producto **no se borra nunca**: el
    mismo archivo puede estar congelado en una cotización ya enviada y borrarlo
    dejaría huecos en documentos históricos.
    """
    if not clave:
        return
    for carpeta in (_dir_orig(clave), _dir_pub(clave)):
        with contextlib.suppress(Exception):
            shutil.rmtree(carpeta)
    olvidar_meta(clave)
    if espejo:
        with contextlib.suppress(Exception):
            from lib.google_drive import drive

            drive.borrar(clave)


__all__ = [
    "VARIANTES",
    "ArchivoNoDisponible",
    "abrir",
    "base_publica",
    "borrar",
    "clave_de_contenido",
    "derivar",
    "derivar_por_huella",
    "dir_orig_por_huella",
    "dir_pub_por_huella",
    "existe",
    "guardar_bytes",
    "guardar_fileobj",
    "hay_decodificador_heic",
    "leer",
    "meta",
    "olvidar_meta",
    "proporcion",
    "raiz",
    "ruta_variante",
    "url",
]
