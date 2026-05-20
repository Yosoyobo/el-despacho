"""Sprint S-Recados-Chat — modelos Conversacion + Mensaje + MensajeLectura.

No toca tablas existentes (Recado / Destinatario / Version / Grupo
quedan intactas — los recados viejos siguen accesibles vía la bandeja
legacy).
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recados", "0002_seed_grupos"),
        ("cuentas", "__latest__"),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversacion",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("tipo", models.CharField(
                    max_length=10,
                    choices=[("directa", "Directa"), ("grupo", "Grupo")],
                    default="directa",
                    db_index=True,
                )),
                ("nombre", models.CharField(max_length=120, blank=True, default="")),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("ultima_actividad", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("clave_directa", models.CharField(max_length=40, blank=True, null=True, unique=True)),
                ("creada_por", models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    related_name="conversaciones_creadas",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("participantes", models.ManyToManyField(
                    related_name="conversaciones",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "recados_conversacion",
                "ordering": ["-ultima_actividad"],
            },
        ),
        migrations.CreateModel(
            name="Mensaje",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("cuerpo", models.TextField()),
                ("creado_en", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("editado_en", models.DateTimeField(null=True, blank=True)),
                ("autor", models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    related_name="mensajes_chat",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("conversacion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="mensajes",
                    to="recados.conversacion",
                )),
            ],
            options={
                "db_table": "recados_mensaje",
                "ordering": ["creado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="mensaje",
            index=models.Index(fields=["conversacion", "creado_en"], name="recados_men_convers_4f8e6e_idx"),
        ),
        migrations.CreateModel(
            name="MensajeLectura",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("conversacion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lecturas",
                    to="recados.conversacion",
                )),
                ("ultimo_mensaje", models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    to="recados.mensaje",
                )),
                ("usuario", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lecturas_chat",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "recados_mensaje_lectura",
            },
        ),
        migrations.AddConstraint(
            model_name="mensajelectura",
            constraint=models.UniqueConstraint(fields=["usuario", "conversacion"], name="uniq_lectura_user_conv"),
        ),
    ]
