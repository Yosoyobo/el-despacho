"""Agrega Proyecto.slug para el Sistema de Referencias (#).

El slug es el código en minúsculas (`PRY-000123` → `pry-000123`).
"""

from __future__ import annotations

import re
import unicodedata

from django.db import migrations, models


def _normalizar(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", sin_acentos.lower()).strip("-")


def backfill_slugs(apps, schema_editor):
    Proyecto = apps.get_model("proyectos", "Proyecto")
    tomados: set[str] = set()
    for p in Proyecto.objects.all().order_by("pk"):
        base = _normalizar((p.codigo or "").lower()) or "proyecto"
        candidato = base
        n = 2
        while candidato in tomados or Proyecto.objects.filter(slug=candidato).exclude(pk=p.pk).exists():
            candidato = f"{base}-{n}"
            n += 1
        p.slug = candidato
        p.save(update_fields=["slug"])
        tomados.add(candidato)


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("proyectos", "0002_montos_pipeline")]

    operations = [
        migrations.AddField(
            model_name="proyecto",
            name="slug",
            field=models.CharField(max_length=80, null=True),
        ),
        migrations.RunPython(backfill_slugs, reverse_backfill),
        migrations.AlterField(
            model_name="proyecto",
            name="slug",
            field=models.CharField(max_length=80, unique=True),
        ),
    ]
