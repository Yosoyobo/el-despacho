"""S-KPIs-V2: el tablero por omisión nace con lo que el Inicio pintaba fijo.

Hasta hoy la zona compacta del Inicio pintaba SIEMPRE los mismos 8 KPIs
(`COMPACT_KPI_SLUGS`), y la página de preferencias guardaba una fila por CADA
KPI del catálogo (visible o no). Desde esta versión el Inicio pinta el tablero
de los roles de cada quien (o este, el por omisión) y `PreferenciaKPI` sólo
guarda lo que la persona cambió encima.

Dos pasos:
1. El tablero por omisión (`rol=None`) con los 8 de siempre → nadie ve cambiar
   su Inicio al desplegar.
2. Se borran las filas `visible=True, origen="manual"` de KPIs que NO eran de
   esos 8: las escribía el «guardar todo» y nunca se veían. Si se quedaran,
   ahora sí aparecerían y el Inicio de quien alguna vez guardó sus
   preferencias se llenaría de golpe. Se conservan las ocultas (`visible=False`),
   las de la zona grande (`hero-*`), las de KPIs del Chalán (`custom-*`), las
   aceptadas de una sugerencia y cualquier orden de los 8.

Sólo datos (Bug I). Idempotente.
"""

from __future__ import annotations

from django.db import migrations

LOS_OCHO = (
    "ingresos-mes", "egresos-mes", "utilidad-mes", "cxp-total",
    "tareas-vencidas-equipo", "valor-proyectos", "cxc-total", "cotizaciones-pendientes",
)


def sembrar(apps, schema_editor):
    TableroKPI = apps.get_model("taller_home", "TableroKPI")
    PreferenciaKPI = apps.get_model("taller_home", "PreferenciaKPI")

    if not TableroKPI.objects.filter(rol__isnull=True).exists():
        TableroKPI.objects.bulk_create([
            TableroKPI(rol=None, kpi_slug=slug, orden=i) for i, slug in enumerate(LOS_OCHO)
        ])

    (
        PreferenciaKPI.objects.filter(visible=True, origen="manual")
        .exclude(kpi_slug__in=LOS_OCHO)
        .exclude(kpi_slug__startswith="hero-")
        .exclude(kpi_slug__startswith="custom-")
        .delete()
    )


def quitar(apps, schema_editor):
    TableroKPI = apps.get_model("taller_home", "TableroKPI")
    TableroKPI.objects.filter(rol__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("taller_home", "0006_tablero_config_metas_ambito")]
    operations = [migrations.RunPython(sembrar, quitar)]
