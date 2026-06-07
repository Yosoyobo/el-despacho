from django.db import models


class ClienteContacto(models.Model):
    """Persona de contacto de un Cliente (S-LC-Buzon). Un cliente puede tener
    varias. Los campos legacy `nombre_contacto/email_contacto/telefono` del
    Cliente se conservan y el contacto `principal` los espeja."""

    cliente = models.ForeignKey(
        "cartera.Cliente", on_delete=models.CASCADE, related_name="contactos",
    )
    nombre = models.CharField(max_length=200)
    puesto = models.CharField(max_length=120, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    telefono = models.CharField(max_length=40, blank=True, default="")
    principal = models.BooleanField(default=False)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cartera_cliente_contacto"
        ordering = ["-principal", "nombre"]
        verbose_name = "contacto de cliente"
        verbose_name_plural = "contactos de cliente"

    def __str__(self):
        return self.nombre
