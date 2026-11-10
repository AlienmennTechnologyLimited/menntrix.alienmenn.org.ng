from django.apps import AppConfig


class MenntrixCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "menntrix_core"

    def ready(self):
        # Register login/logout signal handlers
        from . import signals  # noqa