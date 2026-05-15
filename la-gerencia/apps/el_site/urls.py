from django.urls import path

from . import views

urlpatterns = [
    path("", views.tablero, name="site-tablero"),
    path("partial/infra", views.partial_infra, name="site-partial-infra"),
    path("partial/integraciones", views.partial_integraciones, name="site-partial-integraciones"),
    path("partial/internos", views.partial_internos, name="site-partial-internos"),
    path("probar/<slug:plataforma>", views.probar_plataforma, name="site-probar"),
    path("probar-todas", views.probar_todas, name="site-probar-todas"),
]
