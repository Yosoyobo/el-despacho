"""Formularios de Compras: la orden y sus renglones."""

from __future__ import annotations

from django import forms

from .models import OrdenCompra, OrdenCompraItem


class OrdenCompraForm(forms.ModelForm):
    class Meta:
        model = OrdenCompra
        fields = ["proveedor", "proyecto", "fecha", "fecha_entrega", "moneda", "condiciones", "notas"]
        widgets = {
            # Fechas ISO: el `es-mx` las localizaría y el input de fecha no las lee.
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_entrega": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "condiciones": forms.Textarea(attrs={"rows": 3, "data-referencias": "1"}),
            "notas": forms.Textarea(attrs={"rows": 3, "data-referencias": "1"}),
        }
        labels = {"fecha_entrega": "Para cuándo", "condiciones": "Condiciones (pago, entrega, empaque)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.el_catalogo.models import Proveedor
        from apps.los_proyectos.models import Proyecto

        self.fields["proveedor"].queryset = Proveedor.objects.filter(activo=True).order_by("razon_social")
        self.fields["proyecto"].queryset = (Proyecto.objects.filter(archivado=False)
                                            .select_related("cliente").order_by("-actualizado_en"))
        self.fields["proyecto"].required = False
        self.fields["moneda"].widget = forms.Select(choices=(("MXN", "MXN"), ("USD", "USD")))


class OrdenCompraItemForm(forms.ModelForm):
    class Meta:
        model = OrdenCompraItem
        # Sin `orden`: la vista numera los renglones por su lugar en la pantalla.
        # Un oculto más haría que un renglón vacío pareciera «cambiado».
        fields = ["descripcion", "cantidad", "unidad", "precio_unitario"]

    def clean_cantidad(self):
        v = self.cleaned_data.get("cantidad")
        if v is None or v <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor a cero.")
        return v

    def clean_precio_unitario(self):
        v = self.cleaned_data.get("precio_unitario")
        if v is None or v < 0:
            raise forms.ValidationError("El precio no puede ser negativo.")
        return v


ItemFormSet = forms.inlineformset_factory(
    OrdenCompra, OrdenCompraItem, form=OrdenCompraItemForm,
    extra=3, can_delete=True, min_num=0, validate_min=False,
)
