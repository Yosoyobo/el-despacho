from datetime import date

from django import forms
from django.utils.text import slugify

from .models import METODOS_EGRESO, CentroDeCosto, Egreso, Ingreso

CSS_INPUT = (
    "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm "
    "text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none "
    "focus:ring-2 focus:ring-brand-500/20 dark:border-gray-700 dark:bg-gray-900 "
    "dark:text-gray-100 dark:placeholder-gray-500"
)


def _aplicar_css(form: forms.Form) -> None:
    for field in form.fields.values():
        existing = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = (existing + " " + CSS_INPUT).strip()


class IngresoForm(forms.ModelForm):
    class Meta:
        model = Ingreso
        fields = [
            "fecha", "monto", "moneda", "descripcion",
            "cliente", "proyecto", "metodo", "referencia_externa",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.TextInput(attrs={"maxlength": 300}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.la_cartera.models import Cliente
        from apps.los_proyectos.models import Proyecto
        self.fields["cliente"].queryset = Cliente.activos.all()
        self.fields["proyecto"].queryset = Proyecto.objects.exclude(estado="cancelado")
        if not self.instance.pk and not self.initial.get("fecha"):
            self.initial["fecha"] = date.today()
        _aplicar_css(self)

    def clean_monto(self):
        monto = self.cleaned_data["monto"]
        if monto is None or monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a cero.")
        return monto


class EgresoForm(forms.ModelForm):
    class Meta:
        model = Egreso
        fields = [
            "fecha", "monto", "moneda", "descripcion", "proveedor_nombre",
            "centro_de_costo", "proyecto",
            "pagado_por", "solicitado_por",
            "estado_pago", "metodo",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.TextInput(attrs={"maxlength": 300}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.los_proyectos.models import Proyecto

        from cuentas.models.usuario import Usuario
        self.fields["centro_de_costo"].queryset = CentroDeCosto.objects.filter(activo=True)
        self.fields["proyecto"].queryset = Proyecto.objects.exclude(estado="cancelado")
        usuarios_activos = Usuario.objects.filter(is_active=True)
        self.fields["pagado_por"].queryset = usuarios_activos
        self.fields["solicitado_por"].queryset = usuarios_activos
        if not self.instance.pk and not self.initial.get("fecha"):
            self.initial["fecha"] = date.today()
        _aplicar_css(self)

    def clean_monto(self):
        monto = self.cleaned_data["monto"]
        if monto is None or monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a cero.")
        return monto

    def clean(self):
        cleaned = super().clean()
        metodo = cleaned.get("metodo")
        estado = cleaned.get("estado_pago")
        if metodo == "tarjeta_personal" and estado == "pagado":
            self.add_error(
                "estado_pago",
                "Pagos con tarjeta personal normalmente quedan como «Por reembolsar».",
            )
        return cleaned


class CentroDeCostoForm(forms.ModelForm):
    class Meta:
        model = CentroDeCosto
        fields = ["nombre", "descripcion", "naturaleza", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_css(self)

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise forms.ValidationError("Requerido.")
        qs = CentroDeCosto.objects.filter(slug=slugify(nombre)[:80])
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un centro de costo con ese nombre/slug.")
        return nombre


class ReembolsarEgresoForm(forms.Form):
    metodo = forms.ChoiceField(
        choices=METODOS_EGRESO, initial="transferencia",
        label="Método de pago",
    )
    banco_o_caja = forms.ChoiceField(
        choices=[("banco", "Banco"), ("caja", "Caja")],
        initial="banco",
        widget=forms.RadioSelect,
        label="Cuenta de salida",
    )
    fecha = forms.DateField(
        initial=date.today,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Fecha del pago",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_css(self)
        # El radio no se beneficia de CSS_INPUT (es inline).
        self.fields["banco_o_caja"].widget.attrs.pop("class", None)


class AnularForm(forms.Form):
    motivo = forms.CharField(
        max_length=300,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Razón de la anulación"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_css(self)

    def clean_motivo(self):
        motivo = (self.cleaned_data.get("motivo") or "").strip()
        if len(motivo) < 5:
            raise forms.ValidationError("Da una razón de al menos 5 caracteres.")
        return motivo
