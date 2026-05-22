from django.urls import path

from . import views

urlpatterns = [
    path("", views.calendario, name="calendario-index"),
]
