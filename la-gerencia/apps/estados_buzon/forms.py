from django import forms
from django.utils.text import slugify

from buzon.models import EstadoBuzon


class EstadoBuzonForm(forms.ModelForm):
    # Color opcional: vacío → default gris. HEX inválido se rechaza vía el
    # validador del modelo (RegexValidator en EstadoBuzon.color).
    color = forms.CharField(required=False, label="Color")

    class Meta:
        model = EstadoBuzon
        fields = ["label", "descripcion", "color", "accion", "orden", "terminal", "activo"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Ej. En seguimiento"}),
            "descripcion": forms.TextInput(attrs={"placeholder": "Ej. Esperando información del autor"}),
            "orden": forms.NumberInput(attrs={"min": 0, "max": 999}),
        }
        labels = {
            "label": "Nombre visible",
            "descripcion": "Significado (ayuda para el equipo)",
            "color": "Color del badge",
            "accion": "Acción automática al entrar a este estado",
            "orden": "Orden",
            "terminal": "Es estado terminal (cierra el ticket)",
            "activo": "Activo (visible en dropdowns)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `accion` y `descripcion` son opcionales: si no vienen, usamos el
        # default ("ninguna" / "") sin invalidar el form.
        self.fields["accion"].required = False

    def clean_color(self):
        return (self.cleaned_data.get("color") or "").strip() or "#667085"

    def clean_accion(self):
        return self.cleaned_data.get("accion") or "ninguna"


class EstadoBuzonNuevoForm(EstadoBuzonForm):
    """Permite definir el slug solo al crear (no al editar)."""

    slug = forms.SlugField(
        max_length=32,
        help_text="Identificador interno; minúsculas y guiones bajos (ej. en_seguimiento).",
        required=False,
    )

    class Meta(EstadoBuzonForm.Meta):
        fields = ["slug", "label", "descripcion", "color", "accion", "orden", "terminal", "activo"]

    def clean(self):
        cleaned = super().clean()
        slug = (cleaned.get("slug") or "").strip()
        if not slug:
            label = cleaned.get("label") or ""
            slug = slugify(label).replace("-", "_")[:32] or "estado_nuevo"
        cleaned["slug"] = slug
        if EstadoBuzon.objects.filter(slug=slug).exists():
            raise forms.ValidationError(f"Ya existe un estado con slug «{slug}». Elige otro.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.slug = self.cleaned_data["slug"]
        obj.sistema = False
        if commit:
            obj.save()
        return obj
