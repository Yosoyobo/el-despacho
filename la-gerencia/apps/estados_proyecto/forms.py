from apps.los_proyectos.models import EstadoProyecto
from django import forms
from django.utils.text import slugify


class EstadoProyectoForm(forms.ModelForm):
    class Meta:
        model = EstadoProyecto
        fields = ["label", "color", "orden", "terminal", "activo"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Ej. En revisión interna"}),
            "orden": forms.NumberInput(attrs={"min": 0, "max": 999}),
        }
        labels = {
            "label": "Nombre visible",
            "color": "Color del badge",
            "orden": "Orden",
            "terminal": "Es estado terminal (cierra el proyecto)",
            "activo": "Activo (visible en dropdowns)",
        }


class EstadoProyectoNuevoForm(EstadoProyectoForm):
    """Permite definir el slug solo al crear (no al editar)."""

    slug = forms.SlugField(
        max_length=32,
        help_text="Identificador interno; minúsculas y guiones bajos (ej. revision_interna).",
        required=False,
    )

    class Meta(EstadoProyectoForm.Meta):
        fields = ["slug", "label", "color", "orden", "terminal", "activo"]

    def clean(self):
        cleaned = super().clean()
        slug = (cleaned.get("slug") or "").strip()
        if not slug:
            label = cleaned.get("label") or ""
            slug = slugify(label).replace("-", "_")[:32] or "estado_nuevo"
        cleaned["slug"] = slug
        if EstadoProyecto.objects.filter(slug=slug).exists():
            raise forms.ValidationError(f"Ya existe un estado con slug «{slug}». Elige otro.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.slug = self.cleaned_data["slug"]
        obj.sistema = False
        if commit:
            obj.save()
        return obj
