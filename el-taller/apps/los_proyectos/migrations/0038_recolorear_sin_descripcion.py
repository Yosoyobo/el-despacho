"""La descripción deja de decidir el color de la tarjeta (LC 2026-09-28, Oscar).

Decisión literal: «sólo alias y catálogo». Hasta hoy una línea cuya
DESCRIPCIÓN mencionaba un color («impresión sobre la playera roja de
siempre») se pintaba de ése, aunque el producto no lo fuera. Esas líneas no
guardaban color propio —0036/0037 las saltaban porque «se pintan de lo que
dicen»—, así que al quitar la regla quedarían con un color viejo o vacío y,
peor, podrían repetir el de una hermana.

Esta migración toca **sólo esas líneas**: las que el texto ya no pinta (ni el
alias ni el nombre del catálogo mencionan color) pero la descripción sí. Las
demás no se mueven — un color que ya se ve «sólidamente ligado» no cambia por
arreglar el de otra tarjeta.

Por cada una, proyecto por proyecto y en orden de captura:
- si su color guardado es válido y ninguna hermana lo ocupa, se queda;
- si no, toma el primero LIBRE de la lista (misma regla que `elegir_color_libre`).

Ocupados cuentan: el color que ven las demás líneas con la regla NUEVA (el que
dice su alias o su nombre del catálogo, o si no, el guardado) y el que ya se le
dio a las líneas que se arreglaron antes en esta misma corrida.

Determinista e idempotente: correrla dos veces deja lo mismo, porque la segunda
vez cada línea encuentra su color guardado libre y lo conserva.
"""

from django.db import migrations


def _nombre_catalogo(linea) -> str:
    # Los modelos históricos no traen properties: se arma aquí a mano con la
    # misma regla que `ProyectoProducto.nombre_catalogo` (sin la higiene de la
    # variación, que para el color no cambia nada: sólo importa si menciona uno).
    nombre = linea.servicio.nombre if linea.servicio_id else ""
    if linea.variacion_id and linea.variacion is not None:
        nombre = f"{nombre} {linea.variacion.nombre or ''}"
    return nombre


def _recolorear(apps, schema_editor):
    from apps.los_proyectos import colores

    ProyectoProducto = apps.get_model("proyectos", "ProyectoProducto")
    lineas = ProyectoProducto.objects.select_related("servicio", "variacion").order_by(
        "proyecto_id", "orden", "pk")
    por_proyecto: dict[int, list] = {}
    for linea in lineas:
        por_proyecto.setdefault(linea.proyecto_id, []).append(linea)

    for grupo in por_proyecto.values():
        usados: list[str] = []
        pendientes = []
        for linea in grupo:
            catalogo = _nombre_catalogo(linea)
            nombrado = colores.color_del_texto(linea.nombre_proyecto, catalogo)
            if nombrado:
                usados.append(nombrado)
                continue
            if colores.color_del_texto(linea.nota):
                # Su color salía de la descripción: se arregla abajo.
                pendientes.append(linea)
                continue
            guardado = colores.normalizar(linea.color)
            usados.append(guardado or colores.color_estable(
                (linea.nombre_proyecto or "").strip() or catalogo))
        for linea in pendientes:
            guardado = colores.normalizar(linea.color)
            if guardado and guardado not in {u.lower() for u in usados}:
                usados.append(guardado)
                continue
            nuevo = colores.elegir_color_libre(usados)
            usados.append(nuevo)
            if guardado != nuevo:
                linea.color = nuevo
                linea.save(update_fields=["color"])


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0037_recolorear_tarjetas"),
    ]

    operations = [
        migrations.RunPython(_recolorear, migrations.RunPython.noop),
    ]
