"""ConfiguracionCorreo — proveedor de correo activo de El Cartero.

Singleton (una sola fila, `id=1`): elige por qué CANAL sale el correo que El
Cartero compone. El Cartero arma asunto/cuerpo/adjunto y decide; el canal solo
entrega:

- `smtp`  → Django EmailMessage con conexión armada al vuelo desde La Bóveda
            (slots `smtp_*`).
- `n8n`   → evento Portavoz `correo.solicitado` con el correo ya armado; el
            workflow de n8n solo lo manda por su proveedor.

Las credenciales (host SMTP, contraseña, webhook de n8n…) viven cifradas en La
Bóveda. Aquí solo se persiste la ELECCIÓN del canal + auditoría.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

PROVEEDORES_CORREO = (
    ("n8n", "n8n (vía El Portavoz)"),
    ("smtp", "SMTP directo"),
)


class ConfiguracionCorreo(models.Model):
    # Singleton: siempre id=1 (ver obtener()).
    proveedor = models.CharField(
        max_length=10, choices=PROVEEDORES_CORREO, default="n8n",
    )
    remitente_nombre = models.CharField(
        max_length=120, blank=True, default="Learning Center",
        help_text="Nombre visible del remitente (ej. «Learning Center»).",
    )
    # LC 2026-08-23 (Oscar): «el correo salió de hola@ y no de chalán@».
    # Cuando el correo lo dispara El Chalán y la plantilla no declara alias
    # propio, sale de esta dirección. Va aquí —y no escrito en el código—
    # porque la regla del proyecto es que lo configurable vive en un GUI de
    # La Gerencia: Ajustes → El Cartero.
    #
    # NO le gana al alias de la plantilla: una cotización sigue saliendo de
    # cotizaciones@ aunque la mande El Chalán. El Chalán es el medio, no el
    # remitente; esto sólo cubre el hueco de la plantilla que no dice nada.
    remitente_chalan = models.EmailField(
        blank=True, default="",
        help_text="Dirección desde la que salen los correos que manda El Chalán "
                  "cuando la plantilla no trae una propia. Vacío = el remitente general.",
    )
    # V6 Bloque 7A — correos automáticos. ARRANCAN APAGADOS (mismo criterio
    # que La Cobranza) para no sorprender a los clientes.
    auto_bienvenida = models.BooleanField(
        default=False,
        help_text="Enviar correo de bienvenida al dar de alta un cliente con email.",
    )
    auto_pago = models.BooleanField(
        default=False,
        help_text="Enviar confirmación de pago al registrar un ingreso con cliente.",
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="config_correo_actualizadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_configuracion_correo"
        verbose_name = "configuración de correo"
        verbose_name_plural = "configuración de correo"

    def __str__(self) -> str:
        return f"ConfiguracionCorreo(proveedor={self.proveedor})"

    @classmethod
    def obtener(cls) -> ConfiguracionCorreo:
        """Devuelve la fila singleton, creándola con defaults si no existe."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
