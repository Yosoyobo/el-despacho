from django import forms

from apps.la_cartera.models import Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "razon_social",
            "rfc",
            "nombre_contacto",
            "email_contacto",
            "telefono",
            "direccion",
            "notas",
            "estado",
        ]

    def clean_rfc(self):
        rfc = (self.cleaned_data.get("rfc") or "").strip().upper()
        if rfc and not (12 <= len(rfc) <= 13):
            raise forms.ValidationError("RFC debe tener 12 o 13 caracteres.")
        return rfc
