from apps.los_proyectos.models import Proyecto, ProyectoAsignacion
from django.contrib import admin


class AsignacionInline(admin.TabularInline):
    model = ProyectoAsignacion
    extra = 0


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "nombre", "cliente", "estado",
        "fecha_compromiso", "monto_estimado", "monto_facturado", "creado_en",
    )
    list_filter = ("estado", "fecha_ingreso_esperado")
    search_fields = ("codigo", "nombre", "cliente__razon_social")
    inlines = [AsignacionInline]
    readonly_fields = ("creado_en", "actualizado_en", "creado_por", "codigo")
    fieldsets = (
        (None, {
            "fields": ("codigo", "nombre", "cliente", "descripcion", "estado", "creado_por"),
        }),
        ("Fechas", {
            "fields": ("fecha_inicio", "fecha_compromiso", "fecha_real_entrega"),
        }),
        ("Montos del ciclo comercial", {
            "fields": (
                "monto_estimado", "monto_cotizado",
                "monto_facturado", "monto_cobrado",
                "fecha_ingreso_esperado",
            ),
            "description": (
                "Monto estimado es inicial. Los demás se llenan conforme avanza "
                "el ciclo comercial. En S2b llegan flujos automáticos; por ahora "
                "la captura es manual."
            ),
        }),
        ("Auditoría", {
            "fields": ("creado_en", "actualizado_en"),
        }),
    )


@admin.register(ProyectoAsignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ("proyecto", "usuario", "rol_en_proyecto", "asignado_en")
    list_filter = ("rol_en_proyecto",)
