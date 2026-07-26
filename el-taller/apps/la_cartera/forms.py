from apps.la_cartera.models import Cliente, ClienteContacto, ClienteRazonSocial
from django import forms


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # LC 2026-07-26: `razon_social_fiscal` y `rfc` salieron del form — los
        # datos de facturación se capturan en el formset de razones sociales
        # (varias por cliente, cada una con su RFC). Los campos del modelo se
        # conservan como espejo de la principal (ver services.espejar_razon_principal).
        fields = [
            "razon_social",
            "direccion",
            "fiscal_igual",
            "direccion_fiscal",
            "lat",
            "lng",
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
            # Coordenadas del pin (geo-picker) — ocultas, las llena el mini-mapa.
            "lat": forms.HiddenInput(),
            "lng": forms.HiddenInput(),
        }

    def clean_razon_social(self):
        # Nombre (razón social) siempre en MAYÚSCULAS. str.upper() respeta
        # acentos en español ("josé" → "JOSÉ").
        return (self.cleaned_data.get("razon_social") or "").strip().upper()


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


class ClienteRazonSocialForm(forms.ModelForm):
    """Una razón social de facturación: nombre legal + su RFC (LC 2026-07-26).

    Van en la MISMA línea en el form del cliente (pedido de Oscar), porque el
    RFC pertenece a esa razón social y no al cliente en general.
    """

    class Meta:
        model = ClienteRazonSocial
        fields = ["razon_social", "rfc", "principal"]
        labels = {
            "razon_social": "Razón social",
            "rfc": "RFC",
            "principal": "Principal",
        }
        widgets = {
            "razon_social": forms.TextInput(attrs={"placeholder": "NOMBRE LEGAL DEL CFDI"}),
            "rfc": forms.TextInput(attrs={"placeholder": "XAXX010101000", "maxlength": 13}),
        }

    def clean_razon_social(self):
        # Como aparece en el CFDI: mayúsculas.
        return (self.cleaned_data.get("razon_social") or "").strip().upper()

    def clean_rfc(self):
        rfc = (self.cleaned_data.get("rfc") or "").strip().upper()
        if rfc and not (12 <= len(rfc) <= 13):
            raise forms.ValidationError("RFC debe tener 12 o 13 caracteres.")
        return rfc


class _RazonSocialBaseFormSet(forms.BaseInlineFormSet):
    def save(self, commit=True):
        objetos = super().save(commit=commit)
        if commit:
            vivas = list(self.instance.razones_sociales.all())
            # Una sola principal: si ninguna quedó marcada, la primera manda.
            marcadas = [r for r in vivas if r.principal]
            if vivas and not marcadas:
                vivas[0].principal = True
                vivas[0].save(update_fields=["principal"])
            elif len(marcadas) > 1:
                for r in marcadas[1:]:
                    r.principal = False
                    r.save(update_fields=["principal"])
        return objetos


ClienteRazonSocialFormSet = forms.inlineformset_factory(
    Cliente,
    ClienteRazonSocial,
    form=ClienteRazonSocialForm,
    formset=_RazonSocialBaseFormSet,
    extra=1,
    can_delete=True,
)


ClienteContactoFormSet = forms.inlineformset_factory(
    Cliente,
    ClienteContacto,
    fields=["nombre", "puesto", "email", "telefono", "principal"],
    formset=_ContactoBaseFormSet,
    extra=1,
    can_delete=True,
)
