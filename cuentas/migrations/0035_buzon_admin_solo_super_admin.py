"""El Buzón de soporte (`buzon.ver_todos`) = SOLO super_admin (decisión Oscar).

El acceso a la bandeja de TODOS los mensajes (item "Buzón" del sidebar + la
vista admin en La Gerencia) se gatea por el permiso granular `(buzon, ver_todos)`.
Hasta ahora el `dueno` también lo recibía por default; esta migración alinea los
datos existentes para que SOLO el super_admin lo tenga, sin perder el carácter
granular: el super_admin puede volver a delegarlo a quien quiera desde
`/directorio/<id>/permisos/` o vía un rol personalizado.

Qué hace (idempotente):
  1. Quita "ver_todos" del módulo "buzon" en TODO rol personalizado que NO sea
     el rol super_admin (incluye el rol legacy "dueno" sembrado en 0014/0024).
  2. Borra las filas `PermisoUsuario(buzon, ver_todos)` de cualquier usuario que
     NO sea super_admin (primario o vía roles_extra). El super_admin conserva la
     suya (sembrada por el signal `auto_seedear_permisos`).
"""

from __future__ import annotations

from django.db import migrations


def buzon_solo_super_admin(apps, schema_editor):
    Rol = apps.get_model("cuentas", "Rol")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Usuario = apps.get_model("cuentas", "Usuario")

    # 1) Roles personalizados: quitar "ver_todos" del buzón salvo el rol super_admin.
    for rol in Rol.objects.exclude(clave="super_admin"):
        acciones = (rol.permisos or {}).get("buzon") or []
        if "ver_todos" in acciones:
            rol.permisos["buzon"] = [a for a in acciones if a != "ver_todos"]
            rol.save(update_fields=["permisos"])

    # 2) PermisoUsuario individuales: conservar solo a los super_admin (primario
    #    o vía un rol extra con clave="super_admin"); borrar al resto.
    sa_ids = set(Usuario.objects.filter(rol="super_admin").values_list("id", flat=True))
    sa_ids |= set(
        Usuario.objects.filter(roles_extra__clave="super_admin").values_list("id", flat=True)
    )
    (
        PermisoUsuario.objects.filter(modulo="buzon", permiso="ver_todos")
        .exclude(usuario_id__in=sa_ids)
        .delete()
    )


def noop(apps, schema_editor):
    # No revertimos: re-conceder ver_todos a un rol/usuario es trabajo del
    # super_admin desde la UI de permisos (granular).
    pass


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0034_rol_clave")]
    operations = [migrations.RunPython(buzon_solo_super_admin, noop)]
