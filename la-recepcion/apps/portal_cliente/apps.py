from django.apps import AppConfig


class PortalClienteConfig(AppConfig):
    """La Recepción: lo que ve el cliente. Sin modelos propios — los accesos
    viven en la app raíz `portal/` y el negocio en las apps de El Taller."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.portal_cliente"
    label = "portal_cliente"
    verbose_name = "La Recepción (portal de clientes)"
