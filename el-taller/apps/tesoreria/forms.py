from datetime import date
from decimal import Decimal

from django import forms
from django.utils.text import slugify

from .models import (
    METODOS_EGRESO,
    METODOS_EGRESO_FORM,
    METODOS_INGRESO,
    METODOS_INGRESO_FORM,
    METODOS_REEMBOLSO,
    CentroDeCosto,
    Egreso,
    Ingreso,
)

IVA_FACTOR = Decimal("1.16")


def _total_con_iva(subtotal: Decimal, incluye_iva: bool) -> Decimal:
    """subtotal → total que va a Contaduría (×1.16 si incluye_iva)."""
    base = subtotal or Decimal("0")
    total = base * IVA_FACTOR if incluye_iva else base
    return total.quantize(Decimal("0.01"))

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
    # S-LC-Buzon: se captura el subtotal (sin IVA); el total (monto) se computa.
    subtotal = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
        label="Monto (sin IVA)",
    )

    class Meta:
        model = Ingreso
        fields = [
            "fecha", "subtotal", "incluye_iva", "moneda", "descripcion",
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
        proyectos_mgr = getattr(Proyecto, "activos", Proyecto.objects)
        self.fields["proyecto"].queryset = proyectos_mgr.exclude(estado__in=["cancelado", "cerrado"])
        # Métodos de captura manual (Tarjeta default). Los demás los ponen
        # integraciones (Stripe/MP) o llegan como legacy.
        metodos = [(v, etiqueta) for v, etiqueta in METODOS_INGRESO if v in METODOS_INGRESO_FORM]
        # Preserva un método legacy/integración (stripe, depósito…) al editar.
        if self.instance.pk and self.instance.metodo and self.instance.metodo not in METODOS_INGRESO_FORM:
            metodos.append((self.instance.metodo, dict(METODOS_INGRESO).get(self.instance.metodo, self.instance.metodo)))
        self.fields["metodo"].choices = metodos
        if not self.instance.pk and not self.initial.get("metodo"):
            self.initial["metodo"] = "tarjeta"
        if not self.instance.pk and not self.initial.get("fecha"):
            self.initial["fecha"] = date.today()
        # Edición: pre-llena subtotal desde el guardado (o el monto si es legacy).
        if self.instance.pk and self.initial.get("subtotal") is None:
            self.initial["subtotal"] = self.instance.subtotal or self.instance.monto
        _aplicar_css(self)
        # El checkbox de IVA no debe llevar el CSS de input full-width.
        self.fields["incluye_iva"].widget.attrs["class"] = (
            "iva-toggle h-5 w-5 rounded border-gray-300 text-brand-600 "
            "focus:ring-brand-500/30 dark:border-gray-600 dark:bg-gray-800"
        )

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.subtotal = self.cleaned_data["subtotal"]
        obj.monto = _total_con_iva(obj.subtotal, self.cleaned_data.get("incluye_iva"))
        if commit:
            obj.save()
        return obj


class EgresoForm(forms.ModelForm):
    subtotal = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
        label="Monto (sin IVA)",
    )

    class Meta:
        model = Egreso
        fields = [
            "fecha", "subtotal", "incluye_iva", "moneda", "descripcion", "proveedor",
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
        from apps.el_catalogo.models import Proveedor
        from apps.los_proyectos.models import Proyecto

        from cuentas.models.usuario import Usuario
        self.fields["centro_de_costo"].queryset = CentroDeCosto.objects.filter(activo=True)
        proyectos_mgr = getattr(Proyecto, "activos", Proyecto.objects)
        self.fields["proyecto"].queryset = proyectos_mgr.exclude(estado__in=["cancelado", "cerrado"])
        # LC 2026-07: TODO egreso debe ir ligado a un proveedor (obligatorio).
        self.fields["proveedor"].queryset = Proveedor.objects.filter(activo=True).order_by("razon_social")
        self.fields["proveedor"].required = True
        self.fields["proveedor"].empty_label = "— Elige un proveedor —"
        # LC 2026-07: un egreso solo se registra al realizarse → sin "Pendiente".
        # Solo Pagado (saldado) o Por reembolsar; default Pagado.
        self.fields["estado_pago"].choices = [
            ("pagado", "Pagado (saldado)"),
            ("por_reembolsar", "Por reembolsar al empleado"),
        ]
        if not self.instance.pk and not self.initial.get("estado_pago"):
            self.initial["estado_pago"] = "pagado"
        usuarios_activos = Usuario.objects.filter(is_active=True)
        self.fields["pagado_por"].queryset = usuarios_activos
        self.fields["solicitado_por"].queryset = usuarios_activos
        if not self.instance.pk and not self.initial.get("fecha"):
            self.initial["fecha"] = date.today()
        if self.instance.pk and self.initial.get("subtotal") is None:
            self.initial["subtotal"] = self.instance.subtotal or self.instance.monto
        # LC 2026-07: métodos curados en el orden pedido (Tarjeta empresa default,
        # luego transferencia, personales reembolsables; sin cheque). Preserva un
        # método legacy al editar.
        etiquetas = dict(METODOS_EGRESO)
        metodos = [(v, etiquetas.get(v, v)) for v in METODOS_EGRESO_FORM]
        actual = self.instance.metodo if self.instance.pk else None
        if actual and actual not in METODOS_EGRESO_FORM:
            metodos.append((actual, dict(METODOS_EGRESO).get(actual, actual)))
        self.fields["metodo"].choices = metodos
        if not self.instance.pk and not self.initial.get("metodo"):
            self.initial["metodo"] = "tarjeta_empresa"
        _aplicar_css(self)
        # El checkbox de IVA no debe llevar el CSS de input full-width.
        self.fields["incluye_iva"].widget.attrs["class"] = (
            "iva-toggle h-5 w-5 rounded border-gray-300 text-brand-600 "
            "focus:ring-brand-500/30 dark:border-gray-600 dark:bg-gray-800"
        )

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.subtotal = self.cleaned_data["subtotal"]
        obj.monto = _total_con_iva(obj.subtotal, self.cleaned_data.get("incluye_iva"))
        prov = self.cleaned_data.get("proveedor")
        obj.proveedor_nombre = prov.razon_social if prov else "Gasto operativo"
        if commit:
            obj.save()
        return obj

    def clean(self):
        cleaned = super().clean()
        # Lógica defensiva de reembolso (LC 2026-07): si el método implica que
        # el empleado puso el dinero (efectivo/tarjeta personal), el estado muta
        # automáticamente a «Por reembolsar» (sin error — se corrige solo, igual
        # que el JS de las pastillas).
        if cleaned.get("metodo") in METODOS_REEMBOLSO:
            cleaned["estado_pago"] = "por_reembolsar"
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
        widget=forms.Textarea(attrs={"data-referencias": "1", "rows": 3, "placeholder": "Razón de la anulación"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_css(self)

    def clean_motivo(self):
        motivo = (self.cleaned_data.get("motivo") or "").strip()
        if len(motivo) < 5:
            raise forms.ValidationError("Da una razón de al menos 5 caracteres.")
        return motivo
