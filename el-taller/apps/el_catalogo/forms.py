from django import forms

from .models import CategoriaServicio, Servicio, Variacion


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = CategoriaServicio
        fields = ["nombre", "orden", "activa"]


class ServicioForm(forms.ModelForm):
    activo = forms.BooleanField(required=False, label="Disponible", initial=True)

    class Meta:
        model = Servicio
        fields = ["nombre", "descripcion_default", "unidad", "precio_base", "categoria", "activo"]
        labels = {
            "nombre": "Nombre",
            "descripcion_default": "Descripción",
            "unidad": "Unidad",
            "precio_base": "Precio base",
            "categoria": "Categoría",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = CategoriaServicio.objects.filter(activa=True)
        if self.instance.pk and self.instance.categoria_id:
            qs = CategoriaServicio.objects.filter(
                pk__in=list(qs.values_list("pk", flat=True)) + [self.instance.categoria_id]
            )
        self.fields["categoria"].queryset = qs.distinct()


class VariacionForm(forms.ModelForm):
    disponible = forms.BooleanField(required=False, label="Disponible", initial=True)
    impresion_activa = forms.BooleanField(required=False, label="Lleva impresión", initial=False)

    class Meta:
        model = Variacion
        fields = [
            "nombre", "descripcion", "costo",
            "impresion_activa", "impresion_costo", "impresion_descripcion",
            "disponible",
        ]
        labels = {
            "nombre": "Variación",
            "descripcion": "Detalles (tela, tamaño, color, tintas)",
            "costo": "Costo (sin IVA)",
            "impresion_costo": "Costo de impresión",
            "impresion_descripcion": "Detalle de impresión",
        }
