"""S-Mandados-V2 (Oscar): `Rol.clave` estable + `nombre` editable.

Hasta ahora el sistema de permisos identificaba los roles por su `nombre`
(`tiene_rol(user, "super_admin")`, `usuarios_con_rol("dueno")`, etc.). Para que
el usuario pueda renombrar CUALQUIER rol sin romper permisos, se introduce una
clave interna estable y oculta.

Backfill: para los roles cuyo nombre coincide con una clave usada en código
(super_admin/dueno/contador/disenador) la clave = nombre. Para el resto,
`slugify(nombre)` con desambiguación. Idempotente.
"""

from __future__ import annotations

from django.db import migrations, models
from django.utils.text import slugify

# Nombres que el código referencia literalmente → su clave DEBE ser igual.
_CLAVES_CODIGO = {"super_admin", "dueno", "contador", "disenador"}


def poblar_clave(apps, schema_editor):
    Rol = apps.get_model("cuentas", "Rol")
    usadas: set[str] = set()
    for rol in Rol.objects.all().order_by("pk"):
        if rol.clave:
            usadas.add(rol.clave)
            continue
        if rol.nombre in _CLAVES_CODIGO:
            base = rol.nombre
        else:
            base = slugify(rol.nombre) or f"rol-{rol.pk}"
        clave = base
        i = 2
        while clave in usadas:
            clave = f"{base}-{i}"
            i += 1
        usadas.add(clave)
        rol.clave = clave
        rol.save(update_fields=["clave"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0033_unificar_roles_y_runner")]

    operations = [
        migrations.AddField(
            model_name="rol",
            # db_index=False evita crear el índice `_like` (varchar_pattern_ops)
            # de Postgres aquí; el AlterField a unique=True lo crea una sola vez.
            name="clave",
            field=models.SlugField(default="", editable=False, max_length=60, db_index=False),
            preserve_default=False,
        ),
        migrations.RunPython(poblar_clave, reverse_noop),
        migrations.AlterField(
            model_name="rol",
            name="clave",
            field=models.SlugField(editable=False, max_length=60, unique=True),
        ),
    ]
