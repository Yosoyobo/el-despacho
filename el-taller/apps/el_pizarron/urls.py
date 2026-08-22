from django.urls import path

from . import views

urlpatterns = [
    # V6 Bloque 2: el default de /tareas/ es el Kanban (mis tareas).
    path("tareas/", views.kanban_tareas, name="tareas-kanban"),
    path("tareas/lista/", views.lista_tareas, name="tareas-lista"),
    path("tareas/nueva/", views.nueva_tarea_global, name="pizarron-nueva-tarea-global"),
    path("tareas/reordenar", views.reordenar_tareas, name="pizarron-reordenar-tareas"),
    path("proyectos/<int:proyecto_id>/tareas/nueva", views.nueva_tarea, name="pizarron-nueva-tarea"),
    path("proyectos/<int:proyecto_id>/comentar", views.comentar_proyecto, name="pizarron-comentar-proyecto"),
    path("tareas/<int:pk>/", views.detalle_tarea, name="pizarron-detalle-tarea"),
    path("tareas/<int:pk>/editar", views.editar_tarea, name="pizarron-editar-tarea"),
    path("tareas/<int:pk>/eliminar", views.eliminar_tarea, name="pizarron-eliminar-tarea"),
    path("tareas/<int:pk>/archivar", views.archivar_tarea, name="pizarron-archivar-tarea"),
    path("tareas/<int:pk>/editar-rapido", views.editar_tarea_rapido, name="pizarron-editar-tarea-rapido"),
    path("tareas/<int:pk>/comentar", views.comentar_tarea, name="pizarron-comentar-tarea"),
    path("tareas/<int:pk>/completar", views.completar_tarea, name="pizarron-completar-tarea"),
    path("tareas/<int:pk>/cambiar-estado", views.cambiar_estado_tarea, name="pizarron-cambiar-estado"),
    # Geo-picker compartido (cuadro de resultados en vivo + POIs + Nominatim).
    path("geo/buscar", views.geocoding_buscar, name="geo-buscar"),
    # El Runner — Mandados (entregas/recolecciones como entidad logística).
    path("mandados/", views.mandados_lista, name="mandados-lista"),
    # La vuelta del día, ordenada por cercanía + exportar a mapas (2026-08-22).
    path("mandados/mi-ruta/", views.mi_ruta, name="mandados-mi-ruta"),
    path("mandados/geocoding", views.geocoding_buscar, name="mandados-geocoding"),

    # S-Planeador-Rutas: el reparto del día, guardado y reacomodable.
    path("rutas/", views.rutas_panel, name="rutas-panel"),
    path("rutas/planear", views.rutas_planear, name="rutas-planear"),
    path("rutas/<int:pk>/despachar", views.rutas_despachar, name="rutas-despachar"),
    path("rutas/<int:pk>/reordenar", views.rutas_reordenar, name="rutas-reordenar"),
    path("rutas/<int:pk>/cancelar", views.rutas_cancelar, name="rutas-cancelar"),
    path("rutas/paradas/<int:pk>/mover", views.parada_mover, name="rutas-parada-mover"),
    path("mandados/<int:pk>/avanzar", views.mandado_avanzar, name="mandado-avanzar"),
    path("mandados/<int:pk>/destino", views.mandado_destino, name="mandado-destino"),
]
