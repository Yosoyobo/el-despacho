"""Settings de prueba — merge de El Taller + La Gerencia con SQLite en memoria.

No usar en runtime. Solo para pytest. Permite que tests de vistas Django
cubran los CRUDs de S1b y la Auth de ambos proyectos sin levantar Postgres.
"""

import os
import secrets

# Garantiza claves antes de importar lib.boveda (eager check, regla #2).
os.environ.setdefault("BOVEDA_MASTER_KEY", secrets.token_hex(32))
os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = ["*"]

import lib.boveda  # noqa: F401, E402  (regla #2)

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
    # El Taller
    "apps.auth_taller.apps.AuthTallerConfig",
    "apps.taller_home.apps.TallerHomeConfig",
    "apps.legal.apps.LegalConfig",
    "apps.la_cartera.apps.LaCarteraConfig",
    "apps.los_proyectos.apps.LosProyectosConfig",
    "apps.el_pizarron.apps.ElPizarronConfig",
    "apps.calendario.apps.CalendarioConfig",
    "apps.buzon_empleado.apps.BuzonEmpleadoConfig",
    "apps.perfil_notificaciones.apps.PerfilNotificacionesConfig",
    "apps.el_catalogo.apps.ElCatalogoConfig",
    "apps.perfil_chalanes.apps.PerfilChalanesConfig",
    "apps.recados.apps.RecadosConfig",
    "apps.el_dictado.apps.ElDictadoConfig",
    "apps.tesoreria.apps.TesoreriaConfig",
    "apps.cotizaciones.apps.CotizacionesConfig",
    "apps.facturacion.apps.FacturacionConfig",
    "apps.contaduria.apps.ContaduriaConfig",
    "apps.ayuda.apps.AyudaConfig",
    # La Gerencia (apps es namespace pkg — convive con El Taller)
    "apps.auth_gerencia.apps.AuthGerenciaConfig",
    "apps.el_directorio.apps.ElDirectorioConfig",
    "apps.los_ajustes.apps.LosAjustesConfig",
    "apps.gerencia_home.apps.GerenciaHomeConfig",
    "apps.api.apps.ApiConfig",
    "apps.buzon_admin.apps.BuzonAdminConfig",
    "apps.el_site.apps.ElSiteConfig",
    "apps.interfono_admin.apps.InterfonoAdminConfig",
    "apps.los_chalanes.apps.LosChalanesConfig",
    "apps.centros_costo.apps.CentrosCostoConfig",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "tests.urls_taller"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(os.path.dirname(__file__), "..", "el-taller", "templates"),
            os.path.join(os.path.dirname(__file__), "..", "la-gerencia", "templates"),
        ],
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
                "apps.recados.context_processors.recados_no_leidos",
                "apps.taller_home.context_processors.sidebar_grupos",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

AUTH_USER_MODEL = "cuentas.Usuario"
AUTH_PASSWORD_VALIDATORS = []  # tests rápidos
LOGIN_URL = "/sign-in"

SESSION_COOKIE_NAME = "taller_session"
CSRF_COOKIE_NAME = "taller_csrftoken"

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_RATELIMIT = {"limite": 5, "ventana_seg": 60 * 15}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "El Despacho — Inventario de Endpoints",
    "VERSION": "0.1.0-s2a",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
}

LOGGING = {"version": 1, "disable_existing_loggers": True}
