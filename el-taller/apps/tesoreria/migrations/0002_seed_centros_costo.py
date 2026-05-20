"""Seed inicial de centros de costo (DOC_06 §4.1).

Idempotente: usa get_or_create por slug. Super_admin puede editar/desactivar
desde La Gerencia → Catálogos → Centros de costo después del bootstrap."""

from django.db import migrations

SEED = [
    ("Insumos de proyecto", "insumos-de-proyecto", "proyecto",
     "Materiales específicos de un proyecto."),
    ("Impresión y maquila", "impresion-y-maquila", "proyecto",
     "Costos de producción externa."),
    ("Nómina", "nomina", "operativo", "Sueldos y prestaciones."),
    ("Honorarios externos", "honorarios-externos", "mixto",
     "Freelancers, asesores."),
    ("Renta y servicios", "renta-y-servicios", "operativo",
     "Oficina, internet, luz."),
    ("Software y suscripciones", "software-y-suscripciones", "operativo",
     "Licencias, SaaS."),
    ("Viáticos", "viaticos", "mixto", "Transporte, comidas, hospedaje."),
    ("Marketing", "marketing", "operativo", "Anuncios, eventos."),
    ("Impuestos y comisiones", "impuestos-y-comisiones", "operativo",
     "SAT, bancarias."),
    ("Otros", "otros", "mixto", "Catch-all."),
]


def forward(apps, schema_editor):
    Cdc = apps.get_model("tesoreria", "CentroDeCosto")
    for nombre, slug, naturaleza, descripcion in SEED:
        Cdc.objects.get_or_create(
            slug=slug,
            defaults={
                "nombre": nombre,
                "naturaleza": naturaleza,
                "descripcion": descripcion,
                "activo": True,
            },
        )


def reverse(apps, schema_editor):
    Cdc = apps.get_model("tesoreria", "CentroDeCosto")
    Cdc.objects.filter(slug__in=[s for _, s, *_ in SEED]).delete()


class Migration(migrations.Migration):
    dependencies = [("tesoreria", "0001_initial")]
    operations = [migrations.RunPython(forward, reverse)]
