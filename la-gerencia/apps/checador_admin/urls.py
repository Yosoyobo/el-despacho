from django.urls import path

from . import views

urlpatterns = [
    path("catalogos/horarios/", views.horarios, name="checador-admin-horarios"),
    path("catalogos/horarios/nuevo/", views.horario_nuevo, name="checador-admin-horario-nuevo"),
    path("catalogos/horarios/<int:pk>/editar/", views.horario_editar, name="checador-admin-horario-editar"),
    path("catalogos/horarios/<int:pk>/borrar/", views.horario_borrar, name="checador-admin-horario-borrar"),
    path("checador/correcciones/", views.correcciones, name="checador-admin-correcciones"),
    path("checador/correcciones/<int:pk>/resolver/modal", views.correccion_resolver_modal, name="checador-admin-correccion-resolver-modal"),
    path("checador/correcciones/<int:pk>/resolver", views.correccion_resolver, name="checador-admin-correccion-resolver"),
]
