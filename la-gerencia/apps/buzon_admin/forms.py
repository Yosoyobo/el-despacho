from django import forms

from buzon.models import MensajeBuzon


class RespuestaAdminForm(forms.ModelForm):
    class Meta:
        model = MensajeBuzon
        fields = ["estado", "nota_interna", "respuesta_publica"]
        widgets = {
            "nota_interna": forms.Textarea(attrs={"data-referencias": "1", "rows": 4}),
            "respuesta_publica": forms.Textarea(attrs={"data-referencias": "1", "rows": 6}),
        }
