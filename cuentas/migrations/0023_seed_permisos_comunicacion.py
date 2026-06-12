"""S-LC-Feedback-V6 Bloque 7: seedea PermisoUsuario del módulo `comunicacion`
(enviar_correo + campanas) SOLO para super_admin existentes.

Decisión Oscar: gating 100% granular — el resto de usuarios/roles lo recibe
desde /directorio/<id>/permisos/ o vía roles personalizados, no por rol duro.
El signal `auto_seedear_permisos` cubre usuarios nuevos (DEFAULTS_POR_ROL).

Idempotente vía bulk_create(ignore_conflicts=True).
"""

from __future__ import annotations

from django.db import migrations

PERMISOS = ["enviar_correo", "campanas"]


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    filas = []
    for u in Usuario.objects.filter(rol="super_admin").order_by("pk"):
        for permiso in PERMISOS:
            filas.append(PermisoUsuario(usuario=u, modulo="comunicacion", permiso=permiso, activo=True))
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="comunicacion").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0022_seed_permisos_checador")]
    operations = [migrations.RunPython(seed, reverse)]
