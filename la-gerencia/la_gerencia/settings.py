"""Settings de La Gerencia — el panel admin de El Despacho."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# El layout del contenedor monta lib/, cuentas/, ajustes/ en /app/.
# Para correr `manage.py` en HAL local (fuera del container), agregamos la raíz del repo.
REPO_ROOT = BASE_DIR.parent
for p in (str(REPO_ROOT), str(BASE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DESPACHO_ENV", "development") != "production"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

# Forzar import de lib.boveda al arrancar — falla rápido si falta BOVEDA_MASTER_KEY (regla #2).
import lib.boveda  # noqa: E402, F401

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Compartidas
    "cuentas.apps.CuentasConfig",
    "ajustes.apps.AjustesConfig",
    "buzon.apps.BuzonConfig",
    "interfono.apps.InterfonoConfig",
    "auth_google.apps.AuthGoogleConfig",
    "proximamente.apps.ProximamenteConfig",
    "referencias.apps.ReferenciasConfig",
    "chalanes.apps.ChalanesConfig",
    # De La Gerencia
    "apps.auth_gerencia.apps.AuthGerenciaConfig",
    "apps.el_directorio.apps.ElDirectorioConfig",
    "apps.los_ajustes.apps.LosAjustesConfig",
    "apps.gerencia_home.apps.GerenciaHomeConfig",
    "apps.legal.apps.LegalConfig",
    "apps.api.apps.ApiConfig",
    # Pre-S2b.2: El Catálogo se mudó a El Taller. Gerencia mantiene un
    # redirect 302 → Taller en urls.py para preservar bookmarks viejos.
    "apps.buzon_admin.apps.BuzonAdminConfig",
    "apps.el_site.apps.ElSiteConfig",
    "apps.interfono_admin.apps.InterfonoAdminConfig",
    "apps.los_chalanes.apps.LosChalanesConfig",
    # S2b.3 — modelos viven en El Taller (apps.tesoreria); Gerencia
    # importa el modelo y agrega el CRUD admin de Centros de costo.
    # `la_cartera` y `los_proyectos` se instalan porque los modelos de
    # Tesorería tienen FK a Cliente y Proyecto (Egreso.proyecto,
    # Ingreso.cliente/proyecto). Sin esos apps, Django levanta E300
    # al hacer system checks (detectado en CI smoke test de S2b.3).
    # Gerencia no expone URLs de Cartera ni Proyectos — solo necesita
    # los modelos registrados para que el grafo de FKs cierre.
    "apps.la_cartera.apps.LaCarteraConfig",
    "apps.los_proyectos.apps.LosProyectosConfig",
    "apps.tesoreria.apps.TesoreriaConfig",
    "apps.centros_costo.apps.CentrosCostoConfig",
    # S2b.cotizaciones-v1 + S2b.facturacion-v1 + S3.contaduria-v1/v2:
    # mismos modelos viven en El Taller. Gerencia los registra porque
    # tesoreria.Ingreso.factura → facturacion.Factura → cotizaciones.Cotizacion
    # → el_catalogo.Servicio cierran el grafo de FKs (Bug A — sin esto el
    # system check de Django tira E300/E307 al arrancar el contenedor de
    # Gerencia). Detectado en CI smoke test de S2b.facturacion-v1.
    "apps.el_catalogo.apps.ElCatalogoConfig",
    "apps.cotizaciones.apps.CotizacionesConfig",
    "apps.facturacion.apps.FacturacionConfig",
    "apps.contaduria.apps.ContaduriaConfig",
    # 3rd party
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
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
    # Pre-S2b.2: redirige contador/disenador autenticados a El Taller.
    "lib.middleware.RedirigirRolesOperativosMiddleware",
]

ROOT_URLCONF = "la_gerencia.urls"

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
                "apps.el_site.context_processors.badge_integraciones",
                "interfono.context_processors.vapid_public_key",
                "auth_google.context_processors.google_oauth_configurado",
                "cuentas.context_processors.permisos_modulos",
                "lib.aviso_deploy.contexto_aviso_deploy",
            ],
        },
    },
]

ASGI_APPLICATION = "la_gerencia.asgi.application"
WSGI_APPLICATION = "la_gerencia.wsgi.application"

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

# Pre-S2b.2: destino de redirección para roles operativos. Override en tests
# con `@override_settings(TALLER_URL="http://testserver/")`.
TALLER_URL = os.environ.get("TALLER_URL", "https://taller.ninomeando.com/")
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/sign-in"

# Cookie de sesión nombrada para no chocar con El Taller si compartieran subdominio.
SESSION_COOKIE_NAME = "gerencia_session"
CSRF_COOKIE_NAME = "gerencia_csrftoken"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if "." in h
]

# Cache + sesiones en Redis
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

# Login rate-limit
LOGIN_RATELIMIT = {"limite": 5, "ventana_seg": 60 * 15}

# Headers de seguridad básicos
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# DRF: SessionAuthentication (cookie gerencia_session) + permisos default
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "El Despacho — Inventario de Endpoints",
    "DESCRIPTION": "Documentación interna de los endpoints JSON. Acceso restringido a super_admin.",
    "VERSION": "0.1.0-s2a",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PUBLIC": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
