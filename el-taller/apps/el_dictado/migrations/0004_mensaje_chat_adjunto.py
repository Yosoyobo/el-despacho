import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("el_dictado", "0003_chat_conversaciones"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MensajeChatAdjunto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("drive_file_id", models.CharField(max_length=255)),
                ("nombre", models.CharField(max_length=255)),
                ("mime_type", models.CharField(blank=True, default="", max_length=120)),
                ("tamano_bytes", models.PositiveBigIntegerField(default=0)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("mensaje", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="adjuntos", to="el_dictado.mensajechat")),
                ("subido_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="chat_adjuntos", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "el_dictado_mensaje_chat_adjunto",
                "ordering": ["creado_en"],
            },
        ),
    ]
