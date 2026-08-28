from django import forms

from .models import (
    CategoriaProveedor,
    CategoriaServicio,
    Proveedor,
    Servicio,
    SubcategoriaProveedor,
)


class ProveedorForm(forms.ModelForm):
    activo = forms.BooleanField(required=False, label="Activo", initial=True)
    # LC 2026-07: clasificación por subcategorías (checkboxes en el template,
    # agrupadas por categoría core).
    subcategorias = forms.ModelMultipleChoiceField(
        queryset=SubcategoriaProveedor.objects.filter(activa=True),
        required=False, widget=forms.CheckboxSelectMultiple, label="Subcategorías",
    )

    class Meta:
        model = Proveedor
        fields = [
            "razon_social", "nombre_contacto", "email_contacto",
            "telefono", "rfc", "direccion", "fiscal_igual", "direccion_fiscal",
            "lat", "lng", "notas", "subcategorias", "activo",
        ]
        # Render LC 2026-06-30: "Razón social" → "Nombre" (solo etiqueta; el
        # campo en DB sigue siendo `razon_social`, igual que Cliente).
        labels = {
            "razon_social": "Nombre",
            "nombre_contacto": "Persona de contacto",
            "email_contacto": "Email",
            "telefono": "Teléfono",
            "rfc": "RFC",
            "direccion": "Dirección",
            "fiscal_igual": "La dirección fiscal es la misma",
            "direccion_fiscal": "Dirección fiscal",
            "notas": "Notas",
        }
        widgets = {
            # La dirección usa el buscador de direcciones (geo-picker), no las
            # referencias @#$ — y así no hay dos dropdowns en el mismo campo.
            "direccion": forms.Textarea(attrs={"rows": 2}),
            "direccion_fiscal": forms.Textarea(attrs={"rows": 2, "data-fiscal-box": "1"}),
            "notas": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
            # Coordenadas del pin (geo-picker) — ocultas, las llena el mini-mapa.
            "lat": forms.HiddenInput(),
            "lng": forms.HiddenInput(),
        }

    def __init__(self, *args, inline: bool = False, **kwargs):
        """`inline=True` quita el campo `activo` para el detalle editable en
        línea (el alta/baja vive en su propio botón). Al no estar en
        `self.fields`, `construct_instance` no toca `instance.activo`, así que
        el autoguardado no desactiva al proveedor por accidente."""
        super().__init__(*args, **kwargs)
        if inline and "activo" in self.fields:
            self.fields.pop("activo")


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


class CategoriaProveedorForm(forms.ModelForm):
    """Edición de una de las 6 categorías CORE de proveedor (nombre + color).
    Las subcategorías heredan su color (LC 2026-07)."""
    color = forms.CharField(required=False, label="Color")

    class Meta:
        from .models import CategoriaProveedor  # noqa: PLC0415
        model = CategoriaProveedor
        fields = ["nombre", "color", "orden", "activa"]
        labels = {"color": "Color", "activa": "Activa"}

    def clean_color(self):
        return (self.cleaned_data.get("color") or "").strip() or "#667085"


class SubcategoriaProveedorForm(forms.ModelForm):
    """Alta/edición de una subcategoría de proveedor. Hereda el color de su
    categoría CORE (LC #164). El `slug` se autogenera en la vista."""
    activa = forms.BooleanField(required=False, label="Activa", initial=True)

    class Meta:
        model = SubcategoriaProveedor
        fields = ["categoria", "nombre", "orden", "activa"]
        labels = {
            "categoria": "Categoría principal",
            "nombre": "Nombre",
            "orden": "Orden (menor = primero)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = (
            CategoriaProveedor.objects.filter(activa=True).order_by("orden", "nombre")
        )


class ServicioForm(forms.ModelForm):
    # S-LC-Feedback-V3: costo opcional con default 0 (margen 100% si no se captura).
    costo = forms.DecimalField(required=False, initial=0, min_value=0,
                                label="Costo",
                                help_text="Lo que te cuesta producir o comprar. Usado para calcular margen.")

    class Meta:
        model = Servicio
        # Sprint Fiscal 2026-07 (#12 unidad, #10 disponible): la unidad se
        # consolidó a 'pz' (fija por dentro, sin selector) y el estado
        # «Disponible» se jubiló (archivar vive en su propio botón). Ambos
        # campos salen del form.
        # LC 2026-08-28 (Oscar): `proveedor_principal` sale del formulario. Ya no
        # se elige en un segundo control: es el PRIMERO que se marcó, y de eso se
        # encarga `proveedores_orden` (abajo) + la vista al guardar.
        fields = ["nombre", "descripcion_default", "costo", "precio_base", "categoria", "proveedores"]
        labels = {
            "nombre": "Nombre",
            "descripcion_default": "Descripción",
            "costo": "Costo",
            "precio_base": "Precio de venta",
            "categoria": "Categoría",
        }
        help_texts = {
            "costo": "Lo que te cuesta producir o comprar este producto. Usado para calcular margen.",
            "precio_base": "Precio sugerido al que lo vendes. El margen se calcula automáticamente.",
        }
        widgets = {
            # LC 2026-08-28 (Oscar): «el nombre del producto debe de ser lo más
            # protagonista de la página». Es el dato con el que se le nombra en
            # todo el sistema, así que se captura en grande.
            "nombre": forms.TextInput(attrs={
                "class": "text-lg font-semibold",
                "placeholder": "Ej. Playera Dry Fit",
                "autocomplete": "off",
            }),
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
        # LC 2026-08-28 (Oscar): «hay varios selectores de proveedores. Dejemos
        # sólo uno, y al agregarlos en orden el primero queda como principal».
        # El orden de marcado viaja en este campo oculto (lo llena el control de
        # palomitas) porque el orden del POST no basta: los checkboxes se envían
        # en el orden del DOM, que es alfabético.
        #
        # El principal SIGUE siendo un campo del modelo —es la fuente de verdad
        # que consulta `proveedor_default`—, sólo dejó de elegirse a mano.
        self.fields["proveedores_orden"] = forms.CharField(
            required=False, widget=forms.HiddenInput(attrs={"id": "id_proveedores_orden"}),
        )
        self.initial.setdefault("proveedores_orden", self.orden_inicial())

    def orden_inicial(self) -> str:
        """El orden con el que se abre la ficha: el principal primero.

        Así la estrella señala a quien está guardado como principal en vez de al
        primero alfabético.
        """
        if not self.instance.pk:
            return ""
        ids = [str(p) for p in self.instance.proveedores.values_list("pk", flat=True)]
        principal = self.instance.proveedor_principal_id
        if principal and str(principal) in ids:
            ids.remove(str(principal))
            ids.insert(0, str(principal))
        return ",".join(ids)

    def principal_elegido(self, ligados) -> int | None:
        """Quién quedó como principal: el PRIMERO de los que se marcaron.

        `ligados` son los pks que de verdad quedaron en la relación. Se prefiere
        el orden que mandó la pantalla y, si no vino (un POST viejo o el alta
        rápida), el orden en que llegaron los checkboxes.
        """
        ligados = set(ligados)
        crudo = (self.data.get("proveedores_orden") or "").strip()
        orden = [int(x) for x in crudo.split(",") if x.strip().isdigit()] if crudo else []
        for pk in orden:
            if pk in ligados:
                return pk
        for crudo_pk in self.data.getlist("proveedores") if hasattr(self.data, "getlist") else []:
            if str(crudo_pk).strip().isdigit() and int(crudo_pk) in ligados:
                return int(crudo_pk)
        return None

    def clean_costo(self):
        v = self.cleaned_data.get("costo")
        return v if v is not None else 0
