from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.taller_home.urls")),
    path("", include("apps.auth_taller.urls")),
    path("legal/", include("apps.legal.urls")),
    path("cartera/", include("apps.la_cartera.urls")),
    path("proyectos/", include("apps.los_proyectos.urls")),
    path("", include("apps.el_pizarron.urls")),
]
