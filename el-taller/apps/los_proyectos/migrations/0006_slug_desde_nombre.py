"""Migra el slug del proyecto de basarse en código a basarse en nombre.

Para cada proyecto existente:
- `slug_legacy` toma el valor del slug actual (basado en código `lc-NNNN`).
- `slug` se regenera desde el nombre, con desambiguación por sufijo si hay
  colisión. El resolver de referencias consulta ambos campos, así que
  textos viejos con `#lc-0001` siguen funcionando.
"""

from __future__ import annotations

import re
import unicodedata

from django.db import migrations, models


def _normalizar(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    s = sin_acentos.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def renombrar_slugs(apps, schema_editor):
    Proyecto = apps.get_model("proyectos", "Proyecto")
    usados = set()
    proyectos = list(Proyecto.objects.all().order_by("pk"))
    for p in proyectos:
        viejo = p.slug
        base = _normalizar(p.nombre or "")[:60] or "proyecto"
        nuevo = base
        n = 1
        while nuevo in usados or Proyecto.objects.filter(slug=nuevo).exclude(pk=p.pk).exists():
            n += 1
            nuevo = f"{base}-{n}"
        if nuevo != viejo:
            p.slug_legacy = viejo
            p.slug = nuevo
            p.save(update_fields=["slug", "slug_legacy"])
        usados.add(nuevo)


def reverse(apps, schema_editor):
    Proyecto = apps.get_model("proyectos", "Proyecto")
    for p in Proyecto.objects.exclude(slug_legacy__isnull=True).exclude(slug_legacy=""):
        p.slug = p.slug_legacy
        p.slug_legacy = None
        p.save(update_fields=["slug", "slug_legacy"])


class Migration(migrations.Migration):
    dependencies = [("proyectos", "0005_renumerar_a_lc")]
    operations = [
        migrations.AddField(
            model_name="proyecto",
            name="slug_legacy",
            field=models.CharField(blank=True, db_index=True, max_length=80, null=True),
        ),
        migrations.RunPython(renombrar_slugs, reverse),
    ]
