from django.apps import AppConfig


class LosProyectosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.los_proyectos"
    label = "proyectos"
    verbose_name = "Proyectos"

    def ready(self):
        from apps.los_proyectos import signals_egresos  # noqa: F401
        from apps.los_proyectos.models.estado import EstadoProyecto
        from apps.los_proyectos.templatetags.proyectos_extras import (
            invalidar_mapa_estados,
        )
        from django.db.models.signals import post_delete, post_save

        def _invalidar(sender, **kwargs):
            invalidar_mapa_estados()

        # weak=False (fix V6): con el default (weak=True) la closure local se
        # garbage-collectea al salir de ready() y la señal muere en silencio —
        # el cache de 60s disimulaba el bug en prod.
        post_save.connect(_invalidar, sender=EstadoProyecto, dispatch_uid="proyectos_estado_cache", weak=False)
        post_delete.connect(_invalidar, sender=EstadoProyecto, dispatch_uid="proyectos_estado_cache_del", weak=False)
