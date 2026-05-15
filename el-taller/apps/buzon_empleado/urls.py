from django.urls import path

from . import views

urlpatterns = [
    path("buzon/nuevo", views.nuevo, name="buzon-empleado-nuevo"),
    path("buzon/mios/", views.mios_lista, name="buzon-empleado-mios"),
    path("buzon/mios/<int:pk>/", views.mios_detalle, name="buzon-empleado-mios-detalle"),
]
