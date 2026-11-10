from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# ============================================================
# CORE
# ============================================================
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# ============================================================
# APPS
# ============================================================
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "channels",

    "menntrix_core",
    "menntrix_accounts",
    "menntrix_messaging",
    "menntrix_connections",
    "menntrix_calls",
    "menntrix_meetings",
    "menntrix_channels",
    "menntrix_revenue",
    
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "menntrix_core.middleware.MenntrixSessionMiddleware",
]

ROOT_URLCONF = "menntrix.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "django.template.context_processors.media",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "menntrix.wsgi.application"
ASGI_APPLICATION = "menntrix.asgi.application"

# ============================================================
# AUTH
# ============================================================
AUTH_USER_MODEL = "menntrix_accounts.UserAccount"

# Support BOTH bcrypt (existing users 468+) and Django default (new signups)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "signin"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "signin"

# ============================================================
# I18N
# ============================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# ============================================================
# STATIC & MEDIA
# ============================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# FILE UPLOADS (attachments, profile pictures, channel assets)
# ============================================================
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024   # 25 MB in-memory
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024   # 25 MB POST body
DATA_UPLOAD_MAX_NUMBER_FILES = 20                # per request

# Allowed MIME type whitelist (server-side enforcement)
MENNTRIX_ATTACHMENT_MAX_BYTES = 25 * 1024 * 1024  # 25 MB per file

# ============================================================
# SESSION / CSRF COOKIES
# Set SESSION_COOKIE_DOMAIN in .env for cross-subdomain SSO.
# Leave blank in dev.
# ============================================================
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", "").strip() or None
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "1209600"))  # 14 days
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_DOMAIN = SESSION_COOKIE_DOMAIN
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False   # must be False so JS can read it
CSRF_COOKIE_SAMESITE = "Lax"

# ============================================================
# SECURITY HEADERS
# ============================================================
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ============================================================
# MENNTRIX
# ============================================================
MENNTRIX_SESSION_USER_KEY = "MM_Username"

MENNTRIX_ICE_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
]

MENNTRIX_MESSAGE_PAGE_SIZE = 20
MENNTRIX_DEV_MANAGED_USER = os.getenv("MENNTRIX_DEV_MANAGED_USER", "False") == "True"

# ============================================================
# DJANGO CHANNELS
# Dev: InMemoryChannelLayer (see dev.py)
# Prod: channels_redis (see prod.py)
# ============================================================
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# ============================================================
# EMAIL — dynamic backend (config from DB, fallback to .env)
# ============================================================
EMAIL_BACKEND = "menntrix_core.email_backend.DynamicEmailBackend"

EMAIL_HOST = os.getenv("EMAIL_HOST", "mail.alienmenn.org.ng")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "team@alienmenn.org.ng")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "team@alienmenn.org.ng")

# ============================================================
# WEB PUSH (VAPID)
# ============================================================
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_EMAIL = os.getenv("VAPID_EMAIL", "mailto:team@alienmenn.org.ng")
MENNTRIX_PUSH_ENABLED = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)

# ============================================================
# SERVICE WORKER
# Served from root so scope '/' works.
# ============================================================
MENNTRIX_SERVICE_WORKER_TEMPLATE = "menntrix-sw.js"