"""El montaje de La Caja tal como lo hace El Taller (en la raíz, namespace `caja`).

Existe para `LinkPago.ruta_publica`: la URL pública de pago se arma también
desde procesos que NO sirven las rutas de El Taller —La Recepción (el botón
«Pagar» del portal de clientes), los correos que salen de La Gerencia o de un
comando—. Con el urlconf del proceso, `reverse("caja:pagar")` truena ahí y
`url_pago` se callaba con `None`: el portal nunca enseñaba el botón. Contra este
urlconf fijo sale la misma ruta que en El Taller (hay candado que lo compara).
"""

from django.urls import include, path

urlpatterns = [
    path("", include("apps.caja.urls", namespace="caja")),
]
