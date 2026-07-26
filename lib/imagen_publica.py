"""URLs públicas FIRMADAS y TEMPORALES para imágenes dentro de documentos.

**Por qué existe.** Los PDF de El Despacho se generan vía Google Docs (regla
§8: nada de librerías de PDF locales): armamos HTML → Google lo convierte en
Doc → exportamos PDF. Cuando ese HTML lleva un `<img src="...">`, **Google
baja la imagen desde sus propios servidores, de forma anónima** — sin la
sesión del usuario y sin nuestra credencial de Drive. Por eso el proxy
autenticado de siempre (`/perfil/avatar-img/…`, `/tesoreria/…/comprobante`)
NO sirve aquí: Google llega, ve el login y el PDF sale con un hueco.

**La solución.** Un enlace público pero firmado y con caducidad: el token
lleva el `file_id` de Drive + un timestamp, firmado con `DJANGO_SECRET_KEY`.
Google lo baja sin contraseña durante los segundos que dura la conversión y
el enlace muere solo. Drive nunca se comparte y no queda nada expuesto
después.

Defensa en profundidad — el endpoint que consume esto (ver
`apps.el_catalogo.views.imagen_producto_publica`) además:

1. valida la firma y la expiración (aquí),
2. exige que el `file_id` sea la imagen de ALGÚN producto del catálogo (no
   permite leer archivos arbitrarios de Drive, igual que el proxy de avatar), y
3. sólo responde si el archivo es `image/*`.

**Por qué además se cachea.** Google no espera eternamente: si el origen tarda,
la conversión sigue sin la imagen y el PDF sale con el hueco. Bajar el archivo
de Drive en caliente son varios segundos, así que antes de mandarle el HTML a
Google **precalentamos** la imagen (`precalentar`): se baja UNA vez, se reduce
de tamaño y se guarda en caché. Cuando Google llega, el endpoint responde al
instante y con pocos KB.
"""

from __future__ import annotations

from django.conf import settings
from django.core import signing

# Salt propio: un token firmado para otra cosa no sirve como imagen pública.
SALT = "despacho.imagen_publica"

# Caché de bytes ya reducidos: clave por file_id de Drive. La vida es un poco
# mayor que el TTL del enlace para cubrir un reintento de la conversión.
CACHE_PREFIX = "imagen_publica:"
CACHE_TTL = 1800

# Lado máximo de la imagen que se sirve al documento. Una foto de celular de
# 4000px no aporta nada a 150pt de ancho y sí hace lenta la descarga.
LADO_MAX = 1000

# Vida del enlace. La conversión de Docs tarda segundos; 15 minutos deja
# holgura para reintentos sin dejar el enlace vivo de más.
TTL_SEGUNDOS = 900

# Nombre de la ruta que sirve la imagen (vive en El Taller, el dueño del
# catálogo). Si el urlconf activo no la tiene, `url_absoluta` degrada a "".
NOMBRE_URL = "catalogo-imagen-doc"


def firmar(file_id: str) -> str:
    """Token URL-safe con el `file_id` de Drive y sello de tiempo."""
    return signing.dumps({"f": str(file_id)}, salt=SALT)


def verificar(token: str, *, ttl: int = TTL_SEGUNDOS) -> str | None:
    """`file_id` si el token es legítimo y no expiró; `None` en cualquier otro
    caso (alterado, caducado, basura). Nunca lanza."""
    if not token:
        return None
    try:
        datos = signing.loads(token, salt=SALT, max_age=ttl)
    except Exception:  # noqa: BLE001 — firma inválida, expirado o malformado
        return None
    file_id = (datos or {}).get("f") if isinstance(datos, dict) else None
    return str(file_id) if file_id else None


def base_publica() -> str:
    """URL pública de El Taller, sin diagonal final."""
    base = getattr(settings, "TALLER_URL", "") or "https://taller.learningcenter.mx/"
    return str(base).rstrip("/")


def _clave(file_id: str) -> str:
    return f"{CACHE_PREFIX}{file_id}"


def desde_cache(file_id: str):
    """`(bytes, mime)` si la imagen ya está precalentada; `None` si no."""
    if not file_id:
        return None
    try:
        from django.core.cache import cache
        guardado = cache.get(_clave(file_id))
    except Exception:  # noqa: BLE001 — Redis caído: se sirve sin caché
        return None
    if isinstance(guardado, tuple | list) and len(guardado) == 2:
        return guardado[0], guardado[1]
    return None


def proporcion(file_id: str) -> float:
    """Alto ÷ ancho de la imagen ya precalentada (0.0 si no se puede saber).

    Sirve para estimar cuánto ocupa la foto en la hoja: en el documento va con
    ANCHO fijo, así que su alto depende de la proporción. Sin esto, una foto
    apaisada (un banner 4:1) se contaba como si fuera cuadrada y el hueco que
    empuja las notas al pie salía corto de más. Solo lee de caché — nunca baja
    de Drive ni lanza.
    """
    guardado = desde_cache(file_id)
    if not guardado:
        return 0.0
    try:
        import io

        from PIL import Image

        ancho, alto = Image.open(io.BytesIO(guardado[0])).size
        return (alto / ancho) if ancho else 0.0
    except Exception:  # noqa: BLE001 — Pillow no pudo con el archivo
        return 0.0


def _reducir(contenido: bytes, mime: str):
    """Baja la resolución a `LADO_MAX` para que la descarga sea de pocos KB.

    Si Pillow no puede con el archivo (formato raro, imagen corrupta), devuelve
    el original tal cual — más vale una imagen pesada que ninguna.
    """
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(contenido))
        if max(img.size) <= LADO_MAX and len(contenido) <= 400_000:
            return contenido, mime
        img.thumbnail((LADO_MAX, LADO_MAX), Image.LANCZOS)
        salida = io.BytesIO()
        if img.mode in ("RGBA", "LA", "P"):
            img.convert("RGBA").save(salida, format="PNG", optimize=True)
            return salida.getvalue(), "image/png"
        img.convert("RGB").save(salida, format="JPEG", quality=82, optimize=True)
        return salida.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001 — Pillow no pudo: se sirve el original
        return contenido, mime


def precalentar(file_id: str) -> bool:
    """Baja la imagen de Drive, la reduce y la deja en caché lista para servir.

    Se llama justo antes de mandarle el HTML a Google. Best-effort: cualquier
    fallo devuelve False y el endpoint bajará de Drive como siempre (más lento,
    con riesgo de que Google se canse y deje el hueco).
    """
    if not file_id or desde_cache(file_id) is not None:
        return bool(file_id)
    try:
        from django.core.cache import cache

        from lib.google_drive import drive

        contenido, mime, _ = drive.descargar(file_id)
        if not contenido or not (mime or "").startswith("image/"):
            return False
        contenido, mime = _reducir(contenido, mime)
        cache.set(_clave(file_id), (contenido, mime), CACHE_TTL)
        return True
    except Exception:  # noqa: BLE001 — Drive caído o sin permisos
        return False


def url_absoluta(file_id: str) -> str:
    """Enlace absoluto y firmado que Google puede bajar al convertir el PDF.

    Devuelve "" si no hay `file_id` o si el urlconf activo no expone la ruta
    (p.ej. La Gerencia) — el template simplemente omite la imagen.
    """
    if not file_id:
        return ""
    from django.urls import NoReverseMatch, reverse

    try:
        ruta = reverse(NOMBRE_URL, args=[firmar(file_id)])
    except NoReverseMatch:
        return ""
    return f"{base_publica()}{ruta}"


__all__ = [
    "SALT",
    "TTL_SEGUNDOS",
    "NOMBRE_URL",
    "CACHE_TTL",
    "LADO_MAX",
    "firmar",
    "verificar",
    "base_publica",
    "url_absoluta",
    "desde_cache",
    "precalentar",
    "proporcion",
]
