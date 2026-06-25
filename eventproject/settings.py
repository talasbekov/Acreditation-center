# settings.py - исправленная версия
import logging
from pathlib import Path
from decouple import config, Csv

from eventproject.env_config import parse_bool_flag, require_env

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
# BE-6: все обязательные секреты грузим разом — один понятный ImproperlyConfigured
# со списком ВСЕХ отсутствующих, а не криптичный per-var UndefinedValueError на первой.
_required_env = require_env(config, {
    "SECRET_KEY": {},
    "AVALON_API_KEY": {},
    "KAZENERGY_API_KEY": {},
    "FERNET_KEYS": {"cast": Csv()},
    "ALLOWED_HOSTS": {"cast": Csv()},
})
SECRET_KEY = _required_env["SECRET_KEY"]
AVALON_API_KEY = _required_env["AVALON_API_KEY"]
KAZENERGY_API_KEY = _required_env["KAZENERGY_API_KEY"]
FERNET_KEYS = _required_env["FERNET_KEYS"]
ALLOWED_HOSTS = _required_env["ALLOWED_HOSTS"]


def _env_flag(name, default=False):
    value, recognized = parse_bool_flag(config(name, default=str(default)), default)
    if not recognized:
        # BE-15: typo («yess»/«enabled») не молчим — иначе секьюрный флаг
        # (SECURE_SSL_REDIRECT default=True) тихо отключился бы.
        logging.getLogger("eventproject").warning(
            "Нераспознанное значение булева флага %s — используется default=%s",
            name, default,
        )
    return value


DEBUG = _env_flag("DEBUG", default=False)
APPEND_SLASH = True

# CSRF и CORS настройки
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

# Secure-cookie по умолчанию True (прод за TLS). Локальный HTTP-стек (runserver без
# TLS) переопределяет в False через окружение — иначе браузер не шлёт Secure-cookie
# по HTTP и логин/CSRF не работают.
CSRF_COOKIE_SECURE = _env_flag("CSRF_COOKIE_SECURE", default=True)
CSRF_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE", default=True)
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
    "eventproject.apps.EventprojectConfig",  # Story 5.3: ready() → signals (media cleanup)
    "directories",
    "django_crontab",
    "qr_event",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise отдаёт STATIC_ROOT напрямую — и в dev (runserver при DEBUG=False),
    # и в prod (gunicorn). Без него Django статику не обслуживает (нужен был бы nginx).
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

# Story 2.4 (AC-5): порог неактивности оператора (дней) для warning-индикатора
# в реестре. Конфигурируется через .env.
OPERATOR_INACTIVITY_THRESHOLD_DAYS = config(
    "OPERATOR_INACTIVITY_THRESHOLD_DAYS", default=30, cast=int
)

# Story 3.2: идентификатор Казахстана в Attendee.countryId (резидент РК).
# Значение совпадает с legacy (eventproject/views/attendee.py:217).
KZ_COUNTRY_ID = config("KZ_COUNTRY_ID", default="1000000105")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "eventproject.api.exceptions.rfc7807_exception_handler",
    # Retro Epic 2: централизованная пагинация для всего /api/v1/ —
    # документированный envelope {count, next, previous, results}.
    "DEFAULT_PAGINATION_CLASS": "eventproject.api.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 50,
}

# Кэш: DatabaseCache (общий для всех воркеров gunicorn, без внешнего сервиса). Redis
# убран — его использовали только кэш дашборда (4.2) и django-ratelimit; оба переходят
# на БД. Таблицу кэша создаёт `python manage.py createcachetable` (идемпотентно).
# При необходимости можно переопределить бэкенд через окружение (managed-Redis и т.п.).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "eventproject_cache",
        "KEY_PREFIX": "eventproject",
        "TIMEOUT": 300,
    },
}

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

# Story 5.3 — two-phase upload staging. ВНЕ MEDIA_ROOT: не отдаётся через /media/
# (protected_media обслуживает только MEDIA_ROOT). Django стейджит крупные загрузки
# сюда при разборе запроса (фаза 1), serializer.save() переносит в MEDIA_ROOT (фаза 2).
MEDIA_TEMP_ROOT = config("MEDIA_TEMP_ROOT", default=str(BASE_DIR / "media_temp"))
try:
    Path(MEDIA_TEMP_ROOT).mkdir(parents=True, exist_ok=True)
except OSError as exc:
    # На read-only FS не валим импорт settings, но НЕ молчим — иначе загрузки
    # крупнее FILE_UPLOAD_MAX_MEMORY_SIZE падали бы непрозрачным 500 на parse.
    import logging as _logging

    _logging.getLogger("eventproject").warning(
        "MEDIA_TEMP_ROOT mkdir failed (%s): %s — загрузки на диск могут падать",
        MEDIA_TEMP_ROOT, exc,
    )
FILE_UPLOAD_TEMP_DIR = MEDIA_TEMP_ROOT
# Держим валидные загрузки (≤5 МБ) В ПАМЯТИ → не стейджим на диск (минуем temp-dir
# и его возможный сбой). Файлы крупнее лимита всё равно отклоняются валидацией.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024 + 1024  # чуть выше PHOTO_MAX_SIZE_BYTES

# Story 5.3 — серверная валидация фото участника И скана документа (Pillow).
# ratio = ширина/высота; вертикальный формат 3×4 ⇔ ratio ≤ PHOTO_MAX_RATIO.
PHOTO_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 МБ
PHOTO_MAX_RATIO = 0.85
PHOTO_MIN_WIDTH = 600
PHOTO_MIN_HEIGHT = 800
PHOTO_MAX_PIXELS = 40_000_000  # ~40 МП — анти-decompression-bomb (cap до декода)
PDF_RENDER_DPI = 150  # bounded dpi для pdf2image (анти-bomb на больших страницах)

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
            # BE-14: тот же structured_context, что и у console_json — консистентность
            # (запись несёт audit-поля; для их ВЫВОДА в файл сменить formatter на json).
            "filters": ["structured_context"],
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
