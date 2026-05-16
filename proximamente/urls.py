from django.urls import path

from . import views

app_name = "proximamente"

urlpatterns = [
    path("", views.indice, name="indice"),
    path("<slug:modulo>/", views.modulo, name="modulo"),
]
