from __future__ import annotations

from decimal import Decimal

from django import forms

from .models import Asiento, CuentaContable, Partida


class AsientoForm(forms.ModelForm):
    class Meta:
        model = Asiento
        fields = ["fecha", "descripcion", "referencia_externa"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.TextInput(attrs={"maxlength": 300}),
        }


class PartidaForm(forms.ModelForm):
    class Meta:
        model = Partida
        fields = ["orden", "cuenta", "cargo", "abono", "descripcion"]
        widgets = {
            "orden": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cuenta"].queryset = CuentaContable.activas.order_by("codigo")

    def clean(self):
        cleaned = super().clean()
        c = cleaned.get("cargo") or Decimal("0")
        a = cleaned.get("abono") or Decimal("0")
        if c < 0 or a < 0:
            raise forms.ValidationError("Cargo y abono no pueden ser negativos.")
        if c > 0 and a > 0:
            raise forms.ValidationError("Una partida no puede tener cargo y abono.")
        if c == 0 and a == 0:
            # Permitir filas vacías que se ignoran en el save.
            cleaned["_vacia"] = True
        return cleaned


PartidaFormSet = forms.inlineformset_factory(
    Asiento,
    Partida,
    form=PartidaForm,
    extra=2,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class AnularForm(forms.Form):
    motivo = forms.CharField(max_length=300)
