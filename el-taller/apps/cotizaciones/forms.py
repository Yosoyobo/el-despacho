from __future__ import annotations

from decimal import Decimal

from django import forms

from .models import Cotizacion, CotizacionItem


class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        # S-LC-Feedback-V2: fecha_validez removida del form (queda nullable en el modelo
        # por back-compat con cotizaciones existentes — el formulario sólo edita los
        # demás campos).
        fields = [
            "cliente", "proyecto", "titulo",
            "fecha_emision",
            "moneda", "descuento_global_porcentaje",
            "anticipo_porcentaje", "anticipo_monto_override",
            "notas", "terminos",
        ]
        widgets = {
            "fecha_emision": forms.DateInput(attrs={"type": "date"}),
            "notas": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
            "terminos": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
        }
        labels = {
            "titulo": "Título",
            "fecha_emision": "Fecha de emisión",
            "moneda": "Moneda",
            "descuento_global_porcentaje": "Descuento global (%)",
            "anticipo_porcentaje": "Anticipo (%)",
            "anticipo_monto_override": "Anticipo ($) — override opcional",
        }
        help_texts = {
            "anticipo_porcentaje": "Porcentaje del total que se cobra como anticipo al aprobar. Deja en 0 para no pedir anticipo.",
            "anticipo_monto_override": "Si quieres un monto exacto distinto al calculado, ponlo aquí.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Anticipo es opcional en el form (modelo tiene default 0 / null).
        self.fields["anticipo_porcentaje"].required = False
        self.fields["anticipo_monto_override"].required = False
        # S-LC-Feedback-V2: Proyecto es obligatorio (toda cotización debe ir
        # ligada a un proyecto). El modelo aún acepta null para no migrar
        # cotizaciones legacy, pero el form bloquea.
        self.fields["proyecto"].required = True
        self.fields["proyecto"].empty_label = None

    def clean(self):
        cleaned = super().clean()
        desc = cleaned.get("descuento_global_porcentaje")
        if desc is not None and (desc < 0 or desc > Decimal("100")):
            self.add_error("descuento_global_porcentaje",
                           "El descuento debe estar entre 0 y 100.")
        ant_pct = cleaned.get("anticipo_porcentaje")
        if ant_pct is not None and (ant_pct < 0 or ant_pct > Decimal("100")):
            self.add_error("anticipo_porcentaje",
                           "El anticipo debe estar entre 0 y 100%.")
        ant_monto = cleaned.get("anticipo_monto_override")
        if ant_monto is not None and ant_monto < 0:
            self.add_error("anticipo_monto_override",
                           "El monto del anticipo no puede ser negativo.")
        return cleaned


class CotizacionItemForm(forms.ModelForm):
    class Meta:
        model = CotizacionItem
        fields = [
            "orden", "servicio", "variacion", "descripcion",
            "cantidad", "unidad", "precio_unitario", "descuento_porcentaje",
        ]
        widgets = {
            "descripcion": forms.Textarea(attrs={"data-referencias": "1", "rows": 2}),
            "orden": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # S-LC-Feedback-V4: servicio/variacion opcionales (descripción libre como fallback).
        self.fields["servicio"].required = False
        self.fields["variacion"].required = False
        self.fields["descripcion"].required = False

    def clean(self):
        cleaned = super().clean()
        # Si no hay servicio elegido, exige descripción libre.
        if not cleaned.get("servicio") and not (cleaned.get("descripcion") or "").strip():
            self.add_error("descripcion", "Elige un producto del catálogo o escribe una descripción.")
        return cleaned

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
    motivo = forms.CharField(widget=forms.Textarea(attrs={"data-referencias": "1", "rows": 3}), max_length=1000)


class AnularForm(forms.Form):
    motivo = forms.CharField(max_length=300)
