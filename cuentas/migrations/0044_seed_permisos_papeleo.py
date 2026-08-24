"""Las llaves del archivo de papeleo.

Patrón de 0038/0039/0041/0043: `lib.permisos.puede()` NO tiene failsafe
automático para super_admin — depende de que exista la fila en PermisoUsuario.
Sin esta migración ni el dueño del sistema podría buscar en el archivo.

Sólo super_admin de arranque. El papeleo del despacho son contratos y
comprobantes: quién puede leerlos es una decisión de Oscar, no un default que
se le imponga. Se delega marcando las casillas en El Directorio, como todo lo
demás (§4 #20).

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion`. Escribirlo mal no truena en los tests —las migraciones corren sobre
una base sin usuarios, así que el bucle no itera— pero tumba el arranque en
producción, donde sí hay super admins. Ya pasó el 2026-08-22.
"""

from django.db import migrations

MODULO = "papeleo"
PERMISOS = ("ver", "ligar", "subir")


def _sumar_al_rol(Rol, filtro: dict, permisos) -> None:
    rol = Rol.objects.filter(**filtro).first()
    if rol is None:
        return
    mapa = dict(rol.permisos or {})
    acciones = set(mapa.get(MODULO) or [])
    acciones.update(permisos)
    mapa[MODULO] = sorted(acciones)
    rol.permisos = mapa
    rol.save(update_fields=["permisos"])


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    for usuario in Usuario.objects.filter(rol="super_admin"):
        for permiso in PERMISOS:
            Permiso.objects.update_or_create(
                usuario=usuario, modulo=MODULO, permiso=permiso,
                defaults={"activo": True},
            )

    _sumar_al_rol(Rol, {"clave": "super_admin"}, PERMISOS)


def quitar(apps, schema_editor):
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Permiso.objects.filter(modulo=MODULO).delete()
    Rol = apps.get_model("cuentas", "Rol")
    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        if MODULO in mapa:
            mapa.pop(MODULO)
            rol.permisos = mapa
            rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0043_seed_permisos_rutas"),
    ]

    operations = [migrations.RunPython(sembrar, quitar)]
