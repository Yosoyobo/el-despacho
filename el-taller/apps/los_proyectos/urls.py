from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="proyectos-lista"),
    path("kanban/", views.kanban, name="proyectos-kanban"),
    # LC 2026-08-07: por qué se cancelan los proyectos (lista + captura del motivo).
    path("cancelaciones/", views.cancelaciones, name="proyectos-cancelaciones"),
    path("<int:pk>/motivo-cancelacion", views.motivo_cancelacion, name="proyectos-motivo-cancelacion"),
    path("nuevo", views.nuevo, name="proyectos-nuevo"),
    path("cliente-nuevo/", views.cliente_inline, name="proyectos-cliente-inline"),
    path("<int:pk>/", views.detalle, name="proyectos-detalle"),
    path("<int:pk>/editar", views.editar, name="proyectos-editar"),
    path("<int:pk>/duplicar", views.duplicar, name="proyectos-duplicar"),
    path("<int:pk>/cambiar-estado", views.cambiar_estado, name="proyectos-cambiar-estado"),
    # LC 2026-07: archivar (reversible) y eliminar (permanente, super_admin, sin movimientos).
    path("<int:pk>/archivar", views.archivar, name="proyectos-archivar"),
    path("<int:pk>/eliminar", views.eliminar, name="proyectos-eliminar"),
    path("<int:pk>/resumir-actividad", views.resumen_actividad, name="proyectos-resumir-actividad"),
    path("<int:pk>/asignar", views.asignar, name="proyectos-asignar"),
    # S-LC-Feedback-V5 c4: quick-edits inline desde el detalle.
    path("<int:pk>/editar-fechas", views.editar_fechas, name="proyectos-editar-fechas"),
    path("<int:pk>/editar-economico", views.editar_economico, name="proyectos-editar-economico"),
    path("<int:pk>/agregar-tarea", views.agregar_tarea_modal, name="proyectos-agregar-tarea"),
    # Mini-Chalán de tareas (LC 2026-07-29): dictar → preview → confirmar.
    path("<int:pk>/tareas-chalan", views.tareas_chalan_modal, name="proyectos-tareas-chalan"),
    path("<int:pk>/tareas-chalan/aplicar", views.tareas_chalan_aplicar, name="proyectos-tareas-chalan-aplicar"),
    path("<int:pk>/agregar-producto", views.agregar_producto_modal, name="proyectos-agregar-producto"),
    path("<int:pk>/quitar-producto/<int:prod_pk>", views.quitar_producto, name="proyectos-quitar-producto"),
    # LC Fase 2: persistir el orden (drag & drop) de las tarjetas de producto.
    # LC 2026-08-04 R3: orden manual de las tarjetas del Kanban (compartido).
    path("reordenar-kanban", views.reordenar_kanban, name="proyectos-reordenar-kanban"),
    path("<int:pk>/reordenar-productos", views.reordenar_productos, name="proyectos-reordenar-productos"),
    # LC 2026-08-13 (Deploy B): pestañas por versión de «Productos involucrados».
    # RECONSTRUIDO tras un `git reset --hard` accidental: los nombres y la firma
    # salen de `views.productos_version` / `views.version_restaurar` y de lo que
    # piden `_productos_tabs.html`, `_productos_version.html` y su test.
    path("<int:pk>/productos/version/<int:cot_pk>", views.productos_version, name="proyectos-productos-version"),
    path("<int:pk>/productos/version/<int:cot_pk>/restaurar", views.version_restaurar, name="proyectos-version-restaurar"),
    # LC 2026-08-04 (Oscar): «⧉» de la tarjeta — clona la línea con sus procesos.
    path("<int:pk>/duplicar-producto/<int:prod_pk>", views.duplicar_producto, name="proyectos-duplicar-producto"),
    # LC 2026-07-26: foto del producto desde la tarjeta del proyecto (pegar o
    # subir). `prod_pk` es de la LÍNEA — el destino (uso vs catálogo) lo decide
    # el alias, así que no hace falta pasarlo por la URL.
    path("producto/<int:prod_pk>/imagen", views.producto_imagen, name="proyectos-producto-imagen"),
    # Revisión buzón R2: mini-Chalán del quick-create aplica los productos confirmados.
    path("<int:pk>/productos-ia-aplicar", views.proyecto_productos_ia_aplicar, name="proyectos-productos-ia-aplicar"),
    # Recuadro «Cotizaciones» del proyecto (versionado, render Oscar 2026-06-27).
    path("<int:pk>/cotizacion/vista-previa", views.previsualizar_cotizacion, name="proyectos-previsualizar-cotizacion"),
    path("<int:pk>/cotizacion/generar", views.generar_cotizacion, name="proyectos-generar-cotizacion"),
    path("<int:pk>/cotizacion/estado", views.cotizacion_estado, name="proyectos-cotizacion-estado"),
    # Escalas de volumen (LC 2026-08-17): el modal que pide dejar UNA sola
    # cantidad al aprobar, y el que ofrece aprobar la cotización cuando el
    # proyecto ya entró a producción.
    path("<int:pk>/escalas/elegir", views.escalas_elegir, name="proyectos-escalas-elegir"),
    path("<int:pk>/cotizacion/aprobar-modal", views.modal_aprobar_cotizacion, name="proyectos-modal-aprobar-cotizacion"),
    path("<int:pk>/cotizacion/anticipo", views.registrar_anticipo_modal, name="proyectos-registrar-anticipo"),
    path("<int:pk>/cotizacion/anticipo/vincular", views.vincular_ingreso_anticipo, name="proyectos-vincular-ingreso-anticipo"),
    # C5 S-LC-Feedback-V6: proveedores asignados al proyecto.
    path("<int:pk>/agregar-proveedor", views.agregar_proveedor_modal, name="proyectos-agregar-proveedor"),
    path("<int:pk>/quitar-proveedor/<int:prov_pk>", views.quitar_proveedor, name="proyectos-quitar-proveedor"),
    path("<int:pk>/proveedor-iva/<int:prov_pk>", views.toggle_proveedor_iva, name="proyectos-proveedor-iva"),
    path("<int:pk>/gasto/<int:proc_pk>/proveedor", views.ligar_gasto_proveedor, name="proyectos-ligar-gasto-proveedor"),
    # Render-V2: deshacer el último guardado (Undo en Redis).
    path("<int:pk>/deshacer", views.deshacer, name="proyectos-deshacer"),
    # Contabilidad en línea: registrar gastos del proyecto como egresos.
    path("<int:pk>/gasto/<str:clase>/<int:obj_pk>/registrar-modal", views.registrar_gasto_modal, name="proyectos-registrar-gasto-modal"),
    # LC 2026-07-26: pago de TODO lo pendiente de un proveedor (clave 0 = sin
    # proveedor asignado). Un solo egreso por proveedor.
    path("<int:pk>/pago-proveedor/<int:clave>/registrar", views.registrar_pago_proveedor_modal, name="proyectos-registrar-pago-proveedor"),
    path("<int:pk>/gasto/<str:clase>/<int:obj_pk>/registrar", views.registrar_gasto, name="proyectos-registrar-gasto"),
    path("<int:pk>/gastos/registrar-todos", views.registrar_gastos_todos, name="proyectos-registrar-gastos-todos"),
]
