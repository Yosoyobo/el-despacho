"""S-Directorio-V1: ficha del empleado en el Usuario (puesto, teléfono,
oficina, modalidad, horario, días). Editable en Gerencia, read-only en Taller.
Los checkins/ponchado son El Checador (sprint aparte)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cuentas", "0020_novedades"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="puesto",
            field=models.CharField(blank=True, default="", max_length=120,
                                   help_text="Cargo o puesto, ej. Auditor."),
        ),
        migrations.AddField(
            model_name="usuario",
            name="telefono",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="usuario",
            name="oficina",
            field=models.CharField(blank=True, default="", max_length=120,
                                   help_text="Sede o ubicación de trabajo."),
        ),
        migrations.AddField(
            model_name="usuario",
            name="modalidad",
            field=models.CharField(
                default="presencial", max_length=12,
                choices=[("presencial", "Presencial"), ("remoto", "Home office"), ("hibrido", "Híbrido")],
            ),
        ),
        migrations.AddField(
            model_name="usuario",
            name="horario_inicio",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="horario_fin",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="dias_trabajo",
            field=models.CharField(blank=True, default="", max_length=80,
                                   help_text="Ej. Lunes a viernes."),
        ),
    ]
