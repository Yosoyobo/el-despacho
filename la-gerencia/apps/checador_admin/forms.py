from __future__ import annotations

from apps.checador.models import HorarioLaboral
from apps.checador.models.horario import DIAS_SEMANA
from django import forms

from cuentas.models.usuario import Usuario

# Widget de hora forzado a 24h con flatpickr (texto + data-flatpickr-time; el
# valor se envía como "H:i" → Django lo parsea con %H:%M). Si el JS no carga,
# queda un input de texto HH:MM válido.
_TIME_WIDGET = forms.TimeInput(
    format="%H:%M",
    attrs={
        "type": "text", "data-flatpickr-time": "1",
        "placeholder": "HH:MM", "autocomplete": "off", "inputmode": "numeric",
    },
)


class HorarioLaboralForm(forms.ModelForm):
    """Edición de UN horario existente (día/usuario fijos por registro)."""

    class Meta:
        model = HorarioLaboral
        fields = ["usuario", "dia_semana", "hora_entrada", "hora_salida", "tolerancia_min", "activo"]
        widgets = {
            "hora_entrada": _TIME_WIDGET,
            "hora_salida": _TIME_WIDGET,
        }
        labels = {
            "usuario": "Usuario", "dia_semana": "Día", "hora_entrada": "Entrada",
            "hora_salida": "Salida", "tolerancia_min": "Tolerancia (min)", "activo": "Activo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].required = False
        self.fields["usuario"].empty_label = "— Global (todo el staff) —"
        self.fields["usuario"].queryset = Usuario.objects.filter(is_active=True).order_by("nombre_completo")
        self.fields["usuario"].help_text = "Vacío = horario global para todo el staff."

    def clean(self):
        cleaned = super().clean()
        usuario = cleaned.get("usuario")
        dia = cleaned.get("dia_semana")
        if dia is None:
            return cleaned
        qs = HorarioLaboral.objects.filter(usuario=usuario, dia_semana=dia)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            destino = "para ese usuario" if usuario else "global"
            raise forms.ValidationError(f"Ya existe un horario {destino} para ese día.")
        return cleaned


class HorarioBulkForm(forms.Form):
    """Alta masiva: varios días y/o varios usuarios a la vez (checkboxes).
    Crea/actualiza un HorarioLaboral por cada (usuario × día)."""

    aplicar_global = forms.BooleanField(
        required=False, initial=True, label="Aplicar a todo el staff (global)",
    )
    usuarios = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(is_active=True).order_by("nombre_completo"),
        required=False, widget=forms.CheckboxSelectMultiple, label="Usuarios",
    )
    dias = forms.MultipleChoiceField(
        choices=DIAS_SEMANA, widget=forms.CheckboxSelectMultiple, label="Días",
    )
    hora_entrada = forms.TimeField(label="Entrada", widget=_TIME_WIDGET, input_formats=["%H:%M"])
    hora_salida = forms.TimeField(label="Salida", widget=_TIME_WIDGET, input_formats=["%H:%M"])
    tolerancia_min = forms.IntegerField(label="Tolerancia (min)", min_value=0, initial=15)
    activo = forms.BooleanField(required=False, initial=True, label="Activo")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("aplicar_global") and not cleaned.get("usuarios"):
            raise forms.ValidationError(
                "Elige al menos un usuario o marca «Aplicar a todo el staff».")
        return cleaned

    def guardar(self) -> int:
        """Crea/actualiza los horarios. Devuelve cuántos (usuario×día) tocó."""
        d = self.cleaned_data
        objetivos = [None] if d.get("aplicar_global") else list(d["usuarios"])
        defaults = {
            "hora_entrada": d["hora_entrada"], "hora_salida": d["hora_salida"],
            "tolerancia_min": d["tolerancia_min"], "activo": d["activo"],
        }
        n = 0
        for usuario in objetivos:
            for dia in d["dias"]:
                HorarioLaboral.objects.update_or_create(
                    usuario=usuario, dia_semana=int(dia), defaults=defaults,
                )
                n += 1
        return n
