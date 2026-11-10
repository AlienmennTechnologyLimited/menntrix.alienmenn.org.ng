from .base import *

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "alienmen_alienmenn_db"),
        "USER": os.getenv("DB_USER", "root"),
        "PASSWORD": os.getenv("DB_PASSWORD", "12345678"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

SESSION_COOKIE_DOMAIN = ".alienmenn.org.ng"
CSRF_COOKIE_DOMAIN = ".alienmenn.org.ng"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_AGE = 1209600
SESSION_SAVE_EVERY_REQUEST = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

ALLOWED_HOSTS = [".alienmenn.org.ng"]
CSRF_TRUSTED_ORIGINS = ["https://menntrix.alienmenn.org.ng"]

import os as _os

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(_os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))],
        },
    }
}