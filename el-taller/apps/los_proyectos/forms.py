from apps.el_catalogo.models import Servicio, Variacion
from apps.la_cartera.models import Cliente
from apps.los_proyectos.models import (
    ESTADOS_PROYECTO,
    Proyecto,
    ProyectoAsignacion,
    ProyectoProducto,
)
from django import forms
from django.forms import inlineformset_factory

from cuentas.models.usuario import Usuario


class ProyectoForm(forms.ModelForm):
    cliente = forms.ModelChoiceField(queryset=Cliente.activos.all())

    class Meta:
        model = Proyecto
        fields = [
            "nombre",
            "cliente",
            "descripcion",
            "estado",
            "fecha_inicio",
            "fecha_compromiso",
            "monto_estimado",
        ]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_compromiso": forms.DateInput(attrs={"type": "date"}),
        }


class CambiarEstadoForm(forms.Form):
    estado = forms.ChoiceField(choices=ESTADOS_PROYECTO)
    fecha_real_entrega = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))


class ProyectoProductoForm(forms.ModelForm):
    servicio = forms.ModelChoiceField(
        queryset=Servicio.activos.all().select_related("categoria"),
        required=False,
        empty_label="— Producto del catálogo —",
        label="Producto / servicio",
    )
    variacion = forms.ModelChoiceField(
        queryset=Variacion.objects.filter(disponible=True).select_related("servicio"),
        required=False,
        empty_label="— Sin variación específica —",
        label="Variación",
    )
    cantidad = forms.IntegerField(min_value=1, initial=1, label="Cantidad")

    class Meta:
        model = ProyectoProducto
        fields = ["servicio", "variacion", "cantidad", "nota"]
        labels = {"nota": "Nota corta (opcional)"}


ProyectoProductoFormSet = inlineformset_factory(
    Proyecto, ProyectoProducto, form=ProyectoProductoForm,
    extra=3, can_delete=True,
)
ProyectoProductoFormSetEdit = inlineformset_factory(
    Proyecto, ProyectoProducto, form=ProyectoProductoForm,
    extra=1, can_delete=True,
)


class ClienteInlineForm(forms.ModelForm):
    """Form minimalista para crear un Cliente nuevo desde el modal del form de Proyecto."""

    class Meta:
        model = Cliente
        fields = ["razon_social", "rfc", "nombre_contacto", "email_contacto", "telefono"]


class AsignacionForm(forms.ModelForm):
    usuario = forms.ModelChoiceField(queryset=Usuario.objects.filter(is_active=True).order_by("nombre_completo"))

    class Meta:
        model = ProyectoAsignacion
        fields = ["usuario", "rol_en_proyecto"]
