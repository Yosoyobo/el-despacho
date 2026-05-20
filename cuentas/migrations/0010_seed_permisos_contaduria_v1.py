"""S3.contaduria-v1: re-seed permisos del módulo contaduria con las
acciones reales V1 (ver, capturar, anular, reportes).

Idempotente: bulk_create con ignore_conflicts y, antes, limpia las
acciones legacy 'reconciliar' y 'exportar' que sembró 0007.
"""

from __future__ import annotations

from django.db import migrations

ACCIONES_V1 = {
    "super_admin": ["ver", "capturar", "anular", "reportes"],
    "dueno": ["ver", "capturar", "anular", "reportes"],
    "contador": ["ver", "capturar", "anular", "reportes"],
}

ACCIONES_LEGACY = ["reconciliar", "exportar"]


def seed(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    Usuario = apps.get_model("cuentas", "Usuario")
    # Limpia las acciones legacy de cualquier usuario.
    PermisoUsuario.objects.filter(modulo="contaduria", permiso__in=ACCIONES_LEGACY).delete()
    # Siembra las V1 para usuarios que tengan rol en ACCIONES_V1.
    filas = []
    for u in Usuario.objects.all().order_by("pk"):
        acciones = ACCIONES_V1.get(u.rol, [])
        for permiso in acciones:
            filas.append(PermisoUsuario(
                usuario=u, modulo="contaduria", permiso=permiso, activo=True,
            ))
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="contaduria").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0009_seed_permisos_cotizaciones")]
    operations = [migrations.RunPython(seed, reverse)]
