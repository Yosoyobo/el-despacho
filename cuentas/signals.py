"""Signals de cuentas.

`auto_seedear_permisos`: tras crear un Usuario, popula PermisoUsuario con los
defaults del rol. Idempotente — usa get_or_create por fila.

Los `_invalidar_permisos_*` descartan el memo de `lib.permisos.puede()` cuando
algo cambia los permisos, para que una petición que los muta y los relee no vea
los viejos.

`_presencia_al_entrar` / `_presencia_al_salir`: marcan la actividad del usuario
al iniciar y cerrar sesión (ver `lib.presencia`).
"""

from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_logged_out
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
        from lib.permisos_defaults import defaults_de
    except Exception:
        return
    # `defaults_de` = los del rol + los universales (los que TODO usuario trae
    # desde que nace, p. ej. ver quién está en línea). Así un `miembro` recién
    # dado de alta —que no tiene defaults de rol— también los recibe.
    para_rol = defaults_de(instance.rol)
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


# ── Presencia: entrar y salir también es actividad ──────────────────────────
#
# Entrar al sistema es la primera señal de que alguien está aquí, y salir es la
# única forma de saber que se fue ANTES de que pasen los 30 minutos. Los dos
# escriben en los campos `actividad_*` del usuario (ver `lib.presencia`). Nunca
# lanzan: la presencia jamás puede ser el motivo de que un login falle.


@receiver(user_logged_in, weak=False)
def _presencia_al_entrar(sender, request=None, user=None, **kwargs):
    from lib import presencia

    presencia.marcar_entrada(request, user)


@receiver(user_logged_out, weak=False)
def _presencia_al_salir(sender, request=None, user=None, **kwargs):
    from lib import presencia

    presencia.marcar_salida(request, user)
