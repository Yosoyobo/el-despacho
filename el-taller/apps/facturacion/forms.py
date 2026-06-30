from __future__ import annotations

from decimal import Decimal

from apps.tesoreria.models.ingreso import METODOS_INGRESO
from django import forms

from .models import Factura, FacturaItem


class FacturaForm(forms.ModelForm):
    class Meta:
        model = Factura
        fields = [
            "cliente", "proyecto", "cotizacion_origen", "titulo", "concepto",
            "estado",
            "fecha_emision", "fecha_vencimiento",
            "moneda", "descuento_global_porcentaje",
            "notas", "terminos",
        ]
        widgets = {
            "fecha_emision": forms.DateInput(attrs={"type": "date"}),
            "fecha_vencimiento": forms.DateInput(attrs={"type": "date"}),
            "notas": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
            "terminos": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        emi = cleaned.get("fecha_emision")
        venc = cleaned.get("fecha_vencimiento")
        if emi and venc and venc < emi:
            raise forms.ValidationError(
                "La fecha de vencimiento no puede ser anterior a la fecha de emisión."
            )
        desc = cleaned.get("descuento_global_porcentaje")
        if desc is not None and (desc < 0 or desc > Decimal("100")):
            self.add_error("descuento_global_porcentaje",
                           "El descuento debe estar entre 0 y 100.")
        return cleaned


class FacturaItemForm(forms.ModelForm):
    class Meta:
        model = FacturaItem
        fields = [
            "orden", "servicio", "descripcion",
            "cantidad", "unidad", "precio_unitario", "descuento_porcentaje",
        ]
        widgets = {
            "descripcion": forms.Textarea(attrs={"data-referencias": "1", "rows": 2}),
            "orden": forms.NumberInput(attrs={"min": 0}),
        }
        labels = {"servicio": "Producto"}

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
    Factura,
    FacturaItem,
    form=FacturaItemForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class EmitirForm(forms.Form):
    """Formulario vacío (sólo CSRF). El estado se aplica al confirmar."""


class CancelarForm(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"data-referencias": "1", "rows": 3}), max_length=300)


class RegistrarCobroForm(forms.Form):
    monto = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    fecha = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    metodo = forms.ChoiceField(choices=METODOS_INGRESO)
    banco_o_caja = forms.ChoiceField(
        choices=(("banco", "Banco"), ("caja", "Caja")),
        initial="banco",
    )
    # Ticket LC 2026-06-29 — sección "Referencia" del cobro.
    folio = forms.CharField(
        required=False, max_length=100, label="Folio / referencia",
        widget=forms.TextInput(attrs={"placeholder": "N.º de operación, folio…"}),
    )
    nota = forms.CharField(
        required=False, max_length=200, label="Nota",
        widget=forms.TextInput(attrs={"placeholder": "Observación opcional"}),
    )
