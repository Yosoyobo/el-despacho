"""Las llaves de La Nómina — sólo datos (Bug I: el esquema quedó en 0009).

«Como hoy» (decisión Oscar, 2026-09-29): el permiso `nomina` nace para
super_admin, dueño y contador. Regla general, no por pk ni por correo:

  · super_admin (efectivo)                          → todas las acciones
  · dueño o contador (rol primario O asignado) que
    HOY tiene `tesoreria.ver` efectivo              → todas las acciones
  · nadie más.

¿Por qué pedir además `tesoreria.ver`? Porque la nómina enseña el sueldo de
cada quien — dinero — y hoy el dinero lo ve quien trae `tesoreria.ver`. Un
contador o dueño al que alguien le apagó Tesorería a propósito no debe amanecer
viendo sueldos: si se le quiere dar, se le da desde El Directorio.

Dos pasos (el mismo patrón que `cuentas/0048`):

  1. JSON de los tres roles del sistema (`super_admin`, `dueno`, `contador`):
     se les suma `nomina` completo, igual que `DEFAULTS_POR_ROL` — para quien
     reciba el rol mañana y para «ver como rol». Los roles personalizados no se
     tocan (configuración de Oscar).
  2. Una fila por persona. La grilla de El Directorio escribe una fila por
     acción al guardarse, y `puede()` cae al JSON de los roles asignados cuando
     no hay fila: por eso
       · quien califica → fila ENCENDIDA;
       · quien no califica pero el JSON de un rol suyo se lo abriría (p. ej.
         un contador sin Tesorería) → fila APAGADA, para que el paso 1 no le
         dé nada que hoy no tiene.

Una fila de `nomina` que ya exista no se pisa. Reversa: quita el módulo.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion` (`cuentas/0044` tumbó un arranque en producción por eso).

Depende de la hoja de `cuentas` (`0051`): nadie crea migraciones en `cuentas/`,
cada frente siembra las suyas en su app.
"""

from django.db import migrations

MODULO = "nomina"
TODO = ("ver", "editar", "cerrar", "pagar", "sueldos")
ROLES_NOMINA = ("dueno", "contador")
ROLES_SISTEMA_CON_NOMINA = ("super_admin", "dueno", "contador")


def _roles_de(usuario) -> set[str]:
    roles = {usuario.rol} if usuario.rol else set()
    roles.update(usuario.roles_extra.values_list("clave", flat=True))
    return roles


def _tiene_efectivo(Permiso, usuario, modulo: str, accion: str) -> bool:
    """`puede()` sin caché: fila individual gana; si no hay, el JSON de sus roles."""
    fila = Permiso.objects.filter(usuario=usuario, modulo=modulo, permiso=accion).first()
    if fila is not None:
        return bool(fila.activo)
    return any(accion in ((r.permisos or {}).get(modulo) or []) for r in usuario.roles_extra.all())


def califica(roles: set[str], tiene_tesoreria_ver: bool) -> bool:
    if "super_admin" in roles:
        return True
    return bool(roles & set(ROLES_NOMINA)) and tiene_tesoreria_ver


def sembrar(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Permiso = apps.get_model("cuentas", "PermisoUsuario")
    Rol = apps.get_model("cuentas", "Rol")

    # 1) Los roles del sistema traen `nomina` completo.
    for rol in Rol.objects.filter(clave__in=ROLES_SISTEMA_CON_NOMINA):
        mapa = dict(rol.permisos or {})
        actuales = set(mapa.get(MODULO) or [])
        if set(TODO) <= actuales:
            continue
        mapa[MODULO] = sorted(actuales | set(TODO))
        rol.permisos = mapa
        rol.save(update_fields=["permisos"])

    # 2) Una fila por persona.
    for usuario in Usuario.objects.all():
        roles = _roles_de(usuario)
        si = califica(roles, _tiene_efectivo(Permiso, usuario, "tesoreria", "ver"))
        if not si:
            por_rol = any(
                set(TODO) & set((r.permisos or {}).get(MODULO) or [])
                for r in usuario.roles_extra.all()
            )
            if not por_rol:
                continue
        for accion in TODO:
            Permiso.objects.get_or_create(
                usuario=usuario, modulo=MODULO, permiso=accion, defaults={"activo": si},
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
        ("checador", "0009_nomina"),
        ("cuentas", "0051_seed_permiso_contaduria_cargar"),
    ]

    operations = [migrations.RunPython(sembrar, quitar)]
