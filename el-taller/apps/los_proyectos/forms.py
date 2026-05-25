from apps.el_catalogo.models import Servicio, Variacion
from apps.la_cartera.models import Cliente
from apps.los_proyectos.models import (
    ESTADOS_PROYECTO,
    EstadoProyecto,
    Proyecto,
    ProyectoAsignacion,
    ProyectoProducto,
)
from django import forms
from django.forms import inlineformset_factory

from cuentas.models.usuario import Usuario


class ProyectoForm(forms.ModelForm):
    cliente = forms.ModelChoiceField(queryset=Cliente.activos.all())
    estado = forms.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = _choices_estado_activos()

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
            # S-LC-Feedback-V4: autocomplete @#$ en nombre y descripción.
            "nombre": forms.TextInput(attrs={"data-referencias": "1"}),
            "descripcion": forms.Textarea(attrs={"data-referencias": "1", "rows": 4}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_compromiso": forms.DateInput(attrs={"type": "date"}),
        }


def _choices_estado_activos():
    try:
        return [(e.slug, e.label) for e in EstadoProyecto.objects.filter(activo=True).order_by("orden")]
    except Exception:
        return list(ESTADOS_PROYECTO)


class CambiarEstadoForm(forms.Form):
    estado = forms.ChoiceField(choices=[])
    fecha_real_entrega = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = _choices_estado_activos()


class EditarFechasForm(forms.ModelForm):
    """S-LC-Feedback-V5 c4 — edición rápida de fechas desde el detalle."""

    class Meta:
        model = Proyecto
        fields = ["fecha_inicio", "fecha_compromiso", "fecha_real_entrega"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_compromiso": forms.DateInput(attrs={"type": "date"}),
            "fecha_real_entrega": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "fecha_inicio": "Inicio",
            "fecha_compromiso": "Compromiso",
            "fecha_real_entrega": "Entrega real",
        }


class EditarEconomicoForm(forms.ModelForm):
    """S-LC-Feedback-V5 c4 — edición rápida del bloque económico."""

    class Meta:
        model = Proyecto
        fields = ["monto_estimado", "monto_cotizado", "monto_facturado"]
        labels = {
            "monto_estimado": "Monto estimado",
            "monto_cotizado": "Monto cotizado",
            "monto_facturado": "Monto facturado",
        }


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
    extra=1, can_delete=True,
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
