from apps.el_pizarron.models import EstadoTarea
from django import forms
from django.utils.text import slugify


class EstadoTareaForm(forms.ModelForm):
    # Color opcional: vacío → default gris. HEX inválido se rechaza vía el
    # validador del modelo (RegexValidator en EstadoTarea.color).
    color = forms.CharField(required=False, label="Color")

    class Meta:
        model = EstadoTarea
        fields = ["label", "color", "orden", "terminal", "activo"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Ej. En revisión"}),
            "orden": forms.NumberInput(attrs={"min": 0, "max": 999}),
        }
        labels = {
            "label": "Nombre visible",
            "color": "Color del badge",
            "orden": "Orden",
            "terminal": "Es estado terminal (cierra la tarea)",
            "activo": "Activo (visible en dropdowns)",
        }

    def clean_color(self):
        return (self.cleaned_data.get("color") or "").strip() or "#667085"


class EstadoTareaNuevoForm(EstadoTareaForm):
    """Permite definir el slug solo al crear (no al editar)."""

    slug = forms.SlugField(
        max_length=32,
        help_text="Identificador interno; minúsculas y guiones bajos (ej. en_revision).",
        required=False,
    )

    class Meta(EstadoTareaForm.Meta):
        fields = ["slug", "label", "color", "orden", "terminal", "activo"]

    def clean(self):
        cleaned = super().clean()
        slug = (cleaned.get("slug") or "").strip()
        if not slug:
            label = cleaned.get("label") or ""
            slug = slugify(label).replace("-", "_")[:32] or "estado_nuevo"
        cleaned["slug"] = slug
        if EstadoTarea.objects.filter(slug=slug).exists():
            raise forms.ValidationError(f"Ya existe un estado con slug «{slug}». Elige otro.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.slug = self.cleaned_data["slug"]
        obj.sistema = False
        if commit:
            obj.save()
        return obj
