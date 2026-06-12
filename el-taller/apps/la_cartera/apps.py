from django.apps import AppConfig


class LaCarteraConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.la_cartera"
    label = "cartera"
    verbose_name = "La Cartera"

    def ready(self):
        # V6 Bloque 7A: correo de bienvenida al alta de cliente (best-effort,
        # gobernado por ConfiguracionCorreo.auto_bienvenida — arranca apagado).
        from django.db import transaction
        from django.db.models.signals import post_save

        from apps.la_cartera.models import Cliente

        def _bienvenida(sender, instance, created, **kwargs):
            if not created:
                return
            from lib.correos_auto import enviar_bienvenida
            transaction.on_commit(lambda: enviar_bienvenida(instance))

        # weak=False: la closure local moriría por GC con el default.
        post_save.connect(_bienvenida, sender=Cliente,
                          dispatch_uid="cartera_correo_bienvenida", weak=False)
