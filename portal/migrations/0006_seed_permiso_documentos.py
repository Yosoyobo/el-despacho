"""La llave `recepcion.documentos`: ver, subir y revisar la papelería del cliente.

Sólo datos, sin esquema (§14 Bug I). Idempotente. «Como hoy»: la recibe quien ya
ve los accesos del portal (`recepcion.ver` efectivo) — el mismo equipo que ya
atiende al cliente en la ficha. Mismo patrón de dos pasos que `portal/0002`:
roles (JSON) y una fila ENCENDIDA por persona, porque la grilla de El Directorio
muestra fila o default del rol primario y guardarla apagaría lo que sólo viniera
del rol. `lib.permisos.puede()` NO tiene failsafe de super_admin: se le siembra.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`.
"""

from __future__ import annotations

from django.db import migrations

MODULO = "recepcion"
ACCION = "documentos"
LLAVE = ("recepcion", "ver")


def _rol_trae(rol, modulo: str, accion: str) -> bool:
    return accion in ((rol.permisos or {}).get(modulo) or [])


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    for rol in Rol.objects.all():
        if rol.clave == "super_admin" or _rol_trae(rol, *LLAVE):
            mapa = dict(rol.permisos or {})
            acciones = set(mapa.get(MODULO) or [])
            if ACCION not in acciones:
                acciones.add(ACCION)
                mapa[MODULO] = sorted(acciones)
                rol.permisos = mapa
                rol.save(update_fields=["permisos"])

    for u in Usuario.objects.filter(is_active=True).prefetch_related("roles_extra"):
        extras = list(u.roles_extra.all())
        es_super = u.rol == "super_admin" or any(r.clave == "super_admin" for r in extras)
        if Permiso.objects.filter(usuario=u, modulo=MODULO, permiso=ACCION).exists():
            continue  # ya decidido (a mano o en una corrida anterior): se respeta
        fila = Permiso.objects.filter(usuario=u, modulo=LLAVE[0], permiso=LLAVE[1]).first()
        tiene = es_super or (fila is not None and fila.activo) or (
            fila is None and any(_rol_trae(r, *LLAVE) for r in extras))
        if tiene:
            Permiso.objects.create(usuario=u, modulo=MODULO, permiso=ACCION, activo=True)


def quitar(apps, schema_editor):
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")
    Permiso.objects.filter(modulo=MODULO, permiso=ACCION).delete()
    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        if ACCION in (mapa.get(MODULO) or []):
            mapa[MODULO] = [a for a in mapa[MODULO] if a != ACCION]
            rol.permisos = mapa
            rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0005_revivir_ultima_llave"),
        ("cuentas", "0051_seed_permiso_contaduria_cargar"),
    ]

    operations = [migrations.RunPython(sembrar, quitar)]
