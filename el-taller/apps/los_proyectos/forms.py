from datetime import datetime, time
from decimal import Decimal

from apps.el_catalogo.models import Proveedor, Servicio, Variacion
from apps.la_cartera.models import Cliente
from apps.los_proyectos.models import (
    ESTADOS_PROYECTO,
    EstadoProyecto,
    Proyecto,
    ProyectoAsignacion,
    ProyectoProducto,
    ProyectoProveedor,
)
from apps.tesoreria.models.ingreso import METODOS_INGRESO
from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.utils import timezone

from cuentas.models.usuario import Usuario

# C6 S-LC-Feedback-V6: hora por default en los campos fecha+hora del proyecto.
HORA_DEFAULT = time(12, 0)


class FechaHoraMixin:
    """Reemplaza campos DateTimeField del modelo por un par día + hora en el
    form, con la hora default a las 12:00 PM (pedido de LC).

    Declarar `pares_fecha_hora = (("fecha_inicio", "Inicio"), ...)`. Los campos
    del modelo NO deben estar en Meta.fields — el mixin los asigna en save().
    """

    pares_fecha_hora: tuple = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo, label in self.pares_fecha_hora:
            actual = getattr(getattr(self, "instance", None), campo, None)
            local = timezone.localtime(actual) if actual else None
            # `<input type="date">` SOLO acepta ISO (YYYY-MM-DD) para mostrar y
            # enviar el valor. Sin `format="%Y-%m-%d"` el widget rendea
            # "11/06/2026" (locale es-mx), el navegador lo rechaza y el campo
            # queda en blanco — el autoguardado lo mandaba vacío y BORRABA la
            # fecha. Forzamos ISO en render y aceptamos ISO al parsear.
            self.fields[f"{campo}_dia"] = forms.DateField(
                required=False, label=label,
                widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                input_formats=["%Y-%m-%d", "%d/%m/%Y"],
                initial=local.date() if local else None,
            )
            self.fields[f"{campo}_hora"] = forms.TimeField(
                required=False, label="Hora",
                widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
                input_formats=["%H:%M", "%H:%M:%S"],
                initial=local.time().replace(second=0, microsecond=0) if local else HORA_DEFAULT,
            )

    def clean(self):
        cleaned = super().clean()
        for campo, _label in self.pares_fecha_hora:
            dia = cleaned.get(f"{campo}_dia")
            hora = cleaned.get(f"{campo}_hora") or HORA_DEFAULT
            if dia:
                dt = datetime.combine(dia, hora)
                cleaned[campo] = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
            else:
                cleaned[campo] = None
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        for campo, _label in self.pares_fecha_hora:
            setattr(obj, campo, self.cleaned_data.get(campo))
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class ProyectoForm(FechaHoraMixin, forms.ModelForm):
    cliente = forms.ModelChoiceField(queryset=Cliente.activos.all())
    estado = forms.ChoiceField(choices=[])
    pares_fecha_hora = (("fecha_inicio", "Inicio"), ("fecha_compromiso", "Entrega"))
    # Render-V1: toggle "Aplicar IVA (16%)" = inverso de iva_exento. ON = se
    # cobra IVA. Más natural para el usuario que un check "exento".
    aplicar_iva = forms.BooleanField(
        required=False, initial=True, label="Aplicar IVA (16%)",
        widget=forms.CheckboxInput(attrs={"class": "peer sr-only"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = _choices_estado_activos()
        inst = getattr(self, "instance", None)
        if inst is not None and inst.pk:
            self.fields["aplicar_iva"].initial = not inst.iva_exento
        self.order_fields([
            "nombre", "cliente", "descripcion", "estado",
            "fecha_inicio_dia", "fecha_inicio_hora",
            "fecha_compromiso_dia", "fecha_compromiso_hora",
            "aplicar_iva",
        ])

    def save(self, commit=True):
        obj = super().save(commit=False)  # FechaHoraMixin: setea fechas, no guarda
        obj.iva_exento = not self.cleaned_data.get("aplicar_iva", True)
        if commit:
            obj.save()
            self.save_m2m()
        return obj

    class Meta:
        model = Proyecto
        fields = [
            "nombre",
            "cliente",
            "descripcion",
            "estado",
        ]
        widgets = {
            # S-LC-Feedback-V4: autocomplete @#$ en nombre y descripción.
            "nombre": forms.TextInput(attrs={"data-referencias": "1"}),
            "descripcion": forms.Textarea(attrs={"data-referencias": "1", "rows": 4}),
        }


def _choices_estado_activos():
    try:
        return [(e.slug, e.label) for e in EstadoProyecto.objects.filter(activo=True).order_by("orden")]
    except Exception:
        return list(ESTADOS_PROYECTO)


class CambiarEstadoForm(forms.Form):
    estado = forms.ChoiceField(choices=[])
    fecha_real_entrega = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = _choices_estado_activos()


class EditarFechasForm(FechaHoraMixin, forms.ModelForm):
    """S-LC-Feedback-V5 c4 — edición rápida de fechas desde el detalle.

    C6 S-LC-Feedback-V6: solo Inicio + Entrega, con hora (default 12:00).
    'Entrega real' se setea al marcar el proyecto como entregado.
    """

    pares_fecha_hora = (("fecha_inicio", "Inicio"), ("fecha_compromiso", "Entrega"))

    class Meta:
        model = Proyecto
        fields: list = []


class EditarEconomicoForm(forms.ModelForm):
    """S-LC-Feedback-V5 c4 — edición rápida del bloque económico."""

    class Meta:
        model = Proyecto
        fields = ["monto_estimado", "monto_cotizado", "monto_facturado"]
        labels = {
            "monto_estimado": "Monto estimado",
            "monto_cotizado": "Monto cotizado",
            "monto_facturado": "Monto facturado",
        }


class ProyectoProductoForm(forms.ModelForm):
    servicio = forms.ModelChoiceField(
        queryset=Servicio.activos.all().select_related("categoria"),
        required=False,
        empty_label="— Elige un producto —",
        label="Producto",
    )
    variacion = forms.ModelChoiceField(
        queryset=Variacion.objects.filter(disponible=True).select_related("servicio"),
        required=False,
        empty_label="— Sin variación específica —",
        label="Variación",
    )
    # S-LC-Proyecto-Render-V1: proveedor principal del producto.
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.filter(activo=True).order_by("razon_social"),
        required=False,
        empty_label="— Proveedor —",
        label="Proveedor",
    )
    # Procesos (impresión + operativos) serializados en JSON por el front;
    # la vista los sincroniza a ProyectoProductoProceso tras guardar el form.
    procesos_json = forms.CharField(required=False, widget=forms.HiddenInput())
    # required=False + clean (abajo): una cantidad vacía en CUALQUIER fila no debe
    # invalidar todo el formset del detalle y bloquear silenciosamente el toggle
    # "incluir" de otra fila (reporte Oscar: "el botón de incluir no jala").
    cantidad = forms.IntegerField(required=False, min_value=1, initial=1, label="Cantidad")
    precio_unitario = forms.DecimalField(
        required=False, min_value=0, label="Precio unit.",
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "catálogo"}),
    )
    costo_unitario = forms.DecimalField(
        required=False, min_value=0, label="Costo unit.",
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "catálogo"}),
    )
    merma = forms.IntegerField(
        required=False, min_value=0, initial=0, label="Merma",
        widget=forms.NumberInput(attrs={"placeholder": "0"}),
    )
    incluir_en_calculo = forms.BooleanField(
        required=False, initial=True, label="Incluir en cálculo",
        widget=forms.CheckboxInput(attrs={"class": "peer sr-only", "data-incluir": "1"}),
    )

    class Meta:
        model = ProyectoProducto
        fields = ["servicio", "variacion", "proveedor", "cantidad", "precio_unitario", "costo_unitario", "merma", "incluir_en_calculo", "nota"]
        labels = {"nota": "Nota corta (opcional)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bug Oscar 2026-06-29: al abrir un proyecto existente, las tarjetas
        # mostraban "— Producto del catálogo —" en vez del nombre, y "catálogo"
        # (placeholder) en vez del precio/costo. Dos causas:
        #  (a) el queryset de `servicio`/`variacion`/`proveedor` solo trae los
        #      ACTIVOS; si la línea apunta a uno archivado/inactivo, el valor
        #      guardado no es una opción seleccionable y cae al empty_label.
        #  (b) precio/costo vacíos (= "usa el del catálogo") muestran el
        #      placeholder en vez del número real.
        # Para líneas EXISTENTES garantizamos que el valor actual sea una opción
        # válida y que el precio/costo efectivo se muestre.
        inst = getattr(self, "instance", None)
        if inst is not None and inst.pk:
            if inst.servicio_id:
                self.fields["servicio"].queryset = (
                    Servicio.objects.filter(Q(activo=True) | Q(pk=inst.servicio_id))
                    .select_related("categoria")
                )
            if inst.variacion_id:
                self.fields["variacion"].queryset = (
                    Variacion.objects.filter(Q(disponible=True) | Q(pk=inst.variacion_id))
                    .select_related("servicio")
                )
            if inst.proveedor_id:
                self.fields["proveedor"].queryset = (
                    Proveedor.objects.filter(Q(activo=True) | Q(pk=inst.proveedor_id))
                    .order_by("razon_social")
                )
            # Muestra el precio/costo EFECTIVO (override de la línea o, si está
            # vacío, el del catálogo) para que el usuario siempre vea el número.
            if inst.servicio_id:
                if inst.precio_unitario is None:
                    self.initial["precio_unitario"] = inst.precio_efectivo
                if inst.costo_unitario is None:
                    self.initial["costo_unitario"] = inst.costo_efectivo

    def clean_merma(self):
        # merma es NOT NULL con default 0; el form vacío llega como None.
        return self.cleaned_data.get("merma") or 0

    def clean_cantidad(self):
        # cantidad es NOT NULL con default 1; vacío/None ⇒ 1 (no invalida la fila).
        return self.cleaned_data.get("cantidad") or 1

    def clean(self):
        cleaned = super().clean()
        # El modelo exige servicio (NOT NULL). Una tarjeta nueva inline que se
        # llenó parcialmente (cantidad/precio) pero sin producto truena al
        # guardar; un error claro es mejor que un 500. Las filas intactas/vacías
        # las ignora el formset (has_changed=False), y las marcadas DELETE no se
        # validan.
        if not cleaned.get("servicio") and not self.cleaned_data.get("DELETE") and self.has_changed():
            self.add_error("servicio", "Elige un producto del catálogo.")
        return cleaned


ProyectoProductoFormSet = inlineformset_factory(
    Proyecto, ProyectoProducto, form=ProyectoProductoForm,
    extra=1, can_delete=True,
)
ProyectoProductoFormSetEdit = inlineformset_factory(
    Proyecto, ProyectoProducto, form=ProyectoProductoForm,
    extra=1, can_delete=True,
)
# S-LC-Feedback-V8: en el DETALLE (con autoguardado) NO se agregan productos
# inline — se agregan por el modal atómico. extra=0 evita la tarjeta vacía que,
# combinada con el autosave + hx-swap=none, duplicaba productos (el pk nuevo
# nunca se sincronizaba al cliente). Aquí el formset solo EDITA/borra existentes.
ProyectoProductoFormSetDetalle = inlineformset_factory(
    Proyecto, ProyectoProducto, form=ProyectoProductoForm,
    extra=0, can_delete=True,
)


class ProyectoProveedorForm(FechaHoraMixin, forms.ModelForm):
    """C5 S-LC-Feedback-V6 — asignar un proveedor a un proyecto con su
    compromiso de entrega/recolección (fecha+hora), contacto y ubicación."""

    pares_fecha_hora = (("compromiso", "Fecha de compromiso"),)
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.filter(activo=True).order_by("razon_social"),
        label="Proveedor",
    )

    class Meta:
        model = ProyectoProveedor
        fields = ["proveedor", "tipo", "contacto", "ubicacion", "nota"]
        labels = {
            "tipo": "Tipo",
            "contacto": "Contacto",
            "ubicacion": "Ubicación",
            "nota": "Nota (opcional)",
        }
        widgets = {
            "ubicacion": forms.TextInput(attrs={"placeholder": "Dirección o referencia"}),
            "contacto": forms.TextInput(attrs={"placeholder": "Nombre / teléfono"}),
        }


class ClienteInlineForm(forms.ModelForm):
    """Form minimalista para crear un Cliente nuevo desde el modal del form de Proyecto."""

    class Meta:
        model = Cliente
        fields = ["razon_social", "rfc", "nombre_contacto", "email_contacto", "telefono"]


class AsignacionForm(forms.ModelForm):
    usuario = forms.ModelChoiceField(queryset=Usuario.objects.filter(is_active=True).order_by("nombre_completo"))

    class Meta:
        model = ProyectoAsignacion
        fields = ["usuario", "rol_en_proyecto"]


class RegistrarAnticipoForm(forms.Form):
    """S-LC-Feedback-V13 — registro rápido del ingreso de un anticipo desde el
    recuadro de Cotizaciones del proyecto. SIN monto predeterminado; la UI
    ofrece botones rápidos (25/50/100%) o monto personalizado. El ingreso queda
    ligado al proyecto."""

    monto = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
        label="Monto del anticipo",
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
    )
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="Fecha",
    )
    metodo = forms.ChoiceField(choices=METODOS_INGRESO, initial="transferencia", label="Método")
    banco_o_caja = forms.ChoiceField(
        choices=(("banco", "Banco"), ("caja", "Caja")), initial="banco",
        label="Cuenta destino",
    )
