"""S-LC-Feedback-V10 — gating granular de las áreas administrativas.

Decisión Oscar: "todo, TODO, debe tener permisos granulares". Las áreas de La
Gerencia que se gateaban por rol literal (`@requires_role("super_admin"…)`)
pasan a permisos delegables: `ajustes`, `directorio`, `chalanes`, `site`,
`catalogos`, `interfono`. Esta migración seedea las filas que PRESERVAN el
alcance previo de cada rol:

  • super_admin → todas las acciones de las 6 áreas (failsafe duro + UI).
  • dueno → exactamente lo que ya alcanzaba: directorio[ver,gestionar],
    chalanes[ver], site[ver], interfono[configurar].

El resto de usuarios/roles no recibe nada por default; se delega desde
`/directorio/<id>/permisos/` o vía roles personalizados. El signal
`auto_seedear_permisos` cubre usuarios nuevos (DEFAULTS_POR_ROL).

Idempotente vía bulk_create(ignore_conflicts=True).
"""

from __future__ import annotations

from django.db import migrations

SUPER = {
    "ajustes": ["acceder"],
    "directorio": ["ver", "gestionar", "panel", "ia", "permisos", "roles"],
    "chalanes": ["ver", "configurar"],
    "site": ["ver"],
    "catalogos": ["estados", "tipos", "centros_costo"],
    "interfono": ["configurar"],
}
DUENO = {
    "directorio": ["ver", "gestionar"],
    "chalanes": ["ver"],
    "site": ["ver"],
    "interfono": ["configurar"],
}
MODULOS = list(SUPER.keys())


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    filas = []
    for u in Usuario.objects.filter(rol="super_admin").order_by("pk"):
        for modulo, acciones in SUPER.items():
            for permiso in acciones:
                filas.append(PermisoUsuario(usuario=u, modulo=modulo, permiso=permiso, activo=True))
    for u in Usuario.objects.filter(rol="dueno").order_by("pk"):
        for modulo, acciones in DUENO.items():
            for permiso in acciones:
                filas.append(PermisoUsuario(usuario=u, modulo=modulo, permiso=permiso, activo=True))
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo__in=MODULOS).delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0028_sidebar_orden_usuario_grupo")]
    operations = [migrations.RunPython(seed, reverse)]
