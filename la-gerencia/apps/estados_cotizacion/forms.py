from apps.cotizaciones.models import EstadoCotizacion
from django import forms
from django.utils.text import slugify


class EstadoCotizacionForm(forms.ModelForm):
    # Color opcional: vacío → default gris. HEX inválido lo rechaza el
    # RegexValidator del modelo (EstadoCotizacion.color).
    color = forms.CharField(required=False, label="Color")

    class Meta:
        model = EstadoCotizacion
        fields = ["label", "descripcion", "color", "orden", "terminal", "activo"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Ej. En revisión del cliente"}),
            "descripcion": forms.TextInput(attrs={"placeholder": "Ej. El cliente está revisando la propuesta"}),
            "orden": forms.NumberInput(attrs={"min": 0, "max": 999}),
        }
        labels = {
            "label": "Nombre visible",
            "descripcion": "Significado (ayuda para el equipo)",
            "color": "Color del badge",
            "orden": "Orden (controla el pizza-tracker y el dropdown)",
            "terminal": "Es paso final (ej. Pagada)",
            "activo": "Activo (visible en el recuadro de Cotizaciones)",
        }

    def clean_color(self):
        return (self.cleaned_data.get("color") or "").strip() or "#667085"


class EstadoCotizacionNuevoForm(EstadoCotizacionForm):
    """Permite definir el slug solo al crear (no al editar)."""

    slug = forms.SlugField(
        max_length=32,
        help_text="Identificador interno; minúsculas y guiones bajos (ej. revision_cliente).",
        required=False,
    )

    class Meta(EstadoCotizacionForm.Meta):
        fields = ["slug", "label", "descripcion", "color", "orden", "terminal", "activo"]

    def clean(self):
        cleaned = super().clean()
        slug = (cleaned.get("slug") or "").strip()
        if not slug:
            label = cleaned.get("label") or ""
            slug = slugify(label).replace("-", "_")[:32] or "estado_nuevo"
        cleaned["slug"] = slug
        if EstadoCotizacion.objects.filter(slug=slug).exists():
            raise forms.ValidationError(f"Ya existe un estado con slug «{slug}». Elige otro.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.slug = self.cleaned_data["slug"]
        obj.sistema = False
        if commit:
            obj.save()
        return obj
