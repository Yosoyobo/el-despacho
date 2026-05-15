from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="ajustes-panel"),
    path("guardar", views.guardar, name="ajustes-guardar"),
    path("<slug:clave>/probar", views.probar, name="ajustes-probar"),
    path("tasas/", views.tasas_lista, name="ajustes-tasas"),
    path("tasas/nueva", views.tasa_nueva, name="ajustes-tasa-nueva"),
    path("tasas/<int:pk>/editar", views.tasa_editar, name="ajustes-tasa-editar"),
]
