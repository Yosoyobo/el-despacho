from django.apps import AppConfig


class ImprentaConfig(AppConfig):
    """Los ajustes de los documentos PDF y su historial.

    Las plantillas de los documentos viven en `imprenta/templates/` para que las
    vean los dos proyectos: El Taller las imprime y La Gerencia las enseña en la
    vista previa. Mismo nombre de plantilla que antes (`cotizaciones/pdf.html`),
    así que quien la llamaba no cambia.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "imprenta"
    label = "imprenta"
    verbose_name = "La Imprenta (documentos PDF)"
