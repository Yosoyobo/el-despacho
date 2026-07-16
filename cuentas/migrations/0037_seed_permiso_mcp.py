"""Agrega `mcp.usar`, cerrado por default salvo para super_admin."""

from django.db import migrations


def sembrar_permiso_mcp(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    # Conserva alineado el rol de sistema para usuarios que heredan permisos
    # por `roles_extra`, además del override individual sembrado abajo.
    for rol in Rol.objects.filter(clave="super_admin"):
        permisos = dict(rol.permisos or {})
        acciones = set(permisos.get("mcp") or [])
        acciones.add("usar")
        permisos["mcp"] = sorted(acciones)
        rol.permisos = permisos
        rol.save(update_fields=["permisos"])

    for usuario in Usuario.objects.filter(rol="super_admin", is_active=True):
        PermisoUsuario.objects.update_or_create(
            usuario=usuario,
            modulo="mcp",
            permiso="usar",
            defaults={"activo": True},
        )


def revertir_permiso_mcp(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")
    PermisoUsuario.objects.filter(modulo="mcp", permiso="usar").delete()
    for rol in Rol.objects.filter(clave="super_admin"):
        permisos = dict(rol.permisos or {})
        permisos.pop("mcp", None)
        rol.permisos = permisos
        rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0036_seed_permiso_catalogo_eliminar")]
    operations = [migrations.RunPython(sembrar_permiso_mcp, revertir_permiso_mcp)]
