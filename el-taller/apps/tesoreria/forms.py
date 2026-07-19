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


def _desglosar_total(capturado: Decimal, incluye_iva: bool) -> tuple[Decimal, Decimal]:
    """El número capturado es el TOTAL (LC Fase 2, decisión Oscar). Devuelve
    `(monto, subtotal_base)`:
      - IVA on  → monto = total capturado; subtotal = total ÷ 1.16 (base sin IVA).
      - IVA off → monto = subtotal = total capturado (operación sin IVA).
    El `monto` (lo que va a Contaduría) sigue siendo el total en ambos casos —
    solo cambia lo que el usuario escribe (antes la base, ahora el total)."""
    total = (capturado or Decimal("0")).quantize(Decimal("0.01"))
    base = (total / IVA_FACTOR).quantize(Decimal("0.01")) if incluye_iva else total
    return total, base

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
    # LC Fase 2: se captura el TOTAL; el subtotal (base sin IVA) se computa.
    subtotal = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
        label="Monto",
    )

    class Meta:
        model = Ingreso
        # LC Fase 2: `moneda` sale del form (sistema fijo en MXN; el modelo la
        # deja por default). Los registros existentes conservan la suya.
        fields = [
            "fecha", "subtotal", "incluye_iva", "descripcion",
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
        # LC Fase 2: el campo capturado es el TOTAL → al editar se pre-llena con
        # el monto (total) guardado. IVA ON por default en registros nuevos.
        if self.instance.pk and self.initial.get("subtotal") is None:
            self.initial["subtotal"] = self.instance.monto
        if not self.instance.pk and "incluye_iva" not in self.initial:
            self.initial["incluye_iva"] = True
        # LC Fase 2: cliente/proyecto con buscador integrado (combobox).
        for campo in ("cliente", "proyecto"):
            self.fields[campo].widget.attrs["data-select-buscable"] = ""
        _aplicar_css(self)
        # El checkbox de IVA no debe llevar el CSS de input full-width.
        self.fields["incluye_iva"].widget.attrs["class"] = (
            "iva-toggle h-5 w-5 rounded border-gray-300 text-brand-600 "
            "focus:ring-brand-500/30 dark:border-gray-600 dark:bg-gray-800"
        )

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.monto, obj.subtotal = _desglosar_total(
            self.cleaned_data["subtotal"], self.cleaned_data.get("incluye_iva"))
        if commit:
            obj.save()
        return obj


class EgresoForm(forms.ModelForm):
    # LC Fase 2: se captura el TOTAL; el subtotal (base sin IVA) se computa.
    subtotal = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
        label="Monto",
    )

    class Meta:
        model = Egreso
        # LC Fase 2: `moneda` sale del form (sistema fijo en MXN).
        fields = [
            "fecha", "subtotal", "incluye_iva", "descripcion", "proveedor",
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
        # LC Fase 2: el campo capturado es el TOTAL → al editar se pre-llena con
        # el monto (total) guardado. IVA ON por default en registros nuevos.
        if self.instance.pk and self.initial.get("subtotal") is None:
            self.initial["subtotal"] = self.instance.monto
        if not self.instance.pk and "incluye_iva" not in self.initial:
            self.initial["incluye_iva"] = True
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
        # LC Fase 2: selects largos con buscador integrado (combobox).
        for campo in ("proveedor", "proyecto", "centro_de_costo", "pagado_por", "solicitado_por"):
            self.fields[campo].widget.attrs["data-select-buscable"] = ""
        _aplicar_css(self)
        # El checkbox de IVA no debe llevar el CSS de input full-width.
        self.fields["incluye_iva"].widget.attrs["class"] = (
            "iva-toggle h-5 w-5 rounded border-gray-300 text-brand-600 "
            "focus:ring-brand-500/30 dark:border-gray-600 dark:bg-gray-800"
        )

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.monto, obj.subtotal = _desglosar_total(
            self.cleaned_data["subtotal"], self.cleaned_data.get("incluye_iva"))
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
