from django.urls import include, path

# El admin de Django vive solo en La Gerencia (Django project con `django.contrib.admin`
# en INSTALLED_APPS). El Taller no lo necesita y no tiene la app instalada.
urlpatterns = [
    path("", include("apps.taller_home.urls")),
    path("", include("apps.auth_taller.urls")),
    path("legal/", include("apps.legal.urls")),
    path("cartera/", include("apps.la_cartera.urls")),
    path("proyectos/", include("apps.los_proyectos.urls")),
    path("", include("apps.el_pizarron.urls")),
]
