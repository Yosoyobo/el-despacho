from apps.la_cartera.models import Cliente
from apps.los_proyectos.models import ESTADOS_PROYECTO, Proyecto, ProyectoAsignacion
from django import forms

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


class AsignacionForm(forms.ModelForm):
    usuario = forms.ModelChoiceField(queryset=Usuario.objects.filter(is_active=True).order_by("nombre_completo"))

    class Meta:
        model = ProyectoAsignacion
        fields = ["usuario", "rol_en_proyecto"]
