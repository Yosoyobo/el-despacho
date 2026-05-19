from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interfono", "0003_preferencia_categoria_push"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InterfonoEntrega",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("titulo", models.CharField(max_length=200)),
                ("cuerpo", models.TextField()),
                ("url", models.CharField(blank=True, default="", max_length=500)),
                ("categoria", models.CharField(blank=True, default="", max_length=40)),
                ("tag", models.CharField(blank=True, default="", max_length=100)),
                ("enviado_en", models.DateTimeField(auto_now_add=True)),
                ("clickeado_en", models.DateTimeField(blank=True, null=True)),
                ("visto_en", models.DateTimeField(blank=True, null=True)),
                ("origen_modulo", models.CharField(blank=True, default="", max_length=40)),
                ("origen_id", models.BigIntegerField(blank=True, null=True)),
                ("estado_despacho", models.CharField(blank=True, default="", max_length=30)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="entregas_interfono",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "interfono_entrega",
                "ordering": ["-enviado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="interfonoentrega",
            index=models.Index(fields=["usuario", "-enviado_en"], name="entrega_user_fecha_idx"),
        ),
        migrations.AddIndex(
            model_name="interfonoentrega",
            index=models.Index(fields=["usuario", "clickeado_en"], name="entrega_user_click_idx"),
        ),
        migrations.AddIndex(
            model_name="interfonoentrega",
            index=models.Index(fields=["categoria", "-enviado_en"], name="entrega_cat_fecha_idx"),
        ),
    ]
