"""Le da a los super admins la llave de El Análisis.

Patrón de 0038/0039: `lib.permisos.puede()` no tiene failsafe automático para
super_admin — depende de que exista la fila en PermisoUsuario. Sin esta
migración, ni el dueño del sistema podría abrir la pantalla.

El resto del equipo lo recibe desde El Directorio, marcando la casilla
`analisis / ver`. Se deja así a propósito: la pantalla enseña el dinero de todo
el despacho.
"""

from django.db import migrations

MODULO = "analisis"
ACCION = "ver"


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    for usuario in Usuario.objects.filter(rol="super_admin"):
        Permiso.objects.update_or_create(
            usuario=usuario, modulo=MODULO, accion=ACCION,
            defaults={"activo": True},
        )
    # También al rol "super_admin", para quien lo tenga como rol extra.
    rol = Rol.objects.filter(clave="super_admin").first()
    if rol:
        permisos = dict(rol.permisos or {})
        acciones = set(permisos.get(MODULO) or [])
        acciones.add(ACCION)
        permisos[MODULO] = sorted(acciones)
        rol.permisos = permisos
        rol.save(update_fields=["permisos"])


def quitar(apps, schema_editor):
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Permiso.objects.filter(modulo=MODULO, accion=ACCION).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0040_intento_acceso"),
    ]

    operations = [migrations.RunPython(sembrar, quitar)]
