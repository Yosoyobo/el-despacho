from django.apps import AppConfig


class BuzonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "buzon"
    verbose_name = "El Buzón"

    def ready(self):
        # S-Buzon-Estados-V1: invalida el cache del mapa de estados al
        # guardar/borrar un EstadoBuzon (cambios desde Gerencia visibles ≤60s).
        from django.db.models.signals import post_delete, post_save

        from buzon.estados import invalidar_cache
        from buzon.models.estado import EstadoBuzon

        def _invalidar(sender, **kwargs):
            invalidar_cache()

        # weak=False: _invalidar es una clausura local; sin esto la weak-ref se
        # recolecta y el signal nunca dispara (el cache quedaría stale hasta el
        # TTL de 60s). Con weak=False el receptor vive con el AppConfig.
        post_save.connect(_invalidar, sender=EstadoBuzon, weak=False, dispatch_uid="buzon_estado_cache")
        post_delete.connect(_invalidar, sender=EstadoBuzon, weak=False, dispatch_uid="buzon_estado_cache_del")
