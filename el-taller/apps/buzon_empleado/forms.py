from django import forms

from buzon.models import MensajeBuzon


class RespuestaAdminForm(forms.ModelForm):
    """Pre-S2b.2: portado desde la-gerencia/apps/buzon_admin/forms.py.
    Solo aplica cuando `puede(user, "buzon", "responder")` es True."""

    class Meta:
        model = MensajeBuzon
        fields = ["estado", "nota_interna", "respuesta_publica"]
        widgets = {
            "nota_interna": forms.Textarea(attrs={"data-referencias": "1", "rows": 4}),
            "respuesta_publica": forms.Textarea(attrs={"data-referencias": "1", "rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # S-Buzon-Estados-V1: el estado es configurable — el dropdown ofrece
        # los estados activos (incluidos los custom). Si el actual ya no está
        # activo, lo agregamos para no perderlo al guardar.
        from buzon.estados import estados_activos

        opciones = [(e["slug"], e["label"]) for e in estados_activos()]
        actual = self.instance.estado if self.instance and self.instance.pk else None
        if actual and actual not in {s for s, _ in opciones}:
            from buzon.estados import label_de
            opciones.insert(0, (actual, label_de(actual)))
        self.fields["estado"] = forms.ChoiceField(
            choices=opciones, label="Estado", required=True,
        )


class NuevoMensajeForm(forms.ModelForm):
    prioridad = forms.IntegerField(
        min_value=0, max_value=10, initial=5,
        widget=forms.NumberInput(attrs={"type": "range", "min": 0, "max": 10, "step": 1, "class": "w-full"}),
        label="Prioridad (0 baja · 10 urgente)",
    )

    class Meta:
        model = MensajeBuzon
        fields = ["tipo", "asunto", "cuerpo", "prioridad"]
        widgets = {
            "cuerpo": forms.Textarea(attrs={"data-referencias": "1", "rows": 8, "maxlength": 5000}),
            "asunto": forms.TextInput(attrs={"maxlength": 200}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # S-LC-Buzon-V2: el tipo es configurable (TipoBuzon). El dropdown ofrece
        # los tipos activos; si el actual ya no está activo, lo conservamos.
        from buzon.tipos import label_de, tipos_activos
        opciones = [(t["slug"], t["label"]) for t in tipos_activos()]
        actual = self.instance.tipo if self.instance and self.instance.pk else None
        if actual and actual not in {s for s, _ in opciones}:
            opciones.insert(0, (actual, label_de(actual)))
        self.fields["tipo"] = forms.ChoiceField(choices=opciones, label="Tipo", required=True)

    def clean_cuerpo(self):
        cuerpo = (self.cleaned_data.get("cuerpo") or "").strip()
        if len(cuerpo) < 5:
            raise forms.ValidationError("Detalla un poco más (mínimo 5 caracteres).")
        if len(cuerpo) > 5000:
            raise forms.ValidationError("Máximo 5000 caracteres.")
        return cuerpo
