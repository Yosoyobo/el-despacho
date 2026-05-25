from django.apps import AppConfig


class LosProyectosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.los_proyectos"
    label = "proyectos"
    verbose_name = "Proyectos"

    def ready(self):
        from apps.los_proyectos.models.estado import EstadoProyecto
        from apps.los_proyectos.templatetags.proyectos_extras import (
            invalidar_mapa_estados,
        )
        from django.db.models.signals import post_delete, post_save

        def _invalidar(sender, **kwargs):
            invalidar_mapa_estados()

        post_save.connect(_invalidar, sender=EstadoProyecto, dispatch_uid="proyectos_estado_cache")
        post_delete.connect(_invalidar, sender=EstadoProyecto, dispatch_uid="proyectos_estado_cache_del")
