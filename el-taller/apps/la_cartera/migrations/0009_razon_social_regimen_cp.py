# Datos del receptor del CFDI 4.0 en cada razón social: régimen fiscal y código
# postal del domicilio fiscal. Se llenan a mano o aplicando lo que El Chalán leyó
# de la Constancia de Situación Fiscal que sube el cliente (portal/csf.py).
# Sólo esquema.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cartera", "0008_razones_sociales"),
    ]

    operations = [
        migrations.AddField(
            model_name="clienterazonsocial",
            name="regimen_fiscal",
            field=models.CharField(blank=True, default="", help_text="Régimen fiscal como viene en la constancia, p. ej. «601 · General de Ley Personas Morales».", max_length=120),
        ),
        migrations.AddField(
            model_name="clienterazonsocial",
            name="codigo_postal",
            field=models.CharField(blank=True, default="", help_text="Código postal del domicilio fiscal.", max_length=5),
        ),
    ]
