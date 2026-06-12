"""S-LC-Feedback-V6 Bloque 10 (decisión Oscar): eliminar el rol dueño.

- `Usuario.rol` gana el valor neutro "miembro" (sin defaults de permisos).
- Data migration: cada usuario con rol="dueno" pasa a rol="miembro" y recibe
  el Rol personalizado "dueno" (tabla Rol, seedeado en 0014) vía roles_extra.
  Como `lib.permisos.roles_efectivos()` une rol primario + roles_extra POR
  NOMBRE, todos los checks (es_admin, kpis, pushes) lo siguen reconociendo;
  sus PermisoUsuario granulares quedan intactos.
- "dueno/contador/disenador" quedan como valores legacy del enum (datos y
  tests existentes) — ya no asignables desde El Directorio.
"""

from django.db import migrations, models


def dueno_a_miembro(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Rol = apps.get_model("cuentas", "Rol")
    rol_dueno = Rol.objects.filter(nombre="dueno").first()
    for u in Usuario.objects.filter(rol="dueno"):
        if rol_dueno is not None:
            u.roles_extra.add(rol_dueno)
        u.rol = "miembro"
        u.save(update_fields=["rol"])


def reverse(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Rol = apps.get_model("cuentas", "Rol")
    rol_dueno = Rol.objects.filter(nombre="dueno").first()
    if rol_dueno is None:
        return
    for u in Usuario.objects.filter(rol="miembro", roles_extra=rol_dueno):
        u.rol = "dueno"
        u.save(update_fields=["rol"])
        u.roles_extra.remove(rol_dueno)


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0023_seed_permisos_comunicacion")]
    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="rol",
            field=models.CharField(
                choices=[
                    ("super_admin", "Super Admin"),
                    ("miembro", "Miembro"),
                    ("dueno", "Admin (legacy)"),
                    ("contador", "Contador (legacy)"),
                    ("disenador", "Diseñador (legacy)"),
                ],
                db_index=True,
                default="disenador",
                max_length=20,
            ),
        ),
        migrations.RunPython(dueno_a_miembro, reverse),
    ]
