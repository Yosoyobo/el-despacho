from apps.la_cartera.models import Cliente, ClienteContacto
from django import forms


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "razon_social",
            "rfc",
            "direccion",
            "fiscal_igual",
            "direccion_fiscal",
            "notas",
            "estado",
        ]
        labels = {
            "razon_social": "Nombre",
            "direccion": "Dirección",
            "fiscal_igual": "La dirección fiscal es la misma",
            "direccion_fiscal": "Dirección fiscal",
        }
        widgets = {
            "direccion": forms.Textarea(attrs={"rows": 2}),
            "direccion_fiscal": forms.Textarea(attrs={"rows": 2, "data-fiscal-box": "1"}),
        }

    def clean_rfc(self):
        rfc = (self.cleaned_data.get("rfc") or "").strip().upper()
        if rfc and not (12 <= len(rfc) <= 13):
            raise forms.ValidationError("RFC debe tener 12 o 13 caracteres.")
        return rfc


class _ContactoBaseFormSet(forms.BaseInlineFormSet):
    def save(self, commit=True):
        objetos = super().save(commit=commit)
        # Garantiza un único principal: si ninguno quedó marcado y hay contactos,
        # el primero vigente pasa a principal.
        if commit:
            vivos = list(self.instance.contactos.all())
            if vivos and not any(c.principal for c in vivos):
                vivos[0].principal = True
                vivos[0].save(update_fields=["principal"])
        return objetos


ClienteContactoFormSet = forms.inlineformset_factory(
    Cliente,
    ClienteContacto,
    fields=["nombre", "puesto", "email", "telefono", "principal"],
    formset=_ContactoBaseFormSet,
    extra=1,
    can_delete=True,
)
