import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")

DEBUG = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET_KEY", "change-me")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "*").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "linemarking_hub",  # Main app with templatetags
    "accounts",
    "mail",
    "jobs",
    "automation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Must be after SecurityMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

ROOT_URLCONF = "linemarking_hub.urls"

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
            ]
        },
    }
]

WSGI_APPLICATION = "linemarking_hub.wsgi.application"

# Database configuration using individual DB_* environment variables
if all(
    os.environ.get(key)
    for key in ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
):
    db_config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "HOST": os.environ.get("DB_HOST"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
    # Add SSL mode if specified (for psycopg2 compatibility)
    sslmode = os.environ.get("DB_SSLMODE")
    if sslmode:
        db_config["OPTIONS"] = {"sslmode": sslmode.lower()}
    DATABASES = {"default": db_config}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-au"

TIME_ZONE = "Australia/Brisbane"  # Always GMT+10 (no daylight saving time)

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# WhiteNoise configuration for serving static files in production
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"]
}

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)

# Google OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

# Microsoft OAuth Configuration
MICROSOFT_OAUTH_CLIENT_ID = os.environ.get("MICROSOFT_OAUTH_CLIENT_ID", "")
MICROSOFT_OAUTH_CLIENT_SECRET = os.environ.get("MICROSOFT_OAUTH_CLIENT_SECRET", "")
MICROSOFT_OAUTH_TENANT_ID = os.environ.get("MICROSOFT_OAUTH_TENANT_ID", "common")

# Authentication Configuration
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/auth/login/"

# Email sync: caps for first sync vs incremental (paginated; avoid missing emails)
EMAIL_FIRST_SYNC_MAX_MESSAGES = int(os.environ.get("EMAIL_FIRST_SYNC_MAX_MESSAGES", "500"))
EMAIL_INCREMENTAL_SYNC_MAX_MESSAGES = int(
    os.environ.get("EMAIL_INCREMENTAL_SYNC_MAX_MESSAGES", "200")
)
# Email sync audit: log each onboarding/sync decision (Gmail fetch, store, queue). Set to false in production to keep logs quiet.
EMAIL_SYNC_AUDIT_LOGGING = os.environ.get("EMAIL_SYNC_AUDIT_LOGGING", "true").lower() in ("1", "true", "yes")

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Stripe Configuration
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")

# Logging Configuration
# DigitalOcean App Platform captures stdout/stderr, so we log to console
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "stream": "ext://sys.stdout",
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "stream": "ext://sys.stderr",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django.request": {
            "handlers": ["error_console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": os.environ.get("DB_LOG_LEVEL", "WARNING"),  # Set to DEBUG to see SQL queries
            "propagate": False,
        },
        # Application loggers
        "accounts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "mail": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "mail.sync_audit": {
            "handlers": ["console"],
            "level": "INFO" if EMAIL_SYNC_AUDIT_LOGGING else "WARNING",
            "propagate": False,
        },
        "automation": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "jobs": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "linemarking_hub": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # Third-party loggers
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "gunicorn": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
