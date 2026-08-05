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

        # LC 2026-07-26: los ALIAS de producto («¿cómo se llama aquí?») viajan en
        # el `data-buscar` de los combobox y salen de un mapa cacheado. Sin esta
        # invalidación, un alias nuevo tardaba hasta un minuto en ser buscable.
        # Mismo `weak=False` de arriba, por la misma razón.
        from apps.el_catalogo.widgets import invalidar_mapa_alias
        from apps.los_proyectos.models import ProyectoProducto

        def _invalidar_alias(sender, **kwargs):
            invalidar_mapa_alias()

        post_save.connect(_invalidar_alias, sender=ProyectoProducto,
                          dispatch_uid="proyectos_alias_cache", weak=False)
        post_delete.connect(_invalidar_alias, sender=ProyectoProducto,
                            dispatch_uid="proyectos_alias_cache_del", weak=False)

        # LC 2026-08-04: el proveedor que se le pone a la línea de un proyecto se
        # liga al producto del catálogo (sin mover al principal). Ver
        # signals_catalogo. `weak=False`: la función es de módulo, pero se
        # mantiene el patrón del archivo para que nadie lo cambie sin pensarlo.
        from apps.los_proyectos.signals_catalogo import (
            vincular_proveedor_al_catalogo,
        )

        post_save.connect(vincular_proveedor_al_catalogo, sender=ProyectoProducto,
                          dispatch_uid="proyectos_vincula_proveedor", weak=False)
