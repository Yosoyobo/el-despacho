from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interfono", "0002_url_textfield"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PreferenciaCategoriaPush",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("categoria", models.CharField(max_length=40)),
                ("activo", models.BooleanField(default=True)),
                ("modificado_en", models.DateTimeField(auto_now=True)),
                ("usuario", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="preferencias_push", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "interfono_preferencia_categoria",
                "unique_together": {("usuario", "categoria")},
            },
        ),
        migrations.AddIndex(
            model_name="preferenciacategoriapush",
            index=models.Index(fields=["usuario", "categoria"], name="pref_push_user_cat_idx"),
        ),
    ]
