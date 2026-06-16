"""S-LC-Feedback-V5 c7 — Roles personalizados (encima del campo `rol` primario).

`Usuario.rol` (CharField legacy) queda intacto como rol PRIMARIO y los
checks literales `if user.rol == 'super_admin'` siguen funcionando.
Los `Rol` extras se suman vía M2M `Usuario.roles_extra` y aportan más
permisos a la unión efectiva.

Permisos efectivos del usuario =
    DEFAULTS_POR_ROL[user.rol]
  + UNION(rol.permisos for rol in user.roles_extra.all())
  + PermisoUsuario filas activas
  - PermisoUsuario filas con activo=False (overrides individuales)

`Rol.permisos` es un dict JSON `{"modulo": ["accion1", "accion2"]}` para
mantener la edición simple — no abrimos una tabla M2M intermedia. Los
4 roles "sistema" (super_admin, dueno, contador, disenador) se siembran
en la migración con los mismos permisos de `lib/permisos_defaults.py`.
Esos roles tienen `sistema=True` y NO se pueden borrar (sólo editar
super_admin/dueno).
"""

from __future__ import annotations

from django.db import models


class Rol(models.Model):
    # `clave` es la IDENTIDAD ESTABLE e interna del rol (oculta del GUI). Todo el
    # sistema de permisos identifica roles por la clave —
    # `lib.permisos.tiene_rol(user, "super_admin")`, `usuarios_con_rol("dueno")`,
    # `sincronizar_rol_primario` filtra `clave="super_admin"`, etc. NUNCA cambia
    # tras crearse, así que el usuario puede renombrar `nombre` libremente sin
    # romper ningún check. Claves de sistema: super_admin/dueno/contador/disenador.
    clave = models.SlugField(max_length=60, unique=True, editable=False)
    # `nombre` es la ETIQUETA visible y EDITABLE por el usuario en La Gerencia.
    nombre = models.CharField(max_length=60, unique=True, db_index=True)
    descripcion = models.CharField(max_length=200, blank=True, default="")
    permisos = models.JSONField(default=dict, blank=True)
    # `sistema` solo marca roles protegidos de borrado (super_admin failsafe). No
    # se muestra como etiqueta en el GUI (decisión Oscar S-Mandados-V2).
    sistema = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cuentas_rol"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre

    @property
    def protegido(self) -> bool:
        """Solo el super_admin es failsafe duro y no se puede borrar."""
        return self.clave == "super_admin"

    def tiene_permiso(self, modulo: str, accion: str) -> bool:
        return accion in (self.permisos.get(modulo) or [])
