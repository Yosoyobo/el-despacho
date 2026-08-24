from django.urls import path

from . import views

app_name = "cotizaciones"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nueva/", views.nuevo, name="nuevo"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/enviar/", views.enviar, name="enviar"),
    path("<int:pk>/ya-la-mande/", views.enviada_manual, name="enviada-manual"),
    path("<int:pk>/aprobar/", views.aprobar, name="aprobar"),
    path("<int:pk>/rechazar/", views.rechazar, name="rechazar"),
    path("<int:pk>/anular/", views.anular, name="anular"),
    path("<int:pk>/eliminar/", views.eliminar, name="eliminar"),
    path("<int:pk>/duplicar/", views.duplicar, name="duplicar"),
    path("<int:pk>/ver/", views.pdf_ver, name="ver"),
    path("<int:pk>/pdf/", views.generar_pdf, name="pdf"),
    path("<int:pk>/estado-inline/", views.estado_inline, name="estado-inline"),
    # Semáforo de la PÁGINA de la cotización (LC 2026-08-23). Mismo partial que
    # el recuadro del proyecto; sólo cambia a dónde postea y qué repinta.
    path("<int:pk>/semaforo/", views.semaforo, name="semaforo"),
    # LC 2026-07: corregir el texto del documento (concepto/especificaciones)
    # desde la página de la cotización. `pk` es de la LÍNEA, no de la cotización.
    path("items/<int:pk>/celda/", views.item_celda, name="item-celda"),
    path("<int:pk>/documento/", views.documento_opciones, name="documento-opciones"),
    path("<int:pk>/factura-anticipo/", views.factura_anticipo, name="factura-anticipo"),
    path("api/proyecto/<int:pk>/datos/", views.api_proyecto_datos, name="api-proyecto-datos"),
    path("api/sugerir-precio/", views.sugerir_precio, name="api-sugerir-precio"),
]
