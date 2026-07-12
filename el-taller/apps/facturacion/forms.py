from __future__ import annotations

from decimal import Decimal

from apps.tesoreria.models.ingreso import METODOS_INGRESO
from django import forms

from .models import Factura, FacturaItem


class FacturaForm(forms.ModelForm):
    class Meta:
        model = Factura
        fields = [
            "folio_numero",
            "cliente", "proyecto", "cotizacion_origen", "concepto",
            "estado",
            "fecha_emision", "fecha_vencimiento",
            "moneda", "regimen_fiscal",
            "descuento_global_porcentaje", "porcentaje_a_facturar",
            "notas", "terminos",
        ]
        widgets = {
            "folio_numero": forms.NumberInput(attrs={"min": 1, "class": "folio-input"}),
            "estado": forms.HiddenInput(),
            "regimen_fiscal": forms.RadioSelect(attrs={"class": "sr-only"}),
            "porcentaje_a_facturar": forms.HiddenInput(),
            "fecha_emision": forms.DateInput(attrs={"type": "date"}),
            "fecha_vencimiento": forms.DateInput(attrs={"type": "date"}),
            "notas": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
            "terminos": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
        }
        labels = {"folio_numero": "Factura (folio)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Concepto es obligatorio (LC 2026-07); el modelo lo deja blank.
        self.fields["concepto"].required = True
        # Folio obligatorio; se sugiere el siguiente disponible en la vista.
        self.fields["folio_numero"].required = True
        # Régimen fiscal opcional en el POST: si no llega, conserva el valor
        # actual (facturas editadas fuera de borrador no envían el campo).
        self.fields["regimen_fiscal"].required = False
        # LC #1/#161.3: el default de una factura nueva es «IVA y Retenciones»
        # (honorarios / RESICO — el régimen real de LC). Existentes conservan el
        # suyo.
        if not (self.instance and self.instance.pk) and not self.initial.get("regimen_fiscal"):
            self.fields["regimen_fiscal"].initial = "honorarios"
        # LC #162 (fix del bug latente): estos querysets estaban DESPUÉS de un
        # `return` en clean_regimen_fiscal → CÓDIGO MUERTO; los selects mostraban
        # proyectos archivados / cotizaciones anuladas. Aquí sí se aplican.
        from apps.cotizaciones.models import Cotizacion
        self.fields["cotizacion_origen"].queryset = (
            Cotizacion.vigentes.select_related("proyecto").order_by("-creado_en")
        )
        from apps.los_proyectos.models import Proyecto
        mgr = getattr(Proyecto, "activos", Proyecto.objects)
        self.fields["proyecto"].queryset = mgr.order_by("-creado_en")
        # LC Buzón §4: combobox type-to-search en Cliente / Proyecto / Cotización.
        for _c in ("cliente", "proyecto", "cotizacion_origen"):
            if _c in self.fields:
                self.fields[_c].widget.attrs["data-select-buscable"] = "1"

    def clean_regimen_fiscal(self):
        v = self.cleaned_data.get("regimen_fiscal")
        return v or (self.instance.regimen_fiscal or "iva")

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
        pf = cleaned.get("porcentaje_a_facturar")
        if pf is not None and (pf <= 0 or pf > Decimal("100")):
            self.add_error("porcentaje_a_facturar",
                           "El porcentaje a facturar debe estar entre 1 y 100.")
        return cleaned

    def clean_folio_numero(self):
        v = self.cleaned_data.get("folio_numero")
        if v is None or v < 1:
            raise forms.ValidationError("Captura el número de folio de la factura.")
        return v


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


# extra=0: las líneas arrancan ocultas; aparecen con "+ Agregar línea" o al
# cargar una cotización (LC 2026-07).
ItemFormSet = forms.inlineformset_factory(
    Factura,
    FacturaItem,
    form=FacturaItemForm,
    extra=0,
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
