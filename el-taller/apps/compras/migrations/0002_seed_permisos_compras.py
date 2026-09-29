"""Las llaves de Compras — sólo datos (Bug I: el esquema quedó en 0001).

«Como hoy» (§4 #20): una orden de compra enseña precios de proveedor —dinero—,
así que el permiso `compras` nace para quien HOY ve el dinero del despacho
(`tesoreria.ver` efectivo: fila encendida o rol asignado) y para todo
super_admin. Nadie más; el resto se delega desde El Directorio.

Dos pasos (el patrón de `checador/0010`): el JSON de los roles que ya traen
`tesoreria.ver` (y el de super_admin), y una fila por persona que califica. Una
fila de `compras` que ya exista no se pisa.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO `accion`.
"""

from django.db import migrations

MODULO = "compras"
TODO = ("ver", "crear", "editar", "cancelar")


def _ve_tesoreria(Permiso, usuario) -> bool:
    fila = Permiso.objects.filter(usuario=usuario, modulo="tesoreria", permiso="ver").first()
    if fila is not None:
        return bool(fila.activo)
    return any("ver" in ((r.permisos or {}).get("tesoreria") or []) for r in usuario.roles_extra.all())


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        if rol.clave != "super_admin" and "ver" not in (mapa.get("tesoreria") or []):
            continue
        actuales = set(mapa.get(MODULO) or [])
        if set(TODO) <= actuales:
            continue
        mapa[MODULO] = sorted(actuales | set(TODO))
        rol.permisos = mapa
        rol.save(update_fields=["permisos"])

    for usuario in Usuario.objects.all():
        roles = {usuario.rol} if usuario.rol else set()
        roles.update(usuario.roles_extra.values_list("clave", flat=True))
        if "super_admin" not in roles and not _ve_tesoreria(Permiso, usuario):
            continue
        for accion in TODO:
            Permiso.objects.get_or_create(
                usuario=usuario, modulo=MODULO, permiso=accion, defaults={"activo": True})


def quitar(apps, schema_editor):
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")
    Permiso.objects.filter(modulo=MODULO).delete()
    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        if MODULO in mapa:
            mapa.pop(MODULO)
            rol.permisos = mapa
            rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):
    dependencies = [
        ("compras", "0001_initial"),
        ("cuentas", "0054_seed_permiso_kpis"),
    ]
    operations = [migrations.RunPython(sembrar, quitar)]
