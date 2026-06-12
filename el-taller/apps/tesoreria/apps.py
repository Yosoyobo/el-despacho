from django.apps import AppConfig


class TesoreriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tesoreria"
    label = "tesoreria"
    verbose_name = "La Tesorería"

    def ready(self):
        # V6 Bloque 7A: confirmación de pago al registrar un Ingreso con
        # cliente (best-effort, gobernado por ConfiguracionCorreo.auto_pago —
        # arranca apagado).
        from django.db import transaction
        from django.db.models.signals import post_save

        from apps.tesoreria.models.ingreso import Ingreso

        def _confirmar_pago(sender, instance, created, **kwargs):
            if not created or instance.anulado:
                return
            from lib.correos_auto import enviar_confirmacion_pago
            transaction.on_commit(lambda: enviar_confirmacion_pago(instance))

        # weak=False: la closure local moriría por GC con el default.
        post_save.connect(_confirmar_pago, sender=Ingreso,
                          dispatch_uid="tesoreria_correo_pago", weak=False)
