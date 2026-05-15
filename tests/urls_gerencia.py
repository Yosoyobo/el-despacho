"""URLconf de pruebas: monta solo La Gerencia (Directorio, Ajustes, API/Inventario).

Activar con `@override_settings(ROOT_URLCONF="tests.urls_gerencia")` en tests
marcados con `@pytest.mark.gerencia`.
"""

from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", include("apps.gerencia_home.urls")),
    path("", include("apps.auth_gerencia.urls")),
    path("directorio/", include("apps.el_directorio.urls")),
    path("ajustes/", include("apps.los_ajustes.urls")),
    path("legal/", include("apps.legal.urls")),
    path("catalogo/", include("apps.el_catalogo.urls")),
    path("buzon/clientes/", TemplateView.as_view(template_name="buzon_admin/clientes_proximamente.html"),
         name="buzon-admin-clientes-proximamente"),
    path("buzon/", include("apps.buzon_admin.urls")),
    path("", include("apps.api.urls")),
]
