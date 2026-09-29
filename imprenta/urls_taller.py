from django.urls import path

from . import views_taller

app_name = "imprenta"

urlpatterns = [
    path("<slug:tipo>/<int:pk>/", views_taller.ver, name="ver"),
    path("<slug:tipo>/<int:pk>/pdf/", views_taller.pdf, name="pdf"),
]
