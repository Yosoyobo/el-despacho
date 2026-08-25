"""S-Papeleo-V1: los ajustes del archivo de papeleo (Paperless), por GUI.

Sólo `CreateModel`. La fila única la crea `ConfiguracionPapeleo.obtener()` al
leerla — una migración que INSERTA en la misma tabla cuyo índice acaba de crear
es lo que tumbó el arranque el 2026-08-23 (§14 Bug I).
"""

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ajustes", "0024_rutas_opciones_del_mapa"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionPapeleo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("url_publica", models.URLField(
                    blank=True, default="",
                    help_text=(
                        "La dirección con la que se abre Paperless en el navegador — la de "
                        "la red privada, por ejemplo http://100.121.244.5:8204. NO es la "
                        "que usa el servidor por dentro: sin ésta, los enlaces a un "
                        "documento no abren en ninguna máquina."
                    ))),
                ("ligar_automatico", models.BooleanField(
                    default=False,
                    help_text=(
                        "Cuando entra un documento, buscar en su texto a qué cliente, "
                        "proveedor o proyecto se refiere y ligarlo solo. Sólo liga cuando "
                        "no hay duda: si dos clientes coinciden, lo deja sin ligar para "
                        "que alguien decida — adivinar sería peor que no ligar."
                    ))),
                ("minimo_caracteres_nombre", models.PositiveSmallIntegerField(
                    default=6,
                    validators=[django.core.validators.MinValueValidator(3),
                                django.core.validators.MaxValueValidator(40)],
                    help_text=(
                        "Qué tan largo tiene que ser un nombre para buscarlo en el texto. "
                        "Con menos de seis letras, un nombre corto aparece por casualidad "
                        "dentro de cualquier palabra y liga documentos que no son."
                    ))),
                ("etiqueta_entrada", models.CharField(
                    blank=True, default="El Despacho", max_length=64,
                    help_text=(
                        "Etiqueta que se le pone en Paperless a todo lo que entra desde El "
                        "Despacho, para distinguirlo de lo que se escaneó a mano. Si no "
                        "existe, se crea sola. Vacío = no se etiqueta."
                    ))),
                ("avisar_al_entrar", models.BooleanField(
                    default=False,
                    help_text=(
                        "Avisar por El Interfón cuando llega papeleo nuevo. Arranca apagado "
                        "a propósito: si entran veinte remisiones el lunes, veinte avisos "
                        "enseñan al equipo a ignorarlos."
                    ))),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "ajustes_config_papeleo",
                "verbose_name": "configuración del papeleo",
                "verbose_name_plural": "configuración del papeleo",
            },
        ),
    ]
