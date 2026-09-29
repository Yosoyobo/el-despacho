"""Formularios de La Nómina (S-Checador-V2)."""

from __future__ import annotations

from decimal import ROUND_UP, Decimal

from django import forms
from django.db.models import Sum

from .models import ConceptoRecibo, PrestamoNomina, ReciboNomina, SueldoPersona
from .models.nomina import CERO
from .nomina import METODOS_PAGO_NOMINA, saldo_disponible, tipo_para_clase

FECHA = {"type": "date"}
FORMATO_FECHA = "%Y-%m-%d"

# Las clases que se capturan a mano. Abono a préstamo y reembolso las pone el cálculo.
CLASES_A_MANO = (
    ("bono", "Bono / comisión"),
    ("deduccion", "Deducción"),
    ("ajuste", "Ajuste"),
)


def _personas():
    from cuentas.models.usuario import Usuario

    return Usuario.objects.filter(is_active=True).order_by("nombre_completo")


class _PersonaChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return (obj.nombre_completo or "").strip() or obj.email


class SueldoForm(forms.ModelForm):
    usuario = _PersonaChoice(queryset=None, label="Persona")

    class Meta:
        model = SueldoPersona
        fields = ["usuario", "sueldo_quincenal", "vigente_desde", "en_nomina", "notas"]
        labels = {
            "sueldo_quincenal": "Sueldo por quincena",
            "vigente_desde": "Vigente desde",
            "en_nomina": "En nómina",
            "notas": "Notas",
        }
        widgets = {
            "vigente_desde": forms.DateInput(attrs=FECHA, format=FORMATO_FECHA),
            "notas": forms.Textarea(attrs={"rows": 2, "data-referencias": ""}),
            "sueldo_quincenal": forms.NumberInput(attrs={"step": "0.01", "min": "0", "inputmode": "decimal"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = _personas()

    def clean(self):
        datos = super().clean()
        u, desde = datos.get("usuario"), datos.get("vigente_desde")
        if u and desde:
            qs = SueldoPersona.objects.filter(usuario=u, vigente_desde=desde)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("vigente_desde", "Esa persona ya tiene un sueldo que empieza ese día: edítalo.")
        return datos


class PrestamoForm(forms.ModelForm):
    usuario = _PersonaChoice(queryset=None, label="Persona")
    cuota = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False,
        label="Abono por quincena", help_text="O deja vacío y di en cuántas quincenas.",
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "inputmode": "decimal"}),
    )

    class Meta:
        model = PrestamoNomina
        fields = ["usuario", "concepto", "monto", "fecha", "cuota", "quincenas", "notas"]
        labels = {
            "concepto": "Concepto", "monto": "Monto prestado", "fecha": "Fecha",
            "quincenas": "En cuántas quincenas", "notas": "Notas",
        }
        widgets = {
            "fecha": forms.DateInput(attrs=FECHA, format=FORMATO_FECHA),
            "notas": forms.Textarea(attrs={"rows": 2, "data-referencias": ""}),
            "monto": forms.NumberInput(attrs={"step": "0.01", "min": "0", "inputmode": "decimal"}),
            "concepto": forms.TextInput(attrs={"data-referencias": ""}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = _personas()
        # Con abonos ya aplicados, la persona no cambia.
        if self.instance.pk and self.instance.abonos.filter(recibo__periodo__estado="cerrado").exists():
            self.fields["usuario"].disabled = True

    def clean(self):
        datos = super().clean()
        monto, cuota, n = datos.get("monto"), datos.get("cuota"), datos.get("quincenas")
        if monto is None:
            return datos
        if cuota is None and not n:
            self.add_error("cuota", "Di cuánto se abona por quincena, o en cuántas quincenas.")
            return datos
        if cuota is None:
            datos["cuota"] = (monto / n).quantize(Decimal("0.01"), rounding=ROUND_UP)
        if datos["cuota"] > monto:
            self.add_error("cuota", "El abono no puede ser mayor que el préstamo.")
        if self.instance.pk:
            aplicado = self.instance.abonos.filter(
                recibo__periodo__estado="cerrado").aggregate(s=Sum("monto"))["s"] or CERO
            if monto < aplicado:
                self.add_error("monto", f"Ya se han abonado ${aplicado}: el préstamo no puede ser menor.")
            else:
                self._aplicado = aplicado
        return datos

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.cuota = self.cleaned_data["cuota"]
        obj.saldo = obj.monto - getattr(self, "_aplicado", CERO)
        if commit:
            obj.save()
        return obj


class ReciboForm(forms.ModelForm):
    class Meta:
        model = ReciboNomina
        fields = ["notas"]
        labels = {"notas": "Notas del recibo"}
        widgets = {"notas": forms.Textarea(attrs={"rows": 2, "data-referencias": ""})}


class ConceptoForm(forms.ModelForm):
    class Meta:
        model = ConceptoRecibo
        fields = ["clase", "tipo", "descripcion", "monto", "nota"]
        labels = {"clase": "Concepto", "tipo": "Suma o resta", "descripcion": "Descripción",
                  "monto": "Monto", "nota": "Nota"}
        widgets = {
            "descripcion": forms.TextInput(attrs={"data-referencias": ""}),
            "nota": forms.TextInput(attrs={"data-referencias": "", "placeholder": "Nota (opcional)"}),
            "monto": forms.NumberInput(attrs={"step": "0.01", "min": "0", "inputmode": "decimal"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        ligado = bool(inst.pk and (inst.prestamo_id or inst.egreso_id))
        if ligado:
            # Lo que viene del cálculo conserva su clase y su lado; el reembolso
            # además su monto: se salda completo en Tesorería al pagar.
            self.fields["clase"].disabled = True
            self.fields["tipo"].disabled = True
            if inst.egreso_id:
                self.fields["monto"].disabled = True
        else:
            self.fields["clase"].choices = CLASES_A_MANO
        self.fields["tipo"].required = False

    def clean(self):
        datos = super().clean()
        clase = datos.get("clase") or getattr(self.instance, "clase", "")
        datos["tipo"] = tipo_para_clase(clase, datos.get("tipo") or "")
        return datos

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.tipo = self.cleaned_data["tipo"]
        if commit:
            obj.save()
        return obj


class _ConceptosFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        recibo = self.instance
        percepciones = deducciones = CERO
        for f in self.forms:
            datos = getattr(f, "cleaned_data", None) or {}
            if not datos or datos.get("DELETE"):
                continue
            if not f.instance.pk and not f.has_changed():
                continue
            monto = datos.get("monto") or CERO
            if datos.get("tipo") == "deduccion":
                deducciones += monto
            else:
                percepciones += monto
            p = f.instance.prestamo if f.instance.prestamo_id else None
            if p is not None and monto > saldo_disponible(p, excluir_recibo=recibo):
                f.add_error("monto", f"Máximo ${saldo_disponible(p, excluir_recibo=recibo)}: es lo que queda del préstamo.")
        neto = (recibo.sueldo_aplicado or CERO) + percepciones - deducciones
        if neto < 0:
            raise forms.ValidationError(f"El neto quedaría negativo (${neto}). Revisa las deducciones.")


ConceptosFormSet = forms.inlineformset_factory(
    ReciboNomina, ConceptoRecibo, form=ConceptoForm, formset=_ConceptosFormSet,
    extra=1, can_delete=True,
)


class PagarForm(forms.Form):
    fecha = forms.DateField(
        label="Fecha real del depósito",
        widget=forms.DateInput(attrs=FECHA, format=FORMATO_FECHA),
    )
    metodo = forms.ChoiceField(choices=METODOS_PAGO_NOMINA, initial="transferencia", label="Cómo se pagó")
    banco_o_caja = forms.ChoiceField(
        choices=(("banco", "Banco"), ("caja", "Caja")), initial="banco", label="Salió de",
        help_text="Sólo importa si el recibo trae reembolsos: se saldan en Tesorería desde esa cuenta.",
    )


class AbrirPeriodoForm(forms.Form):
    fecha = forms.DateField(
        label="Cualquier día de la quincena",
        widget=forms.DateInput(attrs=FECHA, format=FORMATO_FECHA),
    )
