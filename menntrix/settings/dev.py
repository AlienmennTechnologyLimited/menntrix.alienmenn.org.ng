import pymysql
pymysql.install_as_MySQLdb()

from .base import *

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'alienmen_alienmenn_db',
        'USER': 'root',
        'PASSWORD': '12345678',
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}

SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}