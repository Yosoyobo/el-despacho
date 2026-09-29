"""Las llaves de La Recepción: `recepcion.ver`, `recepcion.invitar`, `recepcion.revocar`.

Sólo datos, sin esquema (§14 Bug I). Idempotente. Vive en `portal/` y no en
`cuentas/` por el contrato del sprint (nadie crea migraciones en `cuentas/`),
pero depende de su última migración para correr después de ella.

Decisión de Oscar, «como hoy»: las recibe **quien hoy edita la cartera**
(`cartera.editar` efectivo) — el mismo que ya puede cambiar los contactos del
cliente a los que se invita. Nadie gana ni pierde otra cosa.

Dos pasos (el patrón de `cuentas/0048`):

  1. JSON de los roles: cada rol que trae `cartera.editar` recibe las tres
     acciones. Así «ver como rol» dice la verdad y quien reciba el rol mañana
     las trae.
  2. Una fila ENCENDIDA por persona con `cartera.editar` efectivo: super_admin
     (failsafe: `lib.permisos.puede()` NO lo tiene automático), fila propia
     encendida, o algún rol extra que lo traiga sin una fila que lo apague. La
     fila por persona hace falta porque la grilla de El Directorio muestra fila
     o default del rol primario, y guardarla apagaría lo que sólo viniera del rol.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion` (0046 lo documenta: escribirlo mal no truena en pruebas y sí en
producción).
"""

from __future__ import annotations

from django.db import migrations

MODULO = "recepcion"
ACCIONES = ("ver", "invitar", "revocar")
LLAVE = ("cartera", "editar")


def _rol_trae(rol, modulo: str, accion: str) -> bool:
    return accion in ((rol.permisos or {}).get(modulo) or [])


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    # 1) Roles.
    for rol in Rol.objects.all():
        if rol.clave == "super_admin" or _rol_trae(rol, *LLAVE):
            mapa = dict(rol.permisos or {})
            acciones = set(mapa.get(MODULO) or [])
            if not set(ACCIONES) <= acciones:
                acciones.update(ACCIONES)
                mapa[MODULO] = sorted(acciones)
                rol.permisos = mapa
                rol.save(update_fields=["permisos"])

    # 2) Personas.
    for u in Usuario.objects.filter(is_active=True).prefetch_related("roles_extra"):
        extras = list(u.roles_extra.all())
        es_super = u.rol == "super_admin" or any(r.clave == "super_admin" for r in extras)
        fila = Permiso.objects.filter(usuario=u, modulo=LLAVE[0], permiso=LLAVE[1]).first()
        if fila is not None and not fila.activo and not es_super:
            continue  # alguien se lo quitó a mano: se respeta
        tiene = es_super or (fila is not None and fila.activo) or any(
            _rol_trae(r, *LLAVE) for r in extras)
        if not tiene:
            continue
        for accion in ACCIONES:
            Permiso.objects.update_or_create(
                usuario=u, modulo=MODULO, permiso=accion, defaults={"activo": True},
            )


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
        ("portal", "0001_initial"),
        ("cuentas", "0050_recordatorios_texto_por_permiso"),
    ]

    operations = [migrations.RunPython(sembrar, quitar)]
