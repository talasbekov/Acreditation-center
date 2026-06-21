# settings.py - исправленная версия
from pathlib import Path
from decouple import config, Csv
from celery.schedules import crontab

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

LOG_DIR = BASE_DIR / "logs"
try:
    LOG_DIR.mkdir(exist_ok=True)
except OSError:
    # На read-only FS (или если logs существует как обычный файл) не валим импорт
    # settings — RotatingFileHandler сам сообщит об ошибке при первой записи.
    pass

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')
AVALON_API_KEY = config('AVALON_API_KEY')
KAZENERGY_API_KEY = config('KAZENERGY_API_KEY')
FERNET_KEYS = config("FERNET_KEYS", cast=Csv())


def _env_flag(name, default=False):
    value = str(config(name, default=str(default))).strip().lower()
    return value in {"1", "true", "yes", "on"}


DEBUG = _env_flag("DEBUG", default=False)
APPEND_SLASH = True

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

# CSRF и CORS настройки
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = _env_flag("SECURE_SSL_REDIRECT", default=True)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"

SESSION_COOKIE_AGE = 43200  # 12 часов по умолчанию (для Оператора)

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "axes",  # django-axes
    "eventproject",
    "directories",
    "django_crontab",
    "qr_event",
    'django_celery_beat'
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "axes.middleware.AxesMiddleware",  # django-axes middleware
    "eventproject.middleware.ratelimit.RatelimitMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "eventproject.middleware.session_timeout.RoleBasedSessionTimeoutMiddleware",
    # Story 2.3 (AC-5): форс смены пароля для авто-созданных операторов.
    # После AuthenticationMiddleware (нужен request.user).
    "eventproject.middleware.force_password_change.ForcePasswordChangeMiddleware",
    "eventproject.middleware.logging_middleware.RequestLoggingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Axes settings — используем только REMOTE_ADDR: nginx не гарантирует sanitize X-Forwarded-For
AXES_IPWARE_META_PRECEDENCE_ORDER = [
    'REMOTE_ADDR',
]
AXES_FAILURE_LIMIT = 10
AXES_COOLOFF_TIME = 1  # в часах
AXES_RESET_ON_SUCCESS = True

ROOT_URLCONF = "eventproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": ["templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
            ],
        },
    },
]

WSGI_APPLICATION = "eventproject.wsgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config('DB_NAME'),
        "USER": config('DB_USER'),
        "PASSWORD": config('DB_PASSWORD'),
        "HOST": config('DB_HOST', default='192.168.0.104'),
        "PORT": config('DB_PORT', default='5432'),
    }
}

GUNICORN_CONFIG = {
    "timeout": 300,
}

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="", cast=Csv())

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "eventproject.api.exceptions.rfc7807_exception_handler",
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_CACHE_URL", default="redis://redis:6379/1"),
        "KEY_PREFIX": "eventproject",
        "TIMEOUT": 300,
    },
}


# Celery настройки
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://redis:6379/0")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Almaty'
CELERY_ENABLE_UTC = True

# Email (Story 2.3 — онбординг операторов). Значения берутся из .env; по умолчанию
# console-backend (письма печатаются в stdout), чтобы dev/CI не требовали SMTP.
EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=25, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = _env_flag("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="noreply@accreditation.local"
)
# Ссылка для входа в письме оператору.
OPERATOR_LOGIN_URL = config("OPERATOR_LOGIN_URL", default="/user_login/")

# Настройки архивов
ARCHIVE_STORAGE_DURATION = 24  # часов
MAX_ARCHIVE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Пути файлов
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
MEDIA_DIR = BASE_DIR / "media"

MEDIA_URL = "/media/"
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "media"))

# Статика
STATIC_URL = "/static/"
STATICFILES_DIRS = [STATIC_DIR]
STATIC_ROOT = BASE_DIR / "staticfiles"


# Логирование
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "structured_context": {
            "()": "eventproject.logging_filters.StructuredContextFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(user_id)s %(role)s %(action)s %(obj_type)s %(obj_id)s %(ip)s %(message)s",
            "rename_fields": {"levelname": "level", "asctime": "timestamp"},
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "console_json": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["structured_context"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "app.log"),
            "maxBytes": 5 * 1024 * 1024,   # 5 MB
            "backupCount": 3,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console_json", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console_json", "file"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console_json", "file"], "level": "INFO", "propagate": False},
        "celery.task": {"handlers": ["console_json", "file"], "level": "INFO", "propagate": False},
        "eventproject": {"handlers": ["console_json", "file"], "level": "INFO", "propagate": False},
        "request_logger": {  # новый логгер
            "handlers": ["console_json", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Crontab
CRONJOBS_LOGGING = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CRONJOBS = [
    ('*/2 * * * *', 'eventproject.cron.kazexpo_import_job'),
]
