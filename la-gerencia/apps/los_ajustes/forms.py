from django import forms

from ajustes.models import TasaImpositiva


class TasaForm(forms.ModelForm):
    class Meta:
        model = TasaImpositiva
        fields = ["nombre", "porcentaje", "tipo", "aplicable_default", "activa", "orden"]
