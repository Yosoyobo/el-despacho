from django.apps import AppConfig


class ContaduriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.contaduria"
    label = "contaduria"
    verbose_name = "La Contaduría"

    def ready(self):
        # Engancha signals de Tesorería que generan asientos automáticos
        # al crear ingresos/egresos. Import lazy para evitar problemas de
        # carga de apps.
        from . import signals  # noqa: F401
