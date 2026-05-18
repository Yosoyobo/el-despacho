"""Agrega Cliente.slug para el Sistema de Referencias ($)."""

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
    Cliente = apps.get_model("cartera", "Cliente")
    tomados: set[str] = set()
    for c in Cliente.objects.all().order_by("pk"):
        base = _normalizar(c.razon_social or "")[:50] or "cliente"
        candidato = base
        n = 2
        while candidato in tomados or Cliente.objects.filter(slug=candidato).exclude(pk=c.pk).exists():
            candidato = f"{base}-{n}"
            n += 1
        c.slug = candidato
        c.save(update_fields=["slug"])
        tomados.add(candidato)


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("cartera", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="slug",
            field=models.CharField(max_length=80, null=True),
        ),
        migrations.RunPython(backfill_slugs, reverse_backfill),
        migrations.AlterField(
            model_name="cliente",
            name="slug",
            field=models.CharField(max_length=80, unique=True),
        ),
    ]
