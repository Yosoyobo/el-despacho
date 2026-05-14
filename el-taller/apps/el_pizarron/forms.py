from django import forms

from apps.el_pizarron.models import Comentario, Tarea
from cuentas.models.usuario import Usuario


class TareaForm(forms.ModelForm):
    asignada_a = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(is_active=True).order_by("nombre_completo"),
        required=False,
        empty_label="— sin asignar —",
    )

    class Meta:
        model = Tarea
        fields = ["titulo", "descripcion", "estado", "prioridad", "asignada_a", "fecha_compromiso"]
        widgets = {
            "fecha_compromiso": forms.DateInput(attrs={"type": "date"}),
        }


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ["cuerpo", "es_interno"]
