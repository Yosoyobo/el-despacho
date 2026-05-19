from django.db import migrations

GRUPOS = [
    {
        "slug": "todos",
        "nombre_legible": "Todo el equipo",
        "descripcion": "Todos los usuarios activos del despacho.",
        "tipo": "rol",
        "roles": [],  # vacío = todos los roles activos
    },
    {
        "slug": "direccion",
        "nombre_legible": "Dirección",
        "descripcion": "Super-admin y dueño.",
        "tipo": "rol",
        "roles": ["super_admin", "dueno"],
    },
    {
        "slug": "disenio_y_produccion",
        "nombre_legible": "Diseño y producción",
        "descripcion": "Diseñadores.",
        "tipo": "rol",
        "roles": ["disenador"],
    },
    {
        "slug": "finanzas",
        "nombre_legible": "Finanzas",
        "descripcion": "Contador y dueño.",
        "tipo": "rol",
        "roles": ["contador", "dueno"],
    },
]


def seed(apps, schema_editor):
    Grupo = apps.get_model("recados", "RecadoGrupo")
    Grupo.objects.bulk_create(
        [Grupo(**g) for g in GRUPOS],
        ignore_conflicts=True,
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [("recados", "0001_initial")]
    operations = [migrations.RunPython(seed, noop)]
