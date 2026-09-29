"""EnlaceAcceso — la llave personal con la que un cliente entra a La Recepción.

**No caduca y no se gasta** (decisión de Oscar, 2026-09-29: «los links expiran
una vez que entras, debemos hacer que no expiren; siempre pide el correo al que
se envió el registro y que picar el botón te lleve»). Hasta esa fecha el enlace
servía una sola vez y vencía en minutos u horas; el cliente guardaba el correo,
volvía otro día y el botón ya no abría nada.

Lo que ahora protege la llave:

- **El correo.** Abrir el enlace no basta: la pantalla pide el correo al que se
  mandó y sólo abre si coincide. Un enlace reenviado, pegado en un chat o que
  un filtro de correo abrió no entra solo. Con rate-limit por enlace y por IP.
- **Una viva por persona.** Cambiarla (desde la ficha del cliente) anula la
  anterior (`anulado_en`). Revocar el acceso las anula todas y además corta la
  sesión abierta (ver `AccesoCliente.generacion`).

Se guarda el **hash** (SHA-256) para buscarla y una copia **cifrada con La
Bóveda** para poder reenviar LA MISMA llave («Reenviar su enlace», «Copiar
enlace», «pedir mi enlace» en La Recepción). Quien lea un respaldo de la base
sin la llave maestra no puede entrar con lo que ve. Las llaves de antes de este
cambio sólo tienen el hash: se cifran la primera vez que alguien entra con ellas
(el token viaja en esa petición).

`expira_en` queda por compatibilidad: vacío = no caduca, que es lo que se crea
hoy. `usado_en` es la PRIMERA entrada y `ultimo_uso_en` la más reciente.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

MOTIVO_ENTRADA = "entrada"
MOTIVO_INVITACION = "invitacion"
MOTIVOS = (
    (MOTIVO_ENTRADA, "Pedido por la persona"),
    (MOTIVO_INVITACION, "Invitación del despacho"),
)


class EnlaceAcceso(models.Model):
    acceso = models.ForeignKey(
        "portal.AccesoCliente", on_delete=models.CASCADE, related_name="enlaces",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    # La Bóveda (AES-256-GCM). Vacío en las llaves de antes de 2026-09-29.
    token_cifrado = models.TextField(blank=True, default="")
    motivo = models.CharField(max_length=12, choices=MOTIVOS, default=MOTIVO_ENTRADA)
    creado_en = models.DateTimeField(default=timezone.now)
    # Vacío = no caduca (todas las de hoy en adelante).
    expira_en = models.DateTimeField(null=True, blank=True)
    # Se cambió por otra o se revocó el acceso: ya no abre.
    anulado_en = models.DateTimeField(null=True, blank=True)
    usado_en = models.DateTimeField(null=True, blank=True)
    ultimo_uso_en = models.DateTimeField(null=True, blank=True)
    usos = models.PositiveIntegerField(default=0)
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
        if self.anulado_en is not None:
            return False
        return self.expira_en is None or self.expira_en > timezone.now()
