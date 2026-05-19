"""
Configuration Django — fonctionne en local ET sur Render sans modifier une ligne.

python-decouple lit depuis .env en local, depuis les variables d'environnement sur Render.
"""
import os
from pathlib import Path

from decouple import config, Csv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=Csv(),
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "catalogue",
    "chatbot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Juste après Security
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sav_chatbot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "sav_chatbot.wsgi.application"

# --- Base de données ---
# En local  : utilise les variables DB_* du .env
# Sur Render : utilise DATABASE_URL fournie par Neon
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default=(
            f"postgres://{config('DB_UTILISATEUR', default='postgres')}:"
            f"{config('DB_MOT_DE_PASSE', default='postgres')}@"
            f"{config('DB_HOTE', default='localhost')}:"
            f"{config('DB_PORT', default='5432')}/"
            f"{config('DB_NOM', default='sav_chatbot_db')}"
        ),
        conn_max_age=600,
        ssl_require=config("DB_SSL", default=False, cast=bool),
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

# --- Fichiers statiques via WhiteNoise ---
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Chatbot IA ---
GROQ_API_KEY = config("GROQ_API_KEY", default="")
IMPORT_TAILLE_LOT = config("IMPORT_TAILLE_LOT", default=500, cast=int)
CHATBOT_MAX_PRODUITS_CONTEXTE = config("CHATBOT_MAX_PRODUITS_CONTEXTE", default=5, cast=int)

# --- Sécurité HTTPS (production uniquement) ---
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"}
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "catalogue": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "chatbot": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
