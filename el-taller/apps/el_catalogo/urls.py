from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="catalogo-lista"),
    path("nuevo", views.nuevo, name="catalogo-nuevo"),
    path("<int:pk>/editar", views.editar, name="catalogo-editar"),
    path("<int:pk>/celda", views.servicio_celda, name="catalogo-servicio-celda"),
    path("<int:pk>/imagen", views.servicio_imagen, name="catalogo-servicio-imagen"),
    path("<int:pk>/archivar", views.archivar, name="catalogo-archivar"),
    path("<int:pk>/eliminar", views.servicio_eliminar, name="catalogo-eliminar"),
    path("<int:pk>/variaciones/", views.variaciones_lista, name="catalogo-variaciones"),
    path("<int:pk>/variaciones/nueva", views.variacion_nueva, name="catalogo-variacion-nueva"),
    path("<int:pk>/variaciones/<int:vpk>/editar", views.variacion_editar, name="catalogo-variacion-editar"),
    path("<int:pk>/variaciones/<int:vpk>/archivar", views.variacion_archivar, name="catalogo-variacion-archivar"),
    path("categorias/", views.categorias_lista, name="catalogo-categorias"),
    path("categorias/nueva", views.categoria_nueva, name="catalogo-categoria-nueva"),
    path("categorias/<int:pk>/editar", views.categoria_editar, name="catalogo-categoria-editar"),
    path("categorias/<int:pk>/borrar", views.categoria_borrar, name="catalogo-categoria-borrar"),
    # LC 2026-07: categorías CORE de proveedor (6, editables — color heredado por subcategorías)
    path("categorias-proveedor/", views.categorias_proveedor_lista, name="catalogo-categorias-proveedor"),
    path("categorias-proveedor/<int:pk>/editar", views.categoria_proveedor_editar, name="catalogo-categoria-proveedor-editar"),
    # LC #164: CRUD de las 19 subcategorías de proveedor.
    path("categorias-proveedor/subcategorias/nueva", views.subcategoria_proveedor_nueva, name="catalogo-subcategoria-proveedor-nueva"),
    path("categorias-proveedor/subcategorias/<int:pk>/editar", views.subcategoria_proveedor_editar, name="catalogo-subcategoria-proveedor-editar"),
    # S-LC-Feedback-V2: catálogo de unidades de medida
    path("unidades/", views.unidades_lista, name="catalogo-unidades"),
    path("unidades/nueva", views.unidad_nueva, name="catalogo-unidad-nueva"),
    path("unidades/<int:pk>/editar", views.unidad_editar, name="catalogo-unidad-editar"),
    path("unidades/<int:pk>/archivar", views.unidad_archivar, name="catalogo-unidad-archivar"),
    # S-LC-Feedback-V2: quick-create de Servicio desde el form de Proyecto
    path("quick-create/", views.servicio_quick_create, name="catalogo-quick-create"),
    # S-LC-Feedback-V3: CRM de proveedores
    path("proveedores/", views.proveedores_lista, name="catalogo-proveedores"),
    path("proveedores/nuevo", views.proveedor_nuevo, name="catalogo-proveedor-nuevo"),
    # S-LC-Feedback-V5: quick-create inline desde el form de Servicio
    path("proveedores/quick-create/", views.proveedor_quick_create, name="catalogo-proveedor-quick-create"),
    path("proveedores/buscar/", views.proveedor_buscar, name="catalogo-proveedor-buscar"),
    # S-Chalanes-UX hotfix: El Chalán sugiere proveedores por historial.
    path("sugerir-proveedores/", views.sugerir_proveedores, name="catalogo-sugerir-proveedores"),
    path("proveedores/<int:pk>/", views.proveedor_detalle, name="catalogo-proveedor-detalle"),
    path("proveedores/<int:pk>/editar", views.proveedor_editar, name="catalogo-proveedor-editar"),
    path("proveedores/<int:pk>/servicios", views.proveedor_servicios, name="catalogo-proveedor-servicios"),
    path("proveedores/<int:pk>/archivar", views.proveedor_archivar, name="catalogo-proveedor-archivar"),
    path("proveedores/<int:pk>/eliminar", views.proveedor_eliminar, name="catalogo-proveedor-eliminar"),
]
