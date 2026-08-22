"""Las llaves del planeador de rutas.

Patrón de 0038/0039/0041: `lib.permisos.puede()` NO tiene failsafe automático
para super_admin — depende de que exista la fila en PermisoUsuario. Sin esta
migración ni el dueño del sistema podría abrir el planeador.

Al **rol «Runner»** se le da sólo `ver`: un runner necesita abrir SU ruta, no
rearmar el reparto de todos ni despachar (que es lo que dispara el correo). El
resto del equipo lo recibe desde El Directorio marcando las casillas.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion`. Escribirlo mal no truena en los tests —las migraciones corren sobre
una base sin usuarios, así que el bucle no itera— pero tumba el arranque en
producción, donde sí hay super admins. Ya pasó el 2026-08-22.

**Colisión conocida de numeración**: el sprint de La Limpieza (en vuelo, sin
commitear) también toma un `0042`. Cuando las dos ramas se junten, Django va a
ver dos hojas y hay que renombrar una o generar la migración de merge — es de un
solo archivo.
"""

from django.db import migrations

MODULO = "rutas"
PERMISOS = ("ver", "planear", "despachar")
#: Lo único que recibe el rol Runner: consultar. No planear, no despachar.
PERMISOS_RUNNER = ("ver",)


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
    # El rol Runner por su clave estable; se cae al nombre por si viene de una
    # base anterior al backfill de 0034.
    if not Rol.objects.filter(clave="runner").exists():
        _sumar_al_rol(Rol, {"nombre": "Runner"}, PERMISOS_RUNNER)
    else:
        _sumar_al_rol(Rol, {"clave": "runner"}, PERMISOS_RUNNER)


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
        ("cuentas", "0041_seed_permiso_analisis"),
    ]

    operations = [migrations.RunPython(sembrar, quitar)]
