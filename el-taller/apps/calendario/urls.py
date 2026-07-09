from django.urls import path

from . import views

urlpatterns = [
    path("", views.calendario, name="calendario-index"),
    path("dia/<str:fecha_iso>/", views.dia_popover, name="calendario-dia"),
    path("nuevo/", views.nuevo_evento_modal, name="calendario-nuevo-evento"),
    # S-LC-Feedback-V13: eventos genéricos (feriados, vacaciones, operativos).
    path("evento/nuevo/", views.evento_form, name="calendario-evento-nuevo"),
    path("evento/<int:pk>/", views.evento_form, name="calendario-evento-editar"),
    path("evento/<int:pk>/eliminar", views.evento_eliminar, name="calendario-evento-eliminar"),
    path("resumen/", views.resumen_modal, name="calendario-resumen"),
    # D7 (LC 2026-07): recolocar evento por drag&drop.
    path("mover/", views.mover_evento, name="calendario-mover-evento"),
]
