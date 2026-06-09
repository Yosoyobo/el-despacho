"""LecturaBuzon — estado de lectura POR USUARIO (S-Chalanes-UX #3).

El Buzón se siente como email: el "no leído" es de cada quien, no global del
despacho. El `estado` del mensaje (nuevo/leido/respondido/archivado) sigue
siendo el flujo de atención del equipo; esta tabla es independiente y marca
qué mensajes ya abrió/leyó cada usuario.

- Hay fila → el usuario YA leyó el mensaje.
- No hay fila → no leído para ese usuario.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class LecturaBuzon(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lecturas_buzon")
    mensaje = models.ForeignKey(
        "buzon.MensajeBuzon", on_delete=models.CASCADE, related_name="lecturas")
    leido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "buzon_lectura"
        unique_together = ("usuario", "mensaje")
        indexes = [models.Index(fields=["usuario", "mensaje"])]

    def __str__(self):
        return f"Lectura(u={self.usuario_id}, m={self.mensaje_id})"
