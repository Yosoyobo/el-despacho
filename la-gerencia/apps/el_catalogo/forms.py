from django import forms

from .models import CategoriaServicio, Servicio


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = CategoriaServicio
        fields = ["nombre", "orden", "activa"]


class ServicioForm(forms.ModelForm):
    class Meta:
        model = Servicio
        fields = ["nombre", "descripcion_default", "unidad", "precio_base", "categoria", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo categorías activas en el selector (la categoría actual sigue válida al editar).
        qs = CategoriaServicio.objects.filter(activa=True)
        if self.instance.pk and self.instance.categoria_id:
            qs = CategoriaServicio.objects.filter(
                pk__in=list(qs.values_list("pk", flat=True)) + [self.instance.categoria_id]
            )
        self.fields["categoria"].queryset = qs.distinct()
