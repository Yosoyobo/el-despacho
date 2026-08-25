"""Signals de cuentas.

`auto_seedear_permisos`: tras crear un Usuario, popula PermisoUsuario con los
defaults del rol. Idempotente — usa get_or_create por fila.

Los `_invalidar_permisos_*` descartan el memo de `lib.permisos.puede()` cuando
algo cambia los permisos, para que una petición que los muta y los relee no vea
los viejos.
"""

from __future__ import annotations

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models.permiso_usuario import PermisoUsuario
from .models.rol import Rol
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


# ── Invalidación del caché de permisos ───────────────────────────────────────
#
# `lib.permisos.puede()` memoiza el mapa de permisos en la instancia de Usuario
# de la petición en curso. Ese memo vive lo que dura la petición, así que la
# única ventana en la que podría mentir es una petición que MUTA permisos y
# vuelve a leerlos (el panel de El Directorio, un command de seed). Estos
# signals la cierran: cualquier escritura sube la versión y los memos viejos
# se descartan solos.
#
# `weak=False` no es adorno: sin él la closure la puede recoger el recolector
# de basura y el signal deja de dispararse EN SILENCIO (ver §14 y el fix de los
# estados de proyecto de V6).

@receiver([post_save, post_delete], sender=PermisoUsuario, weak=False)
def _invalidar_permisos_por_fila(sender, **kwargs):
    from lib.permisos import invalidar_cache_permisos

    invalidar_cache_permisos()


@receiver(post_save, sender=Rol, weak=False)
def _invalidar_permisos_por_rol(sender, **kwargs):
    from lib.permisos import invalidar_cache_permisos

    invalidar_cache_permisos()


@receiver(m2m_changed, sender=Usuario.roles_extra.through, weak=False)
def _invalidar_permisos_por_roles_extra(sender, **kwargs):
    from lib.permisos import invalidar_cache_permisos

    invalidar_cache_permisos()
