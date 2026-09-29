"""Rutas de La Caja. Se monta en la raíz del Taller porque abarca tres lugares:

  · `/pagar/<token>/…`          la página pública (sin sesión)
  · `/caja/webhook/<pasarela>/` los avisos de Stripe y MercadoPago (sin sesión, con firma)
  · `/tesoreria/caja/…`         la pantalla y los modales del equipo (con permiso)
"""

from django.urls import path

from . import views, views_publicas, webhooks

app_name = "caja"

urlpatterns = [
    # Pública
    path("pagar/<str:firmado>/", views_publicas.pagar, name="pagar"),
    path("pagar/<str:firmado>/stripe/", views_publicas.pagar_con, {"pasarela": "stripe"}, name="pagar-stripe"),
    path("pagar/<str:firmado>/mercadopago/", views_publicas.pagar_con, {"pasarela": "mercadopago"},
         name="pagar-mercadopago"),
    path("pagar/<str:firmado>/gracias/", views_publicas.gracias, name="pagar-gracias"),
    path("pagar/<str:firmado>/cancelado/", views_publicas.cancelado, name="pagar-cancelado"),
    # Webhooks
    path("caja/webhook/stripe/", webhooks.webhook_stripe, name="webhook-stripe"),
    path("caja/webhook/mercadopago/", webhooks.webhook_mercadopago, name="webhook-mercadopago"),
    # Equipo
    path("tesoreria/caja/", views.landing, name="landing"),
    path("tesoreria/caja/links/<int:pk>/", views.link_detalle, name="link-detalle"),
    path("tesoreria/caja/links/<int:pk>/anular/", views.link_anular, name="link-anular"),
    path("tesoreria/caja/links/<int:pk>/correo/", views.link_correo, name="link-correo"),
    path("tesoreria/caja/factura/<int:pk>/", views.link_factura, name="link-factura"),
    path("tesoreria/caja/cotizacion/<int:pk>/", views.link_cotizacion, name="link-cotizacion"),
    path("tesoreria/caja/libre/", views.link_libre, name="link-libre"),
    path("tesoreria/caja/pagos/<int:pk>/revisar/", views.pago_revisar, name="pago-revisar"),
]
