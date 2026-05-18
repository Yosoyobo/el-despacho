from django.urls import path

from . import views

app_name = "referencias"

urlpatterns = [
    path("autocomplete/usuarios", views.autocomplete_usuarios, name="autocomplete_usuarios"),
    path("autocomplete/proyectos", views.autocomplete_proyectos, name="autocomplete_proyectos"),
    path("autocomplete/clientes", views.autocomplete_clientes, name="autocomplete_clientes"),
    path("referencias/usuarios/<int:usuario_id>", views.busqueda_inversa_usuarios, name="busqueda_usuarios"),
    path("referencias/proyectos/<int:proyecto_id>", views.busqueda_inversa_proyectos, name="busqueda_proyectos"),
    path("referencias/clientes/<int:cliente_id>", views.busqueda_inversa_clientes, name="busqueda_clientes"),
]
