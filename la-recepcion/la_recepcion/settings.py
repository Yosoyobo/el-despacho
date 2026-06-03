"""Settings de La Recepción — stub S1a. UI completa en S5."""

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

import lib.boveda  # noqa: E402, F401

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.recepcion_stub.apps.RecepcionStubConfig",
    "auth_google.apps.AuthGoogleConfig",
    "proximamente.apps.ProximamenteConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "la_recepcion.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.request",
            "lib.aviso_deploy.contexto_aviso_deploy",
            "lib.version.contexto_version",
        ]},
    },
]
ASGI_APPLICATION = "la_recepcion.asgi.application"

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
