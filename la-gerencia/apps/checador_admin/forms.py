from __future__ import annotations

from apps.checador.models import HorarioLaboral
from django import forms

from cuentas.models.usuario import Usuario


class HorarioLaboralForm(forms.ModelForm):
    class Meta:
        model = HorarioLaboral
        fields = ["usuario", "dia_semana", "hora_entrada", "hora_salida", "tolerancia_min", "activo"]
        widgets = {
            "hora_entrada": forms.TimeInput(attrs={"type": "time"}),
            "hora_salida": forms.TimeInput(attrs={"type": "time"}),
        }
        labels = {
            "usuario": "Usuario",
            "dia_semana": "Día",
            "hora_entrada": "Entrada",
            "hora_salida": "Salida",
            "tolerancia_min": "Tolerancia (min)",
            "activo": "Activo",
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
        # Evita duplicar el horario global del día (Postgres no lo impide con
        # usuario NULL); el override por usuario lo cubre el UniqueConstraint.
        qs = HorarioLaboral.objects.filter(usuario=usuario, dia_semana=dia)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            destino = "para ese usuario" if usuario else "global"
            raise forms.ValidationError(f"Ya existe un horario {destino} para ese día.")
        return cleaned
