"""URLconf del API JSON interno.

`/inventario-de-endpoints/` monta Swagger UI con sidecar (assets servidos
desde el container, sin CDN). El esquema OpenAPI se sirve en
`/inventario-de-endpoints/schema/`. Ambos requieren super_admin.
"""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .permissions import SoloSuperAdmin
from .views.info import InfoApiView

urlpatterns = [
    path("api/info/", InfoApiView.as_view(), name="api-info"),
    path(
        "inventario-de-endpoints/schema/",
        SpectacularAPIView.as_view(permission_classes=[SoloSuperAdmin]),
        name="inventario-schema",
    ),
    path(
        "inventario-de-endpoints/",
        SpectacularSwaggerView.as_view(
            url_name="inventario-schema",
            permission_classes=[SoloSuperAdmin],
        ),
        name="inventario-swagger",
    ),
]
