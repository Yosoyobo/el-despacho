"""Settings de La Recepción — el portal de clientes B2B (S5, 2026-09-29).

**Lee la misma Postgres que El Taller, pero NO corre `migrate`** (§14 Bug B: sólo
La Gerencia migra). Para leer clientes, proyectos, cotizaciones y facturas
instala los MODELOS de El Taller que cierran el grafo de llaves foráneas —igual
que La Gerencia— sin montar ninguna de sus pantallas. Cada app de aquí abajo
tiene su `COPY` en `la-recepcion/Dockerfile` (§14 Bug A); el smoke test del
stack en Docker (§13) atrapa la que falte.

**Los clientes no son usuarios.** `django.contrib.auth` y `cuentas` están
instalados sólo porque los modelos de negocio apuntan a `cuentas.Usuario`
(creado_por, etc.). No hay `AuthenticationMiddleware` ni login de staff: la
sesión de La Recepción guarda un `portal.AccesoCliente` y nada más, con su
propia cookie (`recepcion_session`, §4 #15).
"""

import importlib.util
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
# En el contenedor todo vive en /app. Fuera de él (HAL, `manage.py check`) hay
# que agregar la raíz del repo y la carpeta de El Taller, de donde vienen las
# apps de negocio (`apps.la_cartera`, `apps.cotizaciones`…).
for p in (str(REPO_ROOT), str(BASE_DIR), str(REPO_ROOT / "el-taller")):
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DESPACHO_ENV", "development") != "production"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]
# Host canónico productivo siempre aceptado, aunque el .env del servidor quede
# desfasado tras un cambio de dominio (defensa contra rollback en deploy). Y
# `localhost`: es el Host con el que pregunta el healthcheck del compose
# (`/ping` desde dentro del contenedor). Sin él, un .env que sólo trajera el
# dominio dejaría al contenedor `unhealthy` para siempre.
if "*" not in ALLOWED_HOSTS:
    for _h in ("recepcion.learningcenter.mx", "localhost", "127.0.0.1"):
        if _h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_h)

# Falla rápido si falta BOVEDA_MASTER_KEY (regla #2).
import lib.boveda  # noqa: E402, F401

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Compartidas: el usuario del equipo (al que apuntan los `creado_por`), las
    # credenciales cifradas (El Cartero, Drive, Google) y El Interfón (el aviso
    # al equipo cuando un cliente responde una cotización). Referencias,
    # Chalanes, Campañas y Papeleo NO: el portal no los toca y el grafo de
    # llaves cierra sin ellos (medido con `manage.py check`).
    "cuentas.apps.CuentasConfig",
    "ajustes.apps.AjustesConfig",
    "interfono.apps.InterfonoConfig",
    # Los accesos de los clientes.
    "portal.apps.PortalConfig",
    # Modelos de El Taller. Mismo grafo que La Gerencia: tesoreria.Ingreso →
    # facturacion.Factura → cotizaciones.Cotizacion → el_catalogo, y
    # proyectos ↔ pizarrón ↔ checador. Sin URLs: sólo el ORM.
    "apps.la_cartera.apps.LaCarteraConfig",
    "apps.los_proyectos.apps.LosProyectosConfig",
    "apps.el_pizarron.apps.ElPizarronConfig",
    "apps.el_catalogo.apps.ElCatalogoConfig",
    "apps.tesoreria.apps.TesoreriaConfig",
    "apps.cotizaciones.apps.CotizacionesConfig",
    "apps.facturacion.apps.FacturacionConfig",
    "apps.contaduria.apps.ContaduriaConfig",
    "apps.checador.apps.CheckadorConfig",
    # El portal mismo.
    "apps.portal_cliente.apps.PortalClienteConfig",
]

# La Caja (contrato del sprint): si su app está en la imagen, el portal enseña
# el botón «Pagar» con `apps.caja.services.url_pago()`. Si no está —se integra
# en otra rama—, el portal funciona igual, sin botón. El Dockerfile la copia
# sólo si existe, por la misma razón.
def _hay_caja() -> bool:
    try:
        return importlib.util.find_spec("apps.caja.apps") is not None
    except (ImportError, ValueError):
        return False


if _hay_caja():
    INSTALLED_APPS.append("apps.caja.apps.CajaConfig")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Deja pasar sólo a una sesión de cliente viva; todo lo demás, a /entrar/.
    "apps.portal_cliente.middleware.SesionClienteMiddleware",
]

ROOT_URLCONF = "la_recepcion.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.request",
            "django.template.context_processors.csrf",
            "django.contrib.messages.context_processors.messages",
            "lib.aviso_deploy.contexto_aviso_deploy",
            "lib.version.contexto_version",
            "apps.portal_cliente.context_processors.portal",
        ]},
    },
]
ASGI_APPLICATION = "la_recepcion.asgi.application"
WSGI_APPLICATION = "la_recepcion.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_USER_MODEL = "cuentas.Usuario"

# Sesión PROPIA del cliente (§4 #15): no choca con las del equipo aunque algún
# día compartieran dominio raíz.
SESSION_COOKIE_NAME = "recepcion_session"
CSRF_COOKIE_NAME = "recepcion_csrftoken"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if "." in h]

# Los mensajes van en la sesión (no hay usuario de Django al que colgarlos).
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Dónde vive El Taller (los botones de pago de La Caja apuntan allá) y La
# Recepción misma (el enlace que va en los correos).
TALLER_URL = os.environ.get("TALLER_URL", "https://taller.learningcenter.mx/")
RECEPCION_URL = os.environ.get("RECEPCION_URL", "https://recepcion.learningcenter.mx")
MEDIOS_DIR = os.environ.get("MEDIOS_DIR", "/app/medios")

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
