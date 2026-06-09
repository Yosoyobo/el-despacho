from django import forms
from django.utils.text import slugify

from buzon.models import TipoBuzon


class TipoBuzonForm(forms.ModelForm):
    color = forms.CharField(required=False, label="Color")

    class Meta:
        model = TipoBuzon
        fields = ["label", "color", "orden", "activo"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Ej. Felicitación"}),
            "orden": forms.NumberInput(attrs={"min": 0, "max": 999}),
        }
        labels = {
            "label": "Nombre visible",
            "color": "Color del badge",
            "orden": "Orden",
            "activo": "Activo (visible en el selector y filtros)",
        }

    def clean_color(self):
        return (self.cleaned_data.get("color") or "").strip() or "#667085"


class TipoBuzonNuevoForm(TipoBuzonForm):
    """Permite definir el slug solo al crear (no al editar)."""

    slug = forms.SlugField(
        max_length=32,
        help_text="Identificador interno; minúsculas y guiones bajos (ej. felicitacion).",
        required=False,
    )

    class Meta(TipoBuzonForm.Meta):
        fields = ["slug", "label", "color", "orden", "activo"]

    def clean(self):
        cleaned = super().clean()
        slug = (cleaned.get("slug") or "").strip()
        if not slug:
            label = cleaned.get("label") or ""
            slug = slugify(label).replace("-", "_")[:32] or "tipo_nuevo"
        cleaned["slug"] = slug
        if TipoBuzon.objects.filter(slug=slug).exists():
            raise forms.ValidationError(f"Ya existe un tipo con slug «{slug}». Elige otro.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.slug = self.cleaned_data["slug"]
        obj.sistema = False
        if commit:
            obj.save()
        return obj
