from django.apps import AppConfig


class CuentasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cuentas"
    verbose_name = "Cuentas (Usuario compartido)"

    def ready(self):
        # Registra signals (auto-seed de PermisoUsuario para nuevos usuarios).
        from . import signals  # noqa: F401
