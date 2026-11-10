from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend


class DynamicEmailBackend(SMTPBackend):
    """
    Reads SMTP settings from the DB (EmailConfig) at runtime.
    Falls back to settings.EMAIL_* from .env if DB row missing.
    """

    def __init__(self, *args, **kwargs):
        # Lazy import to avoid app-loading circulars
        try:
            from .models import EmailConfig
            cfg = EmailConfig.objects.filter(is_active=True).first()
        except Exception:
            cfg = None

        if cfg:
            kwargs.setdefault("host", cfg.host)
            kwargs.setdefault("port", cfg.port)
            kwargs.setdefault("username", cfg.username)
            kwargs.setdefault("password", cfg.password)
            kwargs.setdefault("use_tls", cfg.use_tls)
            kwargs.setdefault("use_ssl", cfg.use_ssl)
        else:
            kwargs.setdefault("host", getattr(settings, "EMAIL_HOST", "localhost"))
            kwargs.setdefault("port", getattr(settings, "EMAIL_PORT", 25))
            kwargs.setdefault("username", getattr(settings, "EMAIL_HOST_USER", ""))
            kwargs.setdefault("password", getattr(settings, "EMAIL_HOST_PASSWORD", ""))
            kwargs.setdefault("use_tls", getattr(settings, "EMAIL_USE_TLS", False))
            kwargs.setdefault("use_ssl", getattr(settings, "EMAIL_USE_SSL", False))

        kwargs.setdefault("fail_silently", False)
        super().__init__(*args, **kwargs)