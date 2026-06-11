import os
from cryptography.fernet import Fernet

os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["AVALON_API_KEY"] = "test-avalon-api-key"
os.environ["KAZENERGY_API_KEY"] = "test-kazenergy-api-key"
os.environ["FERNET_KEYS"] = Fernet.generate_key().decode()
os.environ["DEBUG"] = "False"
os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,testserver"
os.environ["DB_NAME"] = "test-db"
os.environ["DB_USER"] = "test-user"
os.environ["DB_PASSWORD"] = "test-password"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"

from .settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "eventproject-test-cache",
    }
}

MEDIA_ROOT = BASE_DIR / "test_media"

# Отключаем axes для тестов, если он мешает (но в нашем тесте он может быть нужен)
# AXES_ENABLED = False 

# Для тестов ratelimit
RATELIMIT_ENABLE = True

# Disable secure cookies for tests as they are not over HTTPS
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
