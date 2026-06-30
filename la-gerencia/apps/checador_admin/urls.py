from django.urls import path

from . import views

urlpatterns = [
    path("gerencia/geocoding", views.geocoding_buscar, name="gerencia-geocoding"),
    # Alias canónico del geo-picker (cuadro de resultados en vivo + POIs).
    path("geo/buscar", views.geocoding_buscar, name="geo-buscar"),
    path("catalogos/horarios/", views.horarios, name="checador-admin-horarios"),
    path("catalogos/horarios/nuevo/", views.horario_nuevo, name="checador-admin-horario-nuevo"),
    path("catalogos/horarios/<int:pk>/editar/", views.horario_editar, name="checador-admin-horario-editar"),
    path("catalogos/horarios/<int:pk>/borrar/", views.horario_borrar, name="checador-admin-horario-borrar"),
    path("catalogos/sedes/", views.sedes, name="checador-admin-sedes"),
    path("catalogos/sedes/nueva/", views.sede_nuevo, name="checador-admin-sede-nueva"),
    path("catalogos/sedes/<int:pk>/editar/", views.sede_editar, name="checador-admin-sede-editar"),
    path("catalogos/sedes/<int:pk>/borrar/", views.sede_borrar, name="checador-admin-sede-borrar"),
    path("catalogos/sedes/geocerca/", views.geocerca_config, name="checador-admin-geocerca"),
    path("checador/correcciones/", views.correcciones, name="checador-admin-correcciones"),
    path("checador/correcciones/<int:pk>/resolver/modal", views.correccion_resolver_modal, name="checador-admin-correccion-resolver-modal"),
    path("checador/correcciones/<int:pk>/resolver", views.correccion_resolver, name="checador-admin-correccion-resolver"),
]
