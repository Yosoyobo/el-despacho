"""S-LC-Feedback-V13 (Oscar): permiso (catalogo, eliminar) — borrado PERMANENTE
de productos/proveedores, distinto de archivar.

Acción destructiva: se seedea SOLO a los super_admin existentes. El resto de
roles no lo recibe por default; el super_admin lo delega por usuario desde
/directorio/<id>/permisos/. El signal `auto_seedear_permisos` cubre usuarios
nuevos según DEFAULTS_POR_ROL (donde solo super_admin lo trae).

Idempotente vía bulk_create(ignore_conflicts=True).
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
        PermisoUsuario(usuario=u, modulo="catalogo", permiso="eliminar", activo=True)
        for u in supers
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="catalogo", permiso="eliminar").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0035_buzon_admin_solo_super_admin")]
    operations = [migrations.RunPython(seed, reverse)]
