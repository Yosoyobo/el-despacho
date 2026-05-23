from apps.el_pizarron.models import Comentario, Tarea
from django import forms

from cuentas.models.usuario import Usuario


class TareaForm(forms.ModelForm):
    asignada_a = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(is_active=True).order_by("nombre_completo"),
        required=True,
        empty_label="— Elige una persona —",
        label="Asignada a",
        error_messages={"required": "Asigna la tarea a alguien."},
    )
    fecha_compromiso = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Fecha de compromiso",
        error_messages={"required": "Pon una fecha de compromiso."},
    )

    class Meta:
        model = Tarea
        fields = ["titulo", "descripcion", "estado", "prioridad", "asignada_a", "fecha_compromiso"]
        widgets = {
            # S-LC-Feedback-V4: autocomplete @#$ en título y descripción.
            "titulo": forms.TextInput(attrs={"data-referencias": "1"}),
            "descripcion": forms.Textarea(attrs={"data-referencias": "1", "rows": 4}),
        }


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ["cuerpo", "es_interno"]
        widgets = {
            "cuerpo": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
        }
