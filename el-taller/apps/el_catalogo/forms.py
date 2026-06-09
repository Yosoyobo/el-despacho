from django import forms

from .models import CategoriaServicio, Proveedor, Servicio, Unidad, Variacion


class ProveedorForm(forms.ModelForm):
    activo = forms.BooleanField(required=False, label="Activo", initial=True)

    class Meta:
        model = Proveedor
        fields = [
            "razon_social", "nombre_contacto", "email_contacto",
            "telefono", "rfc", "direccion", "notas", "activo",
        ]
        labels = {
            "razon_social": "Razón social",
            "nombre_contacto": "Persona de contacto",
            "email_contacto": "Email",
            "telefono": "Teléfono",
            "rfc": "RFC",
            "direccion": "Dirección",
            "notas": "Notas",
        }
        widgets = {
            "direccion": forms.Textarea(attrs={"data-referencias": "1", "rows": 2}),
            "notas": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
        }


class UnidadForm(forms.ModelForm):
    activa = forms.BooleanField(required=False, label="Disponible", initial=True)

    class Meta:
        model = Unidad
        fields = ["nombre", "abreviacion", "orden", "activa"]
        labels = {
            "nombre": "Nombre",
            "abreviacion": "Abreviación",
            "orden": "Orden",
        }


class CategoriaForm(forms.ModelForm):
    # Color opcional: si llega vacío, default gris (el partial lo pre-llena,
    # pero callers viejos / sin color no deben romper). El HEX inválido sí se
    # rechaza vía el validador del modelo.
    color = forms.CharField(required=False, label="Color")

    class Meta:
        model = CategoriaServicio
        fields = ["nombre", "color", "orden", "activa"]
        labels = {"color": "Color"}

    def clean_color(self):
        return (self.cleaned_data.get("color") or "").strip() or "#667085"


class ServicioForm(forms.ModelForm):
    activo = forms.BooleanField(required=False, label="Disponible", initial=True)
    # S-LC-Feedback-V3: costo opcional con default 0 (margen 100% si no se captura).
    costo = forms.DecimalField(required=False, initial=0, min_value=0,
                                label="Costo (lo que te cuesta)",
                                help_text="Lo que te cuesta producir o comprar. Usado para calcular margen.")

    class Meta:
        model = Servicio
        fields = ["nombre", "descripcion_default", "unidad", "costo", "precio_base", "categoria", "proveedores", "activo"]
        labels = {
            "nombre": "Nombre",
            "descripcion_default": "Descripción",
            "unidad": "Unidad",
            "costo": "Costo (lo que te cuesta)",
            "precio_base": "Precio de venta",
            "categoria": "Categoría",
        }
        help_texts = {
            "costo": "Lo que te cuesta producir o comprar este producto. Usado para calcular margen.",
            "precio_base": "Precio sugerido al que lo vendes. El margen se calcula automáticamente.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = CategoriaServicio.objects.filter(activa=True)
        if self.instance.pk and self.instance.categoria_id:
            qs = CategoriaServicio.objects.filter(
                pk__in=list(qs.values_list("pk", flat=True)) + [self.instance.categoria_id]
            )
        self.fields["categoria"].queryset = qs.distinct()
        # S-LC-Feedback-V5: proveedores como checkboxes (más obvio que <select multiple>).
        # Importante: el widget debe asignarse ANTES del queryset. El setter de queryset
        # propaga `choices` al widget actual; si reemplazamos después, el widget nuevo
        # queda sin choices y el template muestra "Aún no hay proveedores registrados".
        if "proveedores" in self.fields:
            self.fields["proveedores"].widget = forms.CheckboxSelectMultiple()
            self.fields["proveedores"].queryset = Proveedor.objects.filter(activo=True).order_by("razon_social")
            self.fields["proveedores"].required = False
            self.fields["proveedores"].label = "Proveedores aplicables"
            self.fields["proveedores"].help_text = "Marca quién te puede surtir este producto. Opcional."

    def clean_costo(self):
        v = self.cleaned_data.get("costo")
        return v if v is not None else 0


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
