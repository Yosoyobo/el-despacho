from django.urls import path

from . import views

app_name = "recados"

urlpatterns = [
    path("", views.bandeja, name="bandeja"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/leido/", views.marcar_leido, name="marcar_leido"),
]
