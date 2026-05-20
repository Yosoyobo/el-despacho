"""Form de CentroDeCosto vivo en La Gerencia.

NO importamos de `apps.tesoreria.forms` porque ese módulo define
también `IngresoForm` y `EgresoForm` con FKs a `cartera.Cliente` /
`proyectos.Proyecto` — apps que NO están instaladas en La Gerencia.
La metaclass de ModelForm intenta crear form fields al evaluar la
clase y revienta con `Cannot create form field for 'cliente' yet`
(detectado en CI smoke test de S2b.3).

Mantener este form aquí cuesta una copia pequeña; importar el de
Taller arrastraría toda la cadena de modelos del Taller a Gerencia.
"""

from apps.tesoreria.models import CentroDeCosto
from django import forms
from django.utils.text import slugify

CSS_INPUT = (
    "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm "
    "text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none "
    "focus:ring-2 focus:ring-brand-500/20 dark:border-gray-700 dark:bg-gray-900 "
    "dark:text-gray-100 dark:placeholder-gray-500"
)


class CentroDeCostoForm(forms.ModelForm):
    class Meta:
        model = CentroDeCosto
        fields = ["nombre", "descripcion", "naturaleza", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " " + CSS_INPUT).strip()

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
