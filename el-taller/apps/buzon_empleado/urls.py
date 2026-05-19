"""URLs del Buzón unificado (Pre-S2b.2).

Layout nuevo:
  /buzon/                 → lista adaptativa
  /buzon/nuevo            → form crear (cualquier autenticado)
  /buzon/<id>/            → detalle adaptativo (admin con form respuesta)
  /buzon/<id>/exportar.md → solo admin (buzon.ver_todos)
  /buzon/clientes/        → placeholder (clientes externos S5)

URLs legacy (mantienen compat — redirects):
  /buzon/mios/        → /buzon/
  /buzon/mios/<id>/   → /buzon/<id>/
"""

from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    # Layout unificado.
    path("buzon/", views.lista, name="buzon-lista"),
    path("buzon/nuevo", views.nuevo, name="buzon-nuevo"),
    path("buzon/clientes/", TemplateView.as_view(template_name="buzon/clientes_proximamente.html"),
         name="buzon-clientes-proximamente"),
    path("buzon/<int:pk>/", views.detalle, name="buzon-detalle"),
    path("buzon/<int:pk>/exportar.md", views.exportar_a_claude, name="buzon-exportar"),

    # Legacy — redirects al layout nuevo.
    path("buzon/mios/", views.mios_lista, name="buzon-empleado-mios"),
    path("buzon/mios/<int:pk>/", views.mios_detalle, name="buzon-empleado-mios-detalle"),
    path("buzon/empleado/nuevo", views.nuevo, name="buzon-empleado-nuevo"),
]
