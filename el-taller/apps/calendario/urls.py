from django.urls import path

from . import views

urlpatterns = [
    path("", views.calendario, name="calendario-index"),
    path("dia/<str:fecha_iso>/", views.dia_popover, name="calendario-dia"),
    path("nuevo/", views.nuevo_evento_modal, name="calendario-nuevo-evento"),
    path("resumen/", views.resumen_modal, name="calendario-resumen"),
]
