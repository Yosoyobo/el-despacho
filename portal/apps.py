from django.apps import AppConfig


class PortalConfig(AppConfig):
    """Quién de cada cliente puede entrar a La Recepción, y con qué enlace.

    App raíz compartida (patrón de `papeleo/`, `campanas/`): la usan TRES
    proyectos — El Taller invita y revoca, La Recepción deja entrar, y La
    Gerencia corre su migración (es la única que corre `migrate`, §14 Bug B).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "portal"
    label = "portal"
    verbose_name = "Portal de clientes (accesos)"
