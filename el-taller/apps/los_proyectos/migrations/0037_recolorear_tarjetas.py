"""Vuelve a repartir el color de las tarjetas de producto, con la regla nueva.

LC 2026-08-18 R2 (Oscar): «sigo viendo en un proyecto de 6 productos: verde,
rojo, amarillo (feo), rojo, rojo, azul… quiero ver más bien en proyectos nuevos
**y existentes** algo variado y colorido».

Los colores guardados por `0036` se repartieron con dos reglas que cambiaron:

- El color del texto salía de concatenar alias + catálogo + descripción y
  buscar en el orden de la LISTA de colores, así que el rojo (que va antes que
  el azul) se llevaba cualquier línea que mencionara «roja» en cualquiera de
  los tres — de ahí los tres rojos del proyecto de Oscar. Ahora manda el alias
  sobre el nombre del catálogo, y dentro de cada texto el color que se menciona
  primero.
- El ámbar chillón era el cuarto en repartirse (el «amarillo feo»); en la lista
  nueva los amarillos bajaron a la segunda mitad.

Así que se re-reparte todo desde cero, proyecto por proyecto y en orden de
captura. Es determinista: correrla dos veces deja lo mismo. Las líneas cuyo
texto dice su color no guardan nada (se pintan de lo que dicen), y su color
cuenta como ocupado para que a las demás no les toque el mismo.
"""

from django.db import migrations


def _recolorear(apps, schema_editor):
    from apps.los_proyectos import colores

    ProyectoProducto = apps.get_model("proyectos", "ProyectoProducto")
    # Los modelos históricos no traen properties: el nombre del catálogo se arma
    # aquí a mano (misma regla que `ProyectoProducto.nombre_catalogo`, sin la
    # variación — para el color basta el nombre del servicio).
    lineas = ProyectoProducto.objects.select_related("servicio").order_by(
        "proyecto_id", "orden", "pk")
    por_proyecto: dict[int, list] = {}
    for linea in lineas:
        por_proyecto.setdefault(linea.proyecto_id, []).append(linea)

    for grupo in por_proyecto.values():
        usados: list[str] = []
        pendientes = []
        for linea in grupo:
            catalogo = linea.servicio.nombre if linea.servicio_id else ""
            nombrado = colores.color_del_texto(
                linea.nombre_proyecto, catalogo, linea.nota)
            if nombrado:
                usados.append(nombrado)
            else:
                pendientes.append(linea)
        for linea in pendientes:
            nuevo = colores.elegir_color_libre(usados)
            usados.append(nuevo)
            if colores.normalizar(linea.color) != nuevo:
                linea.color = nuevo
                linea.save(update_fields=["color"])


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0036_cuenta_en_precios_y_color_tarjeta"),
    ]

    operations = [
        migrations.RunPython(_recolorear, migrations.RunPython.noop),
    ]
