from django.apps import AppConfig


class FacturacionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.facturacion"
    label = "facturacion"
    verbose_name = "La Facturación"

    def ready(self):
        from . import signals  # noqa: F401
