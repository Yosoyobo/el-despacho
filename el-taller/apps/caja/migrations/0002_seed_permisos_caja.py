"""Las llaves de La Caja — sólo datos (Bug I: el esquema quedó en 0001).

«Como hoy» (contrato con Oscar, 2026-09-29): La Caja la recibe quien YA maneja
el dinero, sin que nadie gane ni pierda nada que no tenía:

  · `caja.ver`                      ← quien tiene `tesoreria.ver` o `facturacion.cobrar`
  · `caja.crear_link/anular_link/revisar_pago` ← quien tiene `facturacion.cobrar`
    (hacer un link, matarlo o decidir un pago que no cuadró es cobrar)
  · super_admin: todo, siempre — `lib.permisos.puede()` NO tiene failsafe
    automático y sin su fila ni el dueño del sistema vería La Caja.

Se mira la fila ACTIVA de cada persona y el JSON de cada Rol (los roles extra
se evalúan por su JSON en `puede()`, así que basta con sumárselo al rol). Una
fila ya existente de `caja` no se pisa: si alguien la apagó a mano, se respeta.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion` (ver `cuentas/0044`: tumbó un arranque en producción).

Depende de `cuentas/0050` por contrato con La Recepción: nadie crea
migraciones en `cuentas/`, cada frente siembra las suyas en su app.
"""

from django.db import migrations

MODULO = "caja"
TODO = ("ver", "crear_link", "anular_link", "revisar_pago")
DE_COBRAR = ("crear_link", "anular_link", "revisar_pago")


def acciones_para(tiene_tesoreria_ver: bool, tiene_cobrar: bool) -> set[str]:
    acciones: set[str] = set()
    if tiene_tesoreria_ver or tiene_cobrar:
        acciones.add("ver")
    if tiene_cobrar:
        acciones.update(DE_COBRAR)
    return acciones


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    for usuario in Usuario.objects.all():
        if usuario.rol == "super_admin":
            acciones = set(TODO)
        else:
            activas = set(
                Permiso.objects.filter(usuario=usuario, activo=True, modulo__in=("tesoreria", "facturacion"))
                .values_list("modulo", "permiso")
            )
            acciones = acciones_para(("tesoreria", "ver") in activas, ("facturacion", "cobrar") in activas)
        for accion in sorted(acciones):
            Permiso.objects.get_or_create(
                usuario=usuario, modulo=MODULO, permiso=accion, defaults={"activo": True},
            )

    for rol in Rol.objects.all():
        mapa = dict(rol.permisos or {})
        if rol.clave == "super_admin":
            nuevas = set(TODO)
        else:
            nuevas = acciones_para("ver" in (mapa.get("tesoreria") or []),
                                   "cobrar" in (mapa.get("facturacion") or []))
        if not nuevas:
            continue
        actuales = set(mapa.get(MODULO) or [])
        if nuevas <= actuales:
            continue
        mapa[MODULO] = sorted(actuales | nuevas)
        rol.permisos = mapa
        rol.save(update_fields=["permisos"])


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
        ("caja", "0001_initial"),
        ("cuentas", "0050_recordatorios_texto_por_permiso"),
    ]

    operations = [migrations.RunPython(sembrar, quitar)]
