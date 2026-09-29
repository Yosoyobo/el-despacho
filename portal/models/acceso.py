"""AccesoCliente — una persona de un cliente que puede entrar a La Recepción.

**No es un `Usuario`.** Los clientes no comparten tabla, sesión ni cookie con el
equipo: su sesión es la de La Recepción (`recepcion_session`) y lo único que
guarda es el id de esta fila y su `generacion`. Así ningún camino del staff
(permisos, El Directorio, el login con contraseña) puede abrirle nada a un
cliente por accidente, y viceversa.

**Todo lo de su empresa.** Decisión de Oscar (2026-09-29): cualquier contacto
invitado ve todos los proyectos, cotizaciones y facturas de SU cliente — y nada
de otro. Por eso el acceso cuelga del `cliente`, y el `contacto` es sólo de
quién se trata.

**Revocar cierra la sesión viva.** Cada sesión recuerda la `generacion` con la
que entró; revocar (y reactivar) la sube, así que una sesión abierta antes deja
de valer en la siguiente petición aunque su cookie siga en el navegador.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AccesoCliente(models.Model):
    cliente = models.ForeignKey(
        "cartera.Cliente", on_delete=models.CASCADE, related_name="accesos_portal",
    )
    # De quién se trata. Puede ser nulo: el correo puede venir del campo
    # `Cliente.email_contacto` (el contacto «de siempre») o el contacto se borró
    # después; el acceso sigue siendo de su empresa.
    contacto = models.ForeignKey(
        "cartera.ClienteContacto", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="accesos_portal",
    )
    # Siempre en minúsculas (lo hace `save`): es la llave con la que la persona
    # pide su enlace y con la que se compara el correo de Google.
    email = models.EmailField(max_length=254, db_index=True)
    nombre = models.CharField(max_length=200, blank=True, default="")
    activo = models.BooleanField(default=True, db_index=True)
    generacion = models.PositiveIntegerField(default=1)

    invitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="accesos_portal_invitados",
    )
    invitado_en = models.DateTimeField(default=timezone.now)
    revocado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="accesos_portal_revocados",
    )
    revocado_en = models.DateTimeField(null=True, blank=True)
    ultima_entrada_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_acceso_cliente"
        verbose_name = "acceso al portal"
        verbose_name_plural = "accesos al portal"
        ordering = ["cliente_id", "nombre", "email"]
        constraints = [
            # Re-invitar a alguien reactiva SU fila; no se apilan duplicados.
            models.UniqueConstraint(fields=["cliente", "email"],
                                    name="portal_acceso_cliente_email_unico"),
            # Un correo abre UN cliente a la vez: al pedir su enlace sólo da su
            # correo, así que dos accesos vivos con el mismo serían ambiguos.
            models.UniqueConstraint(fields=["email"], condition=Q(activo=True),
                                    name="portal_acceso_email_activo_unico"),
        ]

    def __str__(self) -> str:
        return f"{self.nombre or self.email} · {self.cliente_id}"

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    @property
    def nombre_visible(self) -> str:
        return (self.nombre or "").strip() or self.email
