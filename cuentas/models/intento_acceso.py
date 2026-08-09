"""Bitácora de intentos de acceso — **cada** intento, no solo los buenos.

Es lo que contesta *«¿se está usando esto, y quién?»* en el desglose de `/salud`
(`uso.ingresos` / `uso.fallidos`) y lo que distingue «lo usa una persona» de
«alguien está probando contraseñas»: un día con treinta fallidos y dos entradas
significa algo muy distinto de treinta entradas.

Se escribe desde los tres caminos de entrada (login de El Taller, login de La
Gerencia y el SSO de Google) vía `lib.auditoria_acceso.registrar`, que **nunca
lanza**: la bitácora no puede ser el motivo de que alguien no pueda entrar.

**Privacidad.** Se guardan dirección y navegador porque sin ellos no se puede
distinguir un usuario de un ataque, pero **no salen de esta tabla**: a `/salud`
solo viajan conteos, y no hay pantalla que los muestre. (Es la misma razón por la
que El Colador redacta direcciones IP en los reportes de error, que sí se leen en
la UI — ahí el dato no aporta y aquí es el dato.)
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

# Por qué falló (o no) el intento. `ok` es el único que significa que entró.
MOTIVOS = (
    ("ok", "Entró"),
    ("credenciales", "Credenciales inválidas"),
    ("faltan_datos", "Faltó email o contraseña"),
    ("sin_permiso", "Sin permiso para esta app"),
    ("limite", "Frenado por el límite de intentos"),
    ("sso", "Falló el acceso con Google"),
)

VIAS = (("password", "Email y contraseña"), ("google", "Google"))

APPS = (("taller", "El Taller"), ("gerencia", "La Gerencia"), ("recepcion", "La Recepción"))


class IntentoAcceso(models.Model):
    app = models.CharField(max_length=20, choices=APPS)
    via = models.CharField(max_length=20, choices=VIAS, default="password")
    # Lo que se escribió: puede no corresponder a ninguna cuenta (y eso es
    # justamente lo interesante cuando alguien está tanteando).
    email_intentado = models.CharField(max_length=254, blank=True, default="")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intentos_acceso",
    )
    exito = models.BooleanField(default=False)
    motivo = models.CharField(max_length=20, choices=MOTIVOS, default="credenciales")
    ip = models.CharField(max_length=64, blank=True, default="")
    agente = models.CharField(max_length=300, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "cuentas_intento_acceso"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["exito", "creado_en"], name="idx_intento_exito_fecha")]
        verbose_name = "intento de acceso"
        verbose_name_plural = "intentos de acceso"

    def __str__(self) -> str:
        marca = "ok" if self.exito else self.motivo
        return f"{self.app}:{self.email_intentado or '?'}:{marca}"
