from django.urls import path

from . import views

urlpatterns = [
    path("sign-in", views.sign_in, name="sign-in"),
    path("sign-out", views.sign_out, name="sign-out"),
    path("auth/google/start", views.google_iniciar, name="google-iniciar"),
    path("auth/google/callback", views.google_callback, name="google-callback"),
]
