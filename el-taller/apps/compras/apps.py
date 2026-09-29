from django.apps import AppConfig


class ComprasConfig(AppConfig):
    """Las órdenes de compra a proveedores (La Imprenta · Deploy 4, 2026-09-29).

    La UI vive en El Taller (Finanzas → Compras). La Gerencia la instala para
    correr su migración (§14 Bug B) y para previsualizar el documento.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.compras"
    label = "compras"
    verbose_name = "Compras (órdenes de compra)"
