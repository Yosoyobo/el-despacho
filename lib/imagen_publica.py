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
"""

from __future__ import annotations

from django.conf import settings
from django.core import signing

# Salt propio: un token firmado para otra cosa no sirve como imagen pública.
SALT = "despacho.imagen_publica"

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
    "firmar",
    "verificar",
    "base_publica",
    "url_absoluta",
]
