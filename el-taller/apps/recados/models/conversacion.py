"""Modelo chat — sprint S-Recados-Chat.

`Conversacion` agrupa mensajes entre N participantes. `Mensaje` es cada
texto enviado. `MensajeLectura` registra hasta qué mensaje leyó cada
usuario en cada conversación (eficiente para counters de no leídos).

NO se migran los `Recado` históricos (decisión del usuario: "no agrupes,
de aquí en adelante"). La bandeja vieja sigue accesible como
`/recados/legacy/`.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Conversacion(models.Model):
    DIRECTA = "directa"
    GRUPO = "grupo"
    TIPOS = ((DIRECTA, "Directa"), (GRUPO, "Grupo"))

    tipo = models.CharField(max_length=10, choices=TIPOS, default=DIRECTA, db_index=True)
    nombre = models.CharField(max_length=120, blank=True, default="")  # solo grupos
    creada_en = models.DateTimeField(auto_now_add=True)
    ultima_actividad = models.DateTimeField(auto_now_add=True, db_index=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, related_name="conversaciones_creadas",
    )
    participantes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="conversaciones",
    )
    # Clave normalizada para conversaciones 1:1 (par ordenado "minID:maxID");
    # unique para que no se dupliquen. NULL en grupos.
    clave_directa = models.CharField(max_length=40, blank=True, null=True, unique=True)

    class Meta:
        db_table = "recados_conversacion"
        ordering = ["-ultima_actividad"]

    def __str__(self) -> str:
        if self.tipo == self.GRUPO:
            return self.nombre or f"Grupo #{self.pk}"
        return f"Conversación #{self.pk}"

    @staticmethod
    def clave_para_par(uid_a: int, uid_b: int) -> str:
        a, b = sorted((int(uid_a), int(uid_b)))
        return f"{a}:{b}"


class Mensaje(models.Model):
    conversacion = models.ForeignKey(
        Conversacion, on_delete=models.CASCADE, related_name="mensajes",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="mensajes_chat",
    )
    cuerpo = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    editado_en = models.DateTimeField(null=True, blank=True)

    # Si el mensaje es una solicitud de corrección del Checador, apunta a ella
    # para renderizar botones Aprobar/Rechazar en la burbuja (S-Checador-V1.1).
    # FK por string para no acoplar recados↔checador en import-time.
    correccion = models.ForeignKey(
        "checador.SolicitudCorreccion",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="mensajes_chat",
    )

    class Meta:
        db_table = "recados_mensaje"
        ordering = ["creado_en"]
        indexes = [models.Index(fields=["conversacion", "creado_en"])]


class MensajeLectura(models.Model):
    """Un row por (usuario, conversación). `ultimo_mensaje_id` es el ID
    del último mensaje que el usuario marcó como leído. Para contar no
    leídos: `Mensaje.objects.filter(conversacion=c, id__gt=ultimo).count()`.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lecturas_chat",
    )
    conversacion = models.ForeignKey(
        Conversacion, on_delete=models.CASCADE, related_name="lecturas",
    )
    ultimo_mensaje = models.ForeignKey(
        Mensaje, on_delete=models.SET_NULL, null=True, blank=True,
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recados_mensaje_lectura"
        constraints = [
            models.UniqueConstraint(fields=["usuario", "conversacion"], name="uniq_lectura_user_conv"),
        ]
