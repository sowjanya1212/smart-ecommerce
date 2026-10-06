"""Django settings for the Smart E-Commerce admin panel."""
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent


def _load_env():
    """Tiny .env loader (no extra dependency). Real env vars win."""
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()


def _csv(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = _csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = _csv("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8001")

INSTALLED_APPS = [
    "shop",  # first, so its templates/admin/index.html overrides the default
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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


def _database():
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith(("postgres://", "postgresql")):
        u = urlparse(url.replace("postgresql+psycopg2://", "postgresql://"))
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": u.path.lstrip("/"),
            "USER": unquote(u.username or ""),
            "PASSWORD": unquote(u.password or ""),
            "HOST": u.hostname or "localhost",
            "PORT": str(u.port or 5432),
        }
    path = url[len("sqlite:///"):] if url.startswith("sqlite:///") else "data/db.sqlite3"
    path = Path(path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return {"ENGINE": "django.db.backends.sqlite3", "NAME": str(path)}


DATABASES = {"default": _database()}

AUTH_USER_MODEL = "shop.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = DEBUG

# Media is shared with FastAPI (it serves /media). Admin uploads land here.
MEDIA_ROOT = ROOT_DIR / "media"
MEDIA_URL = os.environ.get("PUBLIC_MEDIA_URL", "http://localhost:8000/media/")

# ---- Shop-specific settings ----
LOW_STOCK_THRESHOLD = int(os.environ.get("LOW_STOCK_THRESHOLD", "5"))
FASTAPI_INTERNAL_URL = os.environ.get("FASTAPI_INTERNAL_URL", "http://localhost:8000")
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "change-me-internal")

# ---- Email ----
if os.environ.get("SMTP_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["SMTP_HOST"]
    EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("SMTP_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    EMAIL_USE_TLS = os.environ.get("SMTP_TLS", "1") == "1"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("EMAIL_FROM", "Smart Shop <no-reply@smartshop.local>")

LOGIN_URL = "/admin/login/"
