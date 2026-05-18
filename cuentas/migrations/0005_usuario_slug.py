"""Agrega Usuario.slug para el Sistema de Referencias (@).

Patrón 3 pasos: AddField nullable → RunPython backfill → AlterField unique.
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
    Usuario = apps.get_model("cuentas", "Usuario")
    tomados: set[str] = set()
    for u in Usuario.objects.all().order_by("pk"):
        base = _normalizar((u.email or "").split("@", 1)[0])[:60] or "usuario"
        candidato = base
        n = 2
        while candidato in tomados or Usuario.objects.filter(slug=candidato).exclude(pk=u.pk).exists():
            candidato = f"{base}-{n}"
            n += 1
        u.slug = candidato
        u.save(update_fields=["slug"])
        tomados.add(candidato)


def reverse_backfill(apps, schema_editor):
    pass  # AlterField inverso recibe nullable nuevamente


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0004_avatar_url_text")]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="slug",
            field=models.CharField(max_length=80, null=True, db_index=True),
        ),
        migrations.RunPython(backfill_slugs, reverse_backfill),
        migrations.AlterField(
            model_name="usuario",
            name="slug",
            field=models.CharField(max_length=80, unique=True, db_index=True),
        ),
    ]
