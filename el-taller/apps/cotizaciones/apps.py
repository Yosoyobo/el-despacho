from django.apps import AppConfig


class CotizacionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cotizaciones"
    label = "cotizaciones"
    verbose_name = "Las Cotizaciones"

    def ready(self):
        from apps.cotizaciones.models.estado_cotizacion import (
            EstadoCotizacion,
            invalidar_cache_estados_cot,
        )
        from django.db.models.signals import post_delete, post_save

        def _invalidar(sender, **kwargs):
            invalidar_cache_estados_cot()

        # weak=False: igual que EstadoProyecto, evita que la señal muera al GC
        # la closure local al salir de ready().
        post_save.connect(_invalidar, sender=EstadoCotizacion, dispatch_uid="cotizaciones_estado_cache", weak=False)
        post_delete.connect(_invalidar, sender=EstadoCotizacion, dispatch_uid="cotizaciones_estado_cache_del", weak=False)
