from django.apps import AppConfig


class ChalanesConfig(AppConfig):
    name = "chalanes"
    verbose_name = "Los Chalanes (IA multi-provider)"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401
