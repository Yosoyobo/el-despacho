"""Permiso (cotizaciones, eliminar) — borrado PERMANENTE de una cotización
anulada o en borrador (LC 2026-07-25, Oscar).

Sin esto no había forma de soltar una cotización: `Cotizacion.cliente` es
PROTECT, así que un cliente archivado con cotizaciones (aunque estuvieran
anuladas) quedaba imposible de eliminar y no existía pantalla para borrarlas.

Acción destructiva: se seedea SOLO a los super_admin existentes; el resto se
delega por usuario desde /directorio/<id>/permisos/. Idempotente.
"""

from __future__ import annotations

from django.db import migrations
from django.db.models import Q


def seed(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    supers = (
        Usuario.objects.filter(
            Q(rol="super_admin") | Q(roles_extra__clave="super_admin")
        )
        .distinct()
        .order_by("pk")
    )
    filas = [
        PermisoUsuario(usuario=u, modulo="cotizaciones", permiso="eliminar", activo=True)
        for u in supers
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="cotizaciones", permiso="eliminar").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0038_seed_permiso_cartera_eliminar")]
    operations = [migrations.RunPython(seed, reverse)]
