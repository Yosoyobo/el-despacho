"""Settings de El Taller — app de staff."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
for p in (str(REPO_ROOT), str(BASE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DESPACHO_ENV", "development") != "production"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

import lib.boveda  # noqa: E402, F401  (regla #2 — eager check)

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "cuentas.apps.CuentasConfig",
    "ajustes.apps.AjustesConfig",
    "buzon.apps.BuzonConfig",
    "interfono.apps.InterfonoConfig",
    "auth_google.apps.AuthGoogleConfig",
    "proximamente.apps.ProximamenteConfig",
    "referencias.apps.ReferenciasConfig",
    "chalanes.apps.ChalanesConfig",
    "apps.auth_taller.apps.AuthTallerConfig",
    "apps.taller_home.apps.TallerHomeConfig",
    "apps.legal.apps.LegalConfig",
    "apps.la_cartera.apps.LaCarteraConfig",
    "apps.los_proyectos.apps.LosProyectosConfig",
    "apps.el_pizarron.apps.ElPizarronConfig",
    "apps.calendario.apps.CalendarioConfig",
    "apps.buzon_empleado.apps.BuzonEmpleadoConfig",
    "apps.perfil_notificaciones.apps.PerfilNotificacionesConfig",
    # Pre-S2b.2: movidos desde La Gerencia.
    "apps.el_catalogo.apps.ElCatalogoConfig",
    "apps.perfil_chalanes.apps.PerfilChalanesConfig",
    # S2b.1
    "apps.recados.apps.RecadosConfig",
    # S2b.2
    "apps.el_dictado.apps.ElDictadoConfig",
    # S2b.3
    "apps.tesoreria.apps.TesoreriaConfig",
    # S2b.cotizaciones-v1
    "apps.cotizaciones.apps.CotizacionesConfig",
    # S2b.facturacion-v1
    "apps.facturacion.apps.FacturacionConfig",
    # S3.contaduria-v1
    "apps.contaduria.apps.ContaduriaConfig",
    # S-LC-Feedback-V3: página de ayuda con manual de usuario.
    "apps.ayuda.apps.AyudaConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "el_taller.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "interfono.context_processors.vapid_public_key",
                "auth_google.context_processors.google_oauth_configurado",
                "cuentas.context_processors.permisos_modulos",
                "apps.recados.context_processors.recados_no_leidos",
                "lib.aviso_deploy.contexto_aviso_deploy",
                "apps.taller_home.context_processors.sidebar_grupos",
            ],
        },
    },
]

ASGI_APPLICATION = "el_taller.asgi.application"
WSGI_APPLICATION = "el_taller.wsgi.application"

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
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LOGIN_URL = "/sign-in"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/sign-in"

SESSION_COOKIE_NAME = "taller_session"
CSRF_COOKIE_NAME = "taller_csrftoken"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if "." in h]

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
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
LOGIN_RATELIMIT = {"limite": 5, "ventana_seg": 60 * 15}

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
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
