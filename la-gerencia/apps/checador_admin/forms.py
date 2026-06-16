from __future__ import annotations

from apps.checador.models import ConfiguracionGeocerca, HorarioLaboral, SedeLC
from apps.checador.models.horario import DIAS_SEMANA
from django import forms

from cuentas.models.usuario import Usuario

# Widget de hora forzado a 24h con flatpickr (texto + data-flatpickr-time; el
# valor se envía como "H:i" → Django lo parsea con %H:%M). Si el JS no carga,
# queda un input de texto HH:MM válido.
_TIME_WIDGET = forms.TimeInput(
    format="%H:%M",
    attrs={
        "type": "text", "data-flatpickr-time": "1",
        "placeholder": "HH:MM", "autocomplete": "off", "inputmode": "numeric",
    },
)


class HorarioLaboralForm(forms.ModelForm):
    """Edición de UN horario existente (día/usuario fijos por registro)."""

    class Meta:
        model = HorarioLaboral
        fields = ["usuario", "dia_semana", "hora_entrada", "hora_salida",
                  "tolerancia_min", "sede", "sede_texto", "activo"]
        widgets = {
            "hora_entrada": _TIME_WIDGET,
            "hora_salida": _TIME_WIDGET,
            "sede_texto": forms.TextInput(attrs={"placeholder": "Ej. Oficina 1 (si no está en el catálogo)"}),
        }
        labels = {
            "usuario": "Usuario", "dia_semana": "Día", "hora_entrada": "Entrada",
            "hora_salida": "Salida", "tolerancia_min": "Tolerancia (min)",
            "sede": "Sede esperada", "sede_texto": "Sede (texto libre)", "activo": "Activo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].required = False
        self.fields["usuario"].empty_label = "— Global (todo el staff) —"
        self.fields["usuario"].queryset = Usuario.objects.filter(is_active=True).order_by("nombre_completo")
        self.fields["usuario"].help_text = "Vacío = horario global para todo el staff."
        self.fields["sede"].required = False
        self.fields["sede"].empty_label = "— Sin asignar —"
        self.fields["sede"].queryset = SedeLC.objects.filter(activa=True).order_by("orden", "nombre")
        self.fields["sede_texto"].required = False

    def clean(self):
        cleaned = super().clean()
        usuario = cleaned.get("usuario")
        dia = cleaned.get("dia_semana")
        if dia is None:
            return cleaned
        qs = HorarioLaboral.objects.filter(usuario=usuario, dia_semana=dia)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            destino = "para ese usuario" if usuario else "global"
            raise forms.ValidationError(f"Ya existe un horario {destino} para ese día.")
        return cleaned


class HorarioBulkForm(forms.Form):
    """Alta masiva: varios días y/o varios usuarios a la vez (checkboxes).
    Crea/actualiza un HorarioLaboral por cada (usuario × día)."""

    aplicar_global = forms.BooleanField(
        required=False, initial=True, label="Aplicar a todo el staff (global)",
    )
    usuarios = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(is_active=True).order_by("nombre_completo"),
        required=False, widget=forms.CheckboxSelectMultiple, label="Usuarios",
    )
    dias = forms.MultipleChoiceField(
        choices=DIAS_SEMANA, widget=forms.CheckboxSelectMultiple, label="Días",
    )
    hora_entrada = forms.TimeField(label="Entrada", widget=_TIME_WIDGET, input_formats=["%H:%M"])
    hora_salida = forms.TimeField(label="Salida", widget=_TIME_WIDGET, input_formats=["%H:%M"])
    tolerancia_min = forms.IntegerField(label="Tolerancia (min)", min_value=0, initial=15)
    sede = forms.ModelChoiceField(
        queryset=SedeLC.objects.filter(activa=True).order_by("orden", "nombre"),
        required=False, label="Sede esperada", empty_label="— Sin asignar —",
    )
    sede_texto = forms.CharField(
        required=False, label="Sede (texto libre)", max_length=160,
        widget=forms.TextInput(attrs={"placeholder": "Si no está en el catálogo"}),
    )
    activo = forms.BooleanField(required=False, initial=True, label="Activo")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("aplicar_global") and not cleaned.get("usuarios"):
            raise forms.ValidationError(
                "Elige al menos un usuario o marca «Aplicar a todo el staff».")
        return cleaned

    def guardar(self) -> int:
        """Crea/actualiza los horarios. Devuelve cuántos (usuario×día) tocó."""
        d = self.cleaned_data
        objetivos = [None] if d.get("aplicar_global") else list(d["usuarios"])
        defaults = {
            "hora_entrada": d["hora_entrada"], "hora_salida": d["hora_salida"],
            "tolerancia_min": d["tolerancia_min"], "activo": d["activo"],
            "sede": d.get("sede"), "sede_texto": (d.get("sede_texto") or "").strip(),
        }
        n = 0
        for usuario in objetivos:
            for dia in d["dias"]:
                HorarioLaboral.objects.update_or_create(
                    usuario=usuario, dia_semana=int(dia), defaults=defaults,
                )
                n += 1
        return n


# ───────────────────────── Sedes / POI de LC (V12) ─────────────────────────

class SedeLCForm(forms.ModelForm):
    """Alta/edición de una sede de LC. lat/lng se capturan con el mapa Leaflet
    del template (o a mano); son opcionales: sin pin, la sede no participa en la
    validación de geocerca pero queda en el directorio."""

    class Meta:
        model = SedeLC
        fields = ["nombre", "direccion", "lat", "lng", "radio_m", "activa", "orden", "notas"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Ej. Oficina 1"}),
            "direccion": forms.Textarea(attrs={"rows": 2, "placeholder": "Calle, número, colonia, ciudad…"}),
            # data-sede-* los cablea el mapa Leaflet (form_sede.html).
            "lat": forms.NumberInput(attrs={"step": "any", "data-sede-lat": "1", "placeholder": "19.40"}),
            "lng": forms.NumberInput(attrs={"step": "any", "data-sede-lng": "1", "placeholder": "-99.20"}),
            "radio_m": forms.NumberInput(attrs={"min": 20, "max": 5000, "data-sede-radio": "1"}),
            "orden": forms.NumberInput(attrs={"min": 0, "max": 999}),
            "notas": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "nombre": "Nombre de la sede",
            "direccion": "Dirección",
            "lat": "Latitud",
            "lng": "Longitud",
            "radio_m": "Radio de la geocerca (metros)",
            "activa": "Activa (cuenta como ubicación válida)",
            "orden": "Orden",
            "notas": "Notas",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["direccion"].required = False
        self.fields["lat"].required = False
        self.fields["lng"].required = False
        self.fields["notas"].required = False


class ConfiguracionGeocercaForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionGeocerca
        fields = ["modo"]
        widgets = {"modo": forms.RadioSelect}
        labels = {"modo": "Modo de geocerca"}
