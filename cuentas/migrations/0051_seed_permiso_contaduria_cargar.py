"""Permiso (contaduria, cargar) — la carga contable de un jalón (S-Carga-Contable).

Quién lo recibe: **quien hoy captura en La Contaduría** (fila activa de
`contaduria.capturar`) y todo `super_admin`. Es el mismo círculo que ya mueve
asientos a mano; la carga sólo lo hace en bloque. Sigue siendo granular (§4 #20):
se quita o se da por persona desde /directorio/<id>/permisos/.

Dos caminos, como en la 0046:
· la fila individual de cada usuario — lo que lee `puede()`;
· el JSON de cada Rol que ya trae `capturar` — lo que lee «ver como rol».
Los usuarios NUEVOS lo reciben por `defaults_de()` (TODO_CONTADURIA).

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion`. Sólo datos, sin esquema (Bug I). Idempotente.
"""

from __future__ import annotations

from django.db import migrations

MODULO = "contaduria"
PERMISO = "cargar"
BASE = "capturar"


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    con_captura = set(
        PermisoUsuario.objects.filter(modulo=MODULO, permiso=BASE, activo=True)
        .values_list("usuario_id", flat=True)
    )
    super_admins = set(Usuario.objects.filter(rol="super_admin").values_list("pk", flat=True))
    filas = [
        PermisoUsuario(usuario_id=pk, modulo=MODULO, permiso=PERMISO, activo=True)
        for pk in sorted(con_captura | super_admins)
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)

    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        acciones = set(mapa.get(MODULO) or [])
        if BASE not in acciones or PERMISO in acciones:
            continue
        acciones.add(PERMISO)
        mapa[MODULO] = sorted(acciones)
        rol.permisos = mapa
        rol.save(update_fields=["permisos"])


def quitar(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo=MODULO, permiso=PERMISO).delete()
    Rol = apps.get_model("cuentas", "Rol")
    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        acciones = set(mapa.get(MODULO) or [])
        if PERMISO in acciones:
            acciones.discard(PERMISO)
            mapa[MODULO] = sorted(acciones)
            rol.permisos = mapa
            rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0050_recordatorios_texto_por_permiso")]
    operations = [migrations.RunPython(sembrar, quitar)]
