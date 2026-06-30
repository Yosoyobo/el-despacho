from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="proyectos-lista"),
    path("kanban/", views.kanban, name="proyectos-kanban"),
    path("nuevo", views.nuevo, name="proyectos-nuevo"),
    path("cliente-nuevo/", views.cliente_inline, name="proyectos-cliente-inline"),
    path("<int:pk>/", views.detalle, name="proyectos-detalle"),
    path("<int:pk>/editar", views.editar, name="proyectos-editar"),
    path("<int:pk>/cambiar-estado", views.cambiar_estado, name="proyectos-cambiar-estado"),
    path("<int:pk>/resumir-actividad", views.resumen_actividad, name="proyectos-resumir-actividad"),
    path("<int:pk>/asignar", views.asignar, name="proyectos-asignar"),
    # S-LC-Feedback-V5 c4: quick-edits inline desde el detalle.
    path("<int:pk>/editar-fechas", views.editar_fechas, name="proyectos-editar-fechas"),
    path("<int:pk>/editar-economico", views.editar_economico, name="proyectos-editar-economico"),
    path("<int:pk>/agregar-tarea", views.agregar_tarea_modal, name="proyectos-agregar-tarea"),
    path("<int:pk>/agregar-producto", views.agregar_producto_modal, name="proyectos-agregar-producto"),
    path("<int:pk>/quitar-producto/<int:prod_pk>", views.quitar_producto, name="proyectos-quitar-producto"),
    # Recuadro «Cotizaciones» del proyecto (versionado, render Oscar 2026-06-27).
    path("<int:pk>/cotizacion/generar", views.generar_cotizacion, name="proyectos-generar-cotizacion"),
    path("<int:pk>/cotizacion/estado", views.cotizacion_estado, name="proyectos-cotizacion-estado"),
    path("<int:pk>/cotizacion/anticipo", views.registrar_anticipo_modal, name="proyectos-registrar-anticipo"),
    # C5 S-LC-Feedback-V6: proveedores asignados al proyecto.
    path("<int:pk>/agregar-proveedor", views.agregar_proveedor_modal, name="proyectos-agregar-proveedor"),
    path("<int:pk>/quitar-proveedor/<int:prov_pk>", views.quitar_proveedor, name="proyectos-quitar-proveedor"),
    path("<int:pk>/proveedor-iva/<int:prov_pk>", views.toggle_proveedor_iva, name="proyectos-proveedor-iva"),
    # Render-V2: deshacer el último guardado (Undo en Redis).
    path("<int:pk>/deshacer", views.deshacer, name="proyectos-deshacer"),
    # Contabilidad en línea: registrar gastos del proyecto como egresos.
    path("<int:pk>/gasto/<str:clase>/<int:obj_pk>/registrar-modal", views.registrar_gasto_modal, name="proyectos-registrar-gasto-modal"),
    path("<int:pk>/gasto/<str:clase>/<int:obj_pk>/registrar", views.registrar_gasto, name="proyectos-registrar-gasto"),
    path("<int:pk>/gastos/registrar-todos", views.registrar_gastos_todos, name="proyectos-registrar-gastos-todos"),
]
