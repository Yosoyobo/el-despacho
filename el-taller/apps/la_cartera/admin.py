from django.contrib import admin

from apps.la_cartera.models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "rfc", "estado", "activo", "creado_en")
    list_filter = ("estado", "activo")
    search_fields = ("razon_social", "rfc", "email_contacto", "nombre_contacto")
    readonly_fields = ("creado_en", "actualizado_en", "creado_por")
