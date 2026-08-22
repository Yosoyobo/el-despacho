"""Permiso (site, limpiar) — correr La Limpieza desde El Site (LC 2026-08-23).

El botón suelta caché, RAM y disco: borra las llaves del caché de la aplicación,
compacta La Libreta, aspira la base, poda lo que Docker dejó tirado y recicla los
trabajadores de gunicorn. No borra datos de nadie, pero MUEVE la máquina, y ver el
tablero no tiene por qué implicar poder tocarlo — de ahí que sea una acción propia
y no venga incluida en `site.ver`.

Se seedea sólo a los super_admin existentes; el resto se delega por usuario desde
/directorio/<id>/permisos/, donde ya aparece solo por estar en el catálogo.
Idempotente. En la pared del NUC no se consulta este permiso: ahí la puerta es
estar físicamente en la máquina.
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
        PermisoUsuario(usuario=u, modulo="site", permiso="limpiar", activo=True)
        for u in supers
    ]
    if filas:
        PermisoUsuario.objects.bulk_create(filas, ignore_conflicts=True)


def reverse(apps, schema_editor):
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")
    PermisoUsuario.objects.filter(modulo="site", permiso="limpiar").delete()


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0041_seed_permiso_analisis")]
    operations = [migrations.RunPython(seed, reverse)]
