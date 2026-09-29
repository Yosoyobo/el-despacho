"""EnlaceAcceso — el enlace de UN SOLO USO que abre la sesión de un cliente.

Sólo se guarda el **hash** (SHA-256) del token: quien lea la base —un respaldo,
un volcado para depurar— no puede entrar con lo que ve. El token en claro vive
únicamente en el correo que se le mandó a la persona.

Dos sabores, que sólo difieren en cuánto viven:

- **entrada** (lo pide la persona en La Recepción): 20 minutos. Es el caso del
  encargo — «expira pronto».
- **invitación** (la manda el despacho desde la ficha del cliente): 72 horas.
  Una invitación que caduca a la media hora la abre el cliente al día siguiente
  y ya no sirve; como es de un solo uso y la manda alguien del despacho a un
  correo que el despacho escogió, alargarla no abre nada nuevo. Si caduca, la
  pantalla ofrece pedir uno de entrada con el correo ya escrito.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

MOTIVO_ENTRADA = "entrada"
MOTIVO_INVITACION = "invitacion"
MOTIVOS = (
    (MOTIVO_ENTRADA, "Entrada pedida por la persona"),
    (MOTIVO_INVITACION, "Invitación del despacho"),
)


class EnlaceAcceso(models.Model):
    acceso = models.ForeignKey(
        "portal.AccesoCliente", on_delete=models.CASCADE, related_name="enlaces",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    motivo = models.CharField(max_length=12, choices=MOTIVOS, default=MOTIVO_ENTRADA)
    creado_en = models.DateTimeField(default=timezone.now)
    expira_en = models.DateTimeField()
    usado_en = models.DateTimeField(null=True, blank=True)
    ip_solicitud = models.CharField(max_length=64, blank=True, default="")
    ip_uso = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "portal_enlace_acceso"
        verbose_name = "enlace de acceso"
        verbose_name_plural = "enlaces de acceso"
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"enlace {self.pk} · acceso {self.acceso_id}"

    @property
    def vigente(self) -> bool:
        return self.usado_en is None and self.expira_en > timezone.now()
