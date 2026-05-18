"""Signals de cuentas.

`auto_seedear_permisos`: tras crear un Usuario, popula PermisoUsuario con los
defaults del rol. Idempotente — usa get_or_create por fila.
"""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models.permiso_usuario import PermisoUsuario
from .models.usuario import Usuario


@receiver(post_save, sender=Usuario)
def auto_seedear_permisos(sender, instance: Usuario, created: bool, **kwargs):
    if not created:
        return
    try:
        from lib.permisos_defaults import DEFAULTS_POR_ROL
    except Exception:
        return
    para_rol = DEFAULTS_POR_ROL.get(instance.rol, {})
    for modulo, permisos in para_rol.items():
        for permiso in permisos:
            PermisoUsuario.objects.get_or_create(
                usuario=instance, modulo=modulo, permiso=permiso,
                defaults={"activo": True},
            )
