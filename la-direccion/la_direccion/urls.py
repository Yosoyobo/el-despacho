from django.urls import include, path

urlpatterns = [
    path("", include("apps.direccion_home.urls")),
    path("", include("apps.auth_direccion.urls")),
    path("directorio/", include("apps.el_directorio.urls")),
    path("ajustes/", include("apps.los_ajustes.urls")),
    path("legal/", include("apps.legal.urls")),
]
