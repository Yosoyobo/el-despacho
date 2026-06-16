"""S-Checador-V14 — POI de visita, sede esperada y snapshot de ubicación.

- Visita: propósito (visita/tarea), liga a contacto/tarea + verificación por IA.
- SesionProyecto: snapshot de ubicación (lat/lng/precisión/sin_geo).
- HorarioLaboral / Jornada / SolicitudCorreccion: sede esperada (FK + texto).

Migración escrita a mano (makemigrations genera espurios en este repo).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("checador", "0007_sede_geocerca"),
        ("cartera", "0003_cliente_contacto"),
        ("pizarron", "0006_estado_descripcion_accion"),
    ]

    operations = [
        # ── Visita: POI (contacto/tarea), propósito y verificación IA ──
        migrations.AddField(
            model_name="visita",
            name="proposito",
            field=models.CharField(
                choices=[("visita", "Visita"), ("tarea", "Tarea/entrega completada")],
                default="visita", max_length=10),
        ),
        migrations.AddField(
            model_name="visita",
            name="contacto",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="visitas_checador", to="cartera.clientecontacto"),
        ),
        migrations.AddField(
            model_name="visita",
            name="tarea",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="visitas_checador", to="pizarron.tarea"),
        ),
        migrations.AddField(
            model_name="visita",
            name="ia_proposito",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="visita",
            name="ia_completada",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="visita",
            name="ia_confianza",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="visita",
            name="ia_resumen",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="visita",
            name="ia_verificado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="visita",
            name="tipo",
            field=models.CharField(
                choices=[("cliente", "Cliente"), ("proveedor", "Proveedor"),
                         ("contacto", "Contacto"), ("otro", "Otro")],
                default="cliente", max_length=10),
        ),
        # ── SesionProyecto: snapshot de ubicación ──
        migrations.AddField(
            model_name="sesionproyecto",
            name="lat",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sesionproyecto",
            name="lng",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sesionproyecto",
            name="precision",
            field=models.FloatField(blank=True, help_text="Metros", null=True),
        ),
        migrations.AddField(
            model_name="sesionproyecto",
            name="sin_geo",
            field=models.BooleanField(default=False),
        ),
        # ── HorarioLaboral: sede esperada ──
        migrations.AddField(
            model_name="horariolaboral",
            name="sede",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="horarios", to="checador.sedelc"),
        ),
        migrations.AddField(
            model_name="horariolaboral",
            name="sede_texto",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        # ── Jornada: sede ──
        migrations.AddField(
            model_name="jornada",
            name="sede",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="jornadas", to="checador.sedelc"),
        ),
        migrations.AddField(
            model_name="jornada",
            name="sede_texto",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        # ── SolicitudCorreccion: sede ──
        migrations.AddField(
            model_name="solicitudcorreccion",
            name="sede",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="correcciones", to="checador.sedelc"),
        ),
        migrations.AddField(
            model_name="solicitudcorreccion",
            name="sede_texto",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
    ]
