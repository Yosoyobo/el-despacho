import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recados', '0005_mensaje_adjunto'),
        ('checador', '0002_seed_horario_global'),
    ]

    operations = [
        migrations.AddField(
            model_name='mensaje',
            name='correccion',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mensajes_chat',
                to='checador.solicitudcorreccion',
            ),
        ),
    ]
