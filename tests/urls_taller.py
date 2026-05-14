"""URLconf de pruebas: monta solo El Taller (los S1b CRUDs)."""
from django.urls import include, path

urlpatterns = [
    path("", include("apps.taller_home.urls")),
    path("", include("apps.auth_taller.urls")),
    path("legal/", include("apps.legal.urls")),
    path("cartera/", include("apps.la_cartera.urls")),
    path("proyectos/", include("apps.los_proyectos.urls")),
    path("", include("apps.el_pizarron.urls")),
]
