from django.apps import AppConfig


class ElPizarronConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.el_pizarron"
    label = "pizarron"
    verbose_name = "El Pizarrón"

    def ready(self):
        # Invalidación del cache de estados de tarea al editarlos desde
        # Gerencia (espejo del patrón de los_proyectos.apps).
        from apps.el_pizarron.models.estado_tarea import (
            EstadoTarea,
            invalidar_mapa_estados_tarea,
        )
        from django.db.models.signals import post_delete, post_save

        def _invalidar(sender, **kwargs):
            invalidar_mapa_estados_tarea()

        # weak=False: con el default (weak=True) la closure local se
        # garbage-collectea al salir de ready() y la señal muere en silencio.
        post_save.connect(_invalidar, sender=EstadoTarea, dispatch_uid="pizarron_estado_cache", weak=False)
        post_delete.connect(_invalidar, sender=EstadoTarea, dispatch_uid="pizarron_estado_cache_del", weak=False)
