import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

CORE = [
    ("Materiales", "materiales", "#465FFF", 10),
    ("Confección", "confeccion", "#12B76A", 20),
    ("Impresión", "impresion", "#F79009", 30),
    ("Promocionales", "promocionales", "#EE46BC", 40),
    ("Letreros", "letreros", "#F04438", 50),
    ("Servicios", "servicios", "#0BA5EC", 60),
]

SUB = [
    # (nombre, slug, core_slug)
    ("Insumos", "insumos", "materiales"),
    ("Blanks", "blanks", "materiales"),
    ("Telas", "telas", "materiales"),
    ("Acrílicos y Rígidos", "acrilicos-rigidos", "materiales"),
    ("Empaques", "empaques", "materiales"),
    ("Corte y Confección", "corte-confeccion", "confeccion"),
    ("Ropa y Uniformes", "ropa-uniformes", "confeccion"),
    ("Bordado", "bordado", "confeccion"),
    ("Serigrafía", "serigrafia", "impresion"),
    ("Impresión Digital", "impresion-digital", "impresion"),
    ("DTG", "dtg", "impresion"),
    ("Offset", "offset", "impresion"),
    ("Gran Formato", "gran-formato", "impresion"),
    ("Grabado Láser", "grabado-laser", "impresion"),
    ("Promocionales", "promocionales-sub", "promocionales"),
    ("Letreros", "letreros-sub", "letreros"),
    ("Diseño Gráfico", "diseno-grafico", "servicios"),
    ("Instalación y Montaje", "instalacion-montaje", "servicios"),
    ("Logística y Envíos", "logistica-envios", "servicios"),
]


def _seed(apps, schema_editor):
    Cat = apps.get_model("el_catalogo", "CategoriaProveedor")
    Sub = apps.get_model("el_catalogo", "SubcategoriaProveedor")
    for nombre, slug, color, orden in CORE:
        Cat.objects.update_or_create(
            slug=slug, defaults={"nombre": nombre, "color": color, "orden": orden, "activa": True},
        )
    for i, (nombre, slug, core_slug) in enumerate(SUB):
        core = Cat.objects.get(slug=core_slug)
        Sub.objects.update_or_create(
            slug=slug, defaults={"nombre": nombre, "categoria": core, "orden": i * 5 + 5, "activa": True},
        )


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("el_catalogo", "0008_proveedor_geo"),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoriaProveedor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=60, unique=True)),
                ("slug", models.SlugField(max_length=70, unique=True)),
                ("color", models.CharField(default="#667085", max_length=7, validators=[django.core.validators.RegexValidator("^#[0-9a-fA-F]{6}$", "Usa un color HEX como #465FFF.")])),
                ("orden", models.PositiveSmallIntegerField(db_index=True, default=100)),
                ("activa", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "db_table": "catalogo_categoria_proveedor",
                "ordering": ["orden", "nombre"],
                "verbose_name": "categoría de proveedor",
                "verbose_name_plural": "categorías de proveedor",
            },
        ),
        migrations.CreateModel(
            name="SubcategoriaProveedor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80)),
                ("slug", models.SlugField(max_length=90, unique=True)),
                ("orden", models.PositiveSmallIntegerField(db_index=True, default=100)),
                ("activa", models.BooleanField(db_index=True, default=True)),
                ("categoria", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subcategorias", to="el_catalogo.categoriaproveedor")),
            ],
            options={
                "db_table": "catalogo_subcategoria_proveedor",
                "ordering": ["categoria__orden", "orden", "nombre"],
                "verbose_name": "subcategoría de proveedor",
                "verbose_name_plural": "subcategorías de proveedor",
            },
        ),
        migrations.AddField(
            model_name="proveedor",
            name="subcategorias",
            field=models.ManyToManyField(blank=True, related_name="proveedores", to="el_catalogo.subcategoriaproveedor"),
        ),
        migrations.RunPython(_seed, _noop),
    ]
