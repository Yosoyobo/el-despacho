from django.conf import settings
from django.db import models

ESTADOS_CLIENTE = (
    ("prospecto", "Prospecto"),
    ("activo", "Activo"),
    ("inactivo", "Inactivo"),
)


class ClienteActivosManager(models.Manager):
    """Por default oculta clientes con activo=False (soft delete)."""

    def get_queryset(self):
        return super().get_queryset().filter(activo=True)


class Cliente(models.Model):
    razon_social = models.CharField(max_length=200, db_index=True)
    # Slug para el Sistema de Referencias ($). Auto-generado en save().
    slug = models.CharField(max_length=80, unique=True)
    rfc = models.CharField(max_length=13, blank=True, default="", db_index=True)
    nombre_contacto = models.CharField(max_length=200, blank=True, default="")
    email_contacto = models.EmailField(blank=True, default="")
    telefono = models.CharField(max_length=40, blank=True, default="")
    direccion = models.TextField(blank=True, default="")
    # Dirección fiscal: si `fiscal_igual`, coincide con `direccion`; si no, se
    # captura en `direccion_fiscal` (S-Cliente-Ubicacion).
    direccion_fiscal = models.TextField(blank=True, default="")
    fiscal_igual = models.BooleanField(
        default=True, help_text="La dirección fiscal es la misma que la dirección.",
    )
    # Ubicación del cliente (S-Geo-Picker): el pin del mini-mapa de su dirección.
    # Alimenta el mapeo y la asignación de runner por cercanía (cero costo, OSM).
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    notas = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=20, choices=ESTADOS_CLIENTE, default="prospecto", db_index=True)

    activo = models.BooleanField(default=True, db_index=True)  # soft delete

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clientes_creados",
    )

    objects = models.Manager()        # acceso completo (admin, queries explícitas)
    activos = ClienteActivosManager()  # listas/selectores del UI

    class Meta:
        db_table = "cartera_cliente"
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ["razon_social"]
        constraints = [
            models.UniqueConstraint(
                fields=["rfc"],
                condition=~models.Q(rfc=""),
                name="cartera_cliente_rfc_unique_nonempty",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            from lib.slug import generar_slug_cliente
            self.slug = generar_slug_cliente(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.razon_social

    @property
    def contacto_principal(self):
        """Contacto marcado principal, o el primero; None si no hay ninguno."""
        contactos = list(self.contactos.all())
        for c in contactos:
            if c.principal:
                return c
        return contactos[0] if contactos else None
