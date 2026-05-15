from apps.los_proyectos.models import Proyecto, ProyectoAsignacion
from django.contrib import admin


class AsignacionInline(admin.TabularInline):
    model = ProyectoAsignacion
    extra = 0


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "cliente", "estado", "fecha_compromiso", "creado_en")
    list_filter = ("estado",)
    search_fields = ("codigo", "nombre", "cliente__razon_social")
    inlines = [AsignacionInline]
    readonly_fields = ("creado_en", "actualizado_en", "creado_por", "codigo")


@admin.register(ProyectoAsignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ("proyecto", "usuario", "rol_en_proyecto", "asignado_en")
    list_filter = ("rol_en_proyecto",)
