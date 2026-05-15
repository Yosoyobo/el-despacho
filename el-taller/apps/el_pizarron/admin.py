from apps.el_pizarron.models import Comentario, Tarea
from django.contrib import admin


@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "proyecto", "estado", "prioridad", "asignada_a", "fecha_compromiso")
    list_filter = ("estado", "prioridad")
    search_fields = ("titulo", "proyecto__codigo", "proyecto__nombre")


@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ("__str__", "es_interno", "creado_en")
    list_filter = ("es_interno",)
