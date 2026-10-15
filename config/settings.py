import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv("DEBUG", "0") == "1"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insegura-cambiar-en-produccion")
if not DEBUG and SECRET_KEY.startswith("dev-insegura") and os.getenv("VERCEL"):
    raise RuntimeError("Define la variable de entorno SECRET_KEY en Vercel.")

ALLOWED_HOSTS = [h.strip() for h in os.getenv(
    "ALLOWED_HOSTS", ".vercel.app,localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = ["django.contrib.staticfiles", "simulador"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware",
              "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]

DATABASES = {}                      # sin base de datos
STATIC_URL = "/static/"
# En Vercel, public/static se sirve desde el CDN; en local lo sirve runserver.
STATICFILES_DIRS = [BASE_DIR / "public" / "static"]
LANGUAGE_CODE = "es-mx"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
