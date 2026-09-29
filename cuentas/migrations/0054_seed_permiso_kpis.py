"""Permiso (kpis, configurar) — La Gerencia → Ajustes → KPIs (S-KPIs-V2, 2026-09-29).

Reemplaza a la puerta que tenía el panel de metas (`ajustes.acceder`), así que
nace «como hoy»: lo recibe EXACTAMENTE quien hoy abre Los Ajustes.

· Fila individual (lo que lee `puede()`) para: quien tiene `ajustes.acceder`
  activo por fila, quien lo trae por el JSON de algún rol asignado, y el
  super_admin (primario o asignado).
· El JSON de cada rol que trae `ajustes.acceder` (lo que lee «ver como rol»).
Los usuarios NUEVOS lo reciben por `defaults_de()` (sólo super_admin).

Una revocación explícita (`ajustes.acceder` con `activo=False`) se respeta: esa
persona no recibe la fila nueva. Sólo datos (Bug I). Idempotente.
"""

from __future__ import annotations

from django.db import migrations

MODULO = "kpis"
PERMISO = "configurar"
ORIGEN = ("ajustes", "acceder")


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    roles_con_ajustes = [
        rol for rol in Rol.objects.all()
        if ORIGEN[1] in ((rol.permisos or {}).get(ORIGEN[0]) or [])
    ]
    revocados = set(
        PermisoUsuario.objects.filter(modulo=ORIGEN[0], permiso=ORIGEN[1], activo=False)
        .values_list("usuario_id", flat=True)
    )
    quienes = set(
        PermisoUsuario.objects.filter(modulo=ORIGEN[0], permiso=ORIGEN[1], activo=True)
        .values_list("usuario_id", flat=True)
    )
    quienes |= set(Usuario.objects.filter(rol="super_admin").values_list("pk", flat=True))
    quienes |= set(
        Usuario.objects.filter(roles_extra__clave="super_admin").values_list("pk", flat=True)
    )
    if roles_con_ajustes:
        quienes |= set(
            Usuario.objects.filter(roles_extra__in=roles_con_ajustes).values_list("pk", flat=True)
        )
    quienes -= revocados

    PermisoUsuario.objects.bulk_create(
        [PermisoUsuario(usuario_id=pk, modulo=MODULO, permiso=PERMISO, activo=True)
         for pk in sorted(quienes)],
        ignore_conflicts=True,
    )

    for rol in roles_con_ajustes:
        mapa = dict(rol.permisos or {})
        acciones = set(mapa.get(MODULO) or [])
        if PERMISO in acciones:
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
        if MODULO in mapa:
            mapa.pop(MODULO)
            rol.permisos = mapa
            rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0053_seed_permiso_equipo_historial")]
    operations = [migrations.RunPython(sembrar, quitar)]
