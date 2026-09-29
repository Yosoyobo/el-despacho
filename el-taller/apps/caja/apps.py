from django.apps import AppConfig


class CajaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.caja"
    label = "caja"
    verbose_name = "La Caja"

    def ready(self):
        from . import signals  # noqa: F401
