"""La cuenta escrita en los precios + el color ligado a cada tarjeta.

LC 2026-08-18 (Oscar). Dos cosas, las dos aditivas:

1. `*_expr` en los campos de precio (línea, escala, proceso de venta y la foto
   por versión). El costo ya conservaba la cuenta escrita desde 2026-08-12;
   ahora el precio hace lo mismo, así que «150+45» se sigue leyendo «150+45» al
   volver mañana.
2. `ProyectoProducto.color`: el color de la tarjeta deja de calcularse al vuelo
   y se GUARDA con la línea — es lo que lo vuelve inamovible. La data migration
   reparte los colores de las líneas que ya existen, proyecto por proyecto y en
   orden de captura, saltándose las que ya tienen un color en su nombre (esas se
   pintan del color que dicen, no hace falta guardarles nada).
"""

from django.db import migrations, models


def _repartir_colores(apps, schema_editor):
    from apps.los_proyectos import colores

    ProyectoProducto = apps.get_model("proyectos", "ProyectoProducto")
    # Los modelos históricos no traen properties, así que el nombre visible se
    # arma aquí a mano (misma regla que `ProyectoProducto.nombre_visible`).
    lineas = ProyectoProducto.objects.select_related("servicio").order_by(
        "proyecto_id", "orden", "pk")
    por_proyecto: dict[int, list] = {}
    for linea in lineas:
        por_proyecto.setdefault(linea.proyecto_id, []).append(linea)

    for grupo in por_proyecto.values():
        usados: list[str] = []
        pendientes = []
        # Primera pasada: las que ya dicen su color lo ocupan, para que a las
        # demás no se les reparta el mismo.
        for linea in grupo:
            nombre = (linea.nombre_proyecto or "").strip()
            if not nombre and linea.servicio_id:
                nombre = linea.servicio.nombre
            nombrado = colores.color_del_texto(nombre, linea.nota)
            if nombrado:
                usados.append(nombrado)
            elif not colores.normalizar(linea.color):
                pendientes.append(linea)
            else:
                usados.append(colores.normalizar(linea.color))
        for linea in pendientes:
            linea.color = colores.elegir_color_libre(usados)
            usados.append(linea.color)
            linea.save(update_fields=["color"])


def _sin_colores(apps, schema_editor):
    """Al revés se limpian: el campo desaparece con el `RemoveField`."""


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0035_escalas_volumen"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectoproducto",
            name="precio_unitario_expr",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="proyectoproducto",
            name="color",
            field=models.CharField(blank=True, default="", max_length=7),
        ),
        migrations.AddField(
            model_name="proyectoproductoescala",
            name="precio_unitario_expr",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="proyectoproductoventa",
            name="precio_expr",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="proyectoproductoversion",
            name="precio_unitario_expr",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="proyectoproductoversion",
            name="color",
            field=models.CharField(blank=True, default="", max_length=7),
        ),
        migrations.RunPython(_repartir_colores, _sin_colores),
    ]
