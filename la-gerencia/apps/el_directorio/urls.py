from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="directorio-lista"),
    path("nuevo", views.crear, name="directorio-crear"),
    path("<int:pk>/editar", views.editar, name="directorio-editar"),
    path("<int:pk>/bloquear", views.bloquear, name="directorio-bloquear"),
    path("<int:pk>/permisos", views.permisos, name="directorio-permisos"),
    # S-Directorio-Panel-V1: modal de detalle con tabs.
    path("<int:pk>/panel", views.panel, name="directorio-panel"),
    path("<int:pk>/panel/datos", views.panel_datos, name="directorio-panel-datos"),
    path("<int:pk>/panel/ia", views.panel_ia, name="directorio-panel-ia"),
    path("<int:pk>/panel/ia/forzar", views.ia_forzar, name="directorio-ia-forzar"),
    path("<int:pk>/panel/presupuesto", views.presupuesto, name="directorio-presupuesto"),
    path("<int:pk>/panel/permisos", views.panel_permisos, name="directorio-panel-permisos"),
    # S-LC-Feedback-V5 c7: CRUD de roles personalizados.
    path("roles/", views.roles_lista, name="directorio-roles"),
    path("roles/nuevo", views.rol_nuevo, name="directorio-rol-nuevo"),
    path("roles/<int:pk>/editar", views.rol_editar, name="directorio-rol-editar"),
    path("roles/<int:pk>/borrar", views.rol_borrar, name="directorio-rol-borrar"),
    path("<int:pk>/roles-extra", views.asignar_roles_extra, name="directorio-asignar-roles-extra"),
]
