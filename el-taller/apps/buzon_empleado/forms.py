from django import forms

from buzon.models import MensajeBuzon


class RespuestaAdminForm(forms.ModelForm):
    """Pre-S2b.2: portado desde la-gerencia/apps/buzon_admin/forms.py.
    Solo aplica cuando `puede(user, "buzon", "responder")` es True."""

    class Meta:
        model = MensajeBuzon
        fields = ["estado", "nota_interna", "respuesta_publica"]
        widgets = {
            "nota_interna": forms.Textarea(attrs={"rows": 4}),
            "respuesta_publica": forms.Textarea(attrs={"rows": 6}),
        }


class NuevoMensajeForm(forms.ModelForm):
    class Meta:
        model = MensajeBuzon
        fields = ["tipo", "asunto", "cuerpo"]
        widgets = {
            "cuerpo": forms.Textarea(attrs={"rows": 8, "maxlength": 5000}),
            "asunto": forms.TextInput(attrs={"maxlength": 200}),
        }

    def clean_cuerpo(self):
        cuerpo = (self.cleaned_data.get("cuerpo") or "").strip()
        if len(cuerpo) < 5:
            raise forms.ValidationError("Detalla un poco más (mínimo 5 caracteres).")
        if len(cuerpo) > 5000:
            raise forms.ValidationError("Máximo 5000 caracteres.")
        return cuerpo
