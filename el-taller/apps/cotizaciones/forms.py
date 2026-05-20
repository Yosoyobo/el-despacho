from __future__ import annotations

from decimal import Decimal

from django import forms

from .models import Cotizacion, CotizacionItem


class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = [
            "cliente", "proyecto", "titulo",
            "fecha_emision", "fecha_validez",
            "moneda", "descuento_global_porcentaje",
            "notas", "terminos",
        ]
        widgets = {
            "fecha_emision": forms.DateInput(attrs={"type": "date"}),
            "fecha_validez": forms.DateInput(attrs={"type": "date"}),
            "notas": forms.Textarea(attrs={"rows": 3}),
            "terminos": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        emi = cleaned.get("fecha_emision")
        val = cleaned.get("fecha_validez")
        if emi and val and val < emi:
            raise forms.ValidationError(
                "La fecha de validez no puede ser anterior a la fecha de emisión."
            )
        desc = cleaned.get("descuento_global_porcentaje")
        if desc is not None and (desc < 0 or desc > Decimal("100")):
            self.add_error("descuento_global_porcentaje",
                           "El descuento debe estar entre 0 y 100.")
        return cleaned


class CotizacionItemForm(forms.ModelForm):
    class Meta:
        model = CotizacionItem
        fields = [
            "orden", "servicio", "descripcion",
            "cantidad", "unidad", "precio_unitario", "descuento_porcentaje",
        ]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 2}),
            "orden": forms.NumberInput(attrs={"min": 0}),
        }

    def clean_cantidad(self):
        v = self.cleaned_data.get("cantidad")
        if v is None or v <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor a cero.")
        return v

    def clean_precio_unitario(self):
        v = self.cleaned_data.get("precio_unitario")
        if v is None or v < 0:
            raise forms.ValidationError("El precio unitario no puede ser negativo.")
        return v

    def clean_descuento_porcentaje(self):
        v = self.cleaned_data.get("descuento_porcentaje") or Decimal("0")
        if v < 0 or v > Decimal("100"):
            raise forms.ValidationError("El descuento debe estar entre 0 y 100.")
        return v


ItemFormSet = forms.inlineformset_factory(
    Cotizacion,
    CotizacionItem,
    form=CotizacionItemForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class EnviarForm(forms.Form):
    email_destino = forms.EmailField(required=False, label="Email del cliente")


class AprobarForm(forms.Form):
    nombre = forms.CharField(max_length=200, label="Nombre de quien aprobó")
    email = forms.EmailField(required=False)
    referencia = forms.CharField(
        max_length=200, required=False,
        label="Referencia (OC, correo, etc.)",
    )


class RechazarForm(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=1000)


class AnularForm(forms.Form):
    motivo = forms.CharField(max_length=300)
