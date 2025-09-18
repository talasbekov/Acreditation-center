# settings.py - исправленная версия
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-6sl-*ire%_p+en7)xv&6w)x5m3q8-9yzx0c+#)jy$i4)$xxck*"
AVALON_API_KEY = "Fe6dv1LkLMpY0pqwSuocznfwyGo77upgHYfobtPDM98REHKMWXmW3KW6WKbYZ2t5Q2Fd515wPhIVpYaYt1zRghD3mDB6EQ04XzSD6meoAWVdvZT5vrfM6vCPumCzr55hh"

DEBUG = True
APPEND_SLASH = True

ALLOWED_HOSTS = ["localhost", "*"]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "eventproject",
    "directories",
    "django_crontab",
    "qr_event",
    'django_celery_beat'
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

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
        "NAME": "eventdb",
        "USER": "event", 
        "PASSWORD": "aktobe",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }
}

GUNICORN_CONFIG = {
    "timeout": 300,
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / "django_cache",
        "TIMEOUT": 1,
    }
}


# # Кеширование - используем Redis для синхронизации между контейнерами
# try:
#     import django_redis  # проверяем есть ли библиотека
#     CACHES = {
#         "default": {
#             "BACKEND": "django_redis.cache.RedisCache",
#             "LOCATION": "redis://127.0.0.1:6379/1",
#             "KEY_PREFIX": "eventproject",
#             "TIMEOUT": 120,
#             "OPTIONS": {
#                 "CLIENT_CLASS": "django_redis.client.DefaultClient",
#                 "CONNECTION_POOL_KWARGS": {"max_connections": 20},
#             }
#         }
#     }
# except ImportError:
#     # fallback на стандартный RedisCache Django
#     CACHES = {
#         "default": {
#             "BACKEND": "django.core.cache.backends.redis.RedisCache",
#             "LOCATION": "redis://127.0.0.1:6379/1",
#             "KEY_PREFIX": "eventproject",
#             "TIMEOUT": 120,
#         }
#     }


# Celery настройки
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Almaty'
CELERY_ENABLE_UTC = True

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

MEDIA_ROOT = MEDIA_DIR
MEDIA_URL = "/media/"

# Статика
STATIC_URL = "/static/"
STATICFILES_DIRS = [STATIC_DIR]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Логирование
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
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
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "celery": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "celery.task": {
            "handlers": ["console", "file"],
            "level": "INFO", 
            "propagate": False,
        },
        "eventproject": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        }
    },
}

# Crontab
CRONJOBS_LOGGING = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CRONJOBS = [
    ('*/2 * * * *', 'eventproject.cron.kazenergy_receive'),
]