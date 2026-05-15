from django.urls import path

from . import views

app_name = "google_oauth"

urlpatterns = [
    path("auth/google/iniciar", views.iniciar, name="iniciar"),
    path("auth/google/callback", views.callback, name="callback"),
]
