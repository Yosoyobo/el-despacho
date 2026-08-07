from apps.los_proyectos.models import MotivoCancelacion
from django import forms
from django.utils.text import slugify


class MotivoCancelacionForm(forms.ModelForm):
    class Meta:
        model = MotivoCancelacion
        fields = ["label", "orden", "activo"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Ej. Presupuesto del cliente"}),
            "orden": forms.NumberInput(attrs={"min": 0, "max": 999}),
        }
        labels = {
            "label": "Nombre visible",
            "orden": "Orden",
            "activo": "Activo (se ofrece al cancelar)",
        }


class MotivoCancelacionNuevoForm(MotivoCancelacionForm):
    """Permite definir el slug sólo al crear (no al editar)."""

    slug = forms.SlugField(
        max_length=40,
        help_text="Identificador interno; minúsculas y guiones bajos (ej. presupuesto).",
        required=False,
    )

    class Meta(MotivoCancelacionForm.Meta):
        fields = ["slug", "label", "orden", "activo"]

    def clean(self):
        cleaned = super().clean()
        slug = (cleaned.get("slug") or "").strip()
        if not slug:
            slug = slugify(cleaned.get("label") or "").replace("-", "_")[:40] or "motivo_nuevo"
        cleaned["slug"] = slug
        if MotivoCancelacion.objects.filter(slug=slug).exists():
            raise forms.ValidationError(f"Ya existe un motivo con slug «{slug}». Elige otro.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.slug = self.cleaned_data["slug"]
        obj.sistema = False
        if commit:
            obj.save()
        return obj
