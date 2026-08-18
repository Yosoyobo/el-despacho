from datetime import datetime, time
from decimal import Decimal

from apps.cotizaciones.models import Cotizacion
from apps.el_catalogo.models import Proveedor, Servicio, Variacion
from apps.la_cartera.models import Cliente
from apps.los_proyectos.models import (
    ESTADOS_PROYECTO,
    EstadoProyecto,
    Proyecto,
    ProyectoAsignacion,
    ProyectoProducto,
    ProyectoProductoVersion,
    ProyectoProveedor,
)
from apps.tesoreria.models.ingreso import METODOS_INGRESO
from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.utils import timezone

from cuentas.models.usuario import Usuario
from lib.fiscal import REGIMENES_FISCALES

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
    cliente = forms.ModelChoiceField(
        queryset=Cliente.activos.all(),
        widget=forms.Select(attrs={"data-select-buscable": "1"}),
    )
    estado = forms.ChoiceField(choices=[])
    pares_fecha_hora = (("fecha_inicio", "Inicio"), ("fecha_compromiso", "Entrega"))
    # LC 2026-07: el toggle IVA/exento pasa a un selector de régimen fiscal
    # (IVA 16% / IVA y Retenciones / Exento). Las cotizaciones y facturas del
    # proyecto lo heredan. Se sincroniza `iva_exento` por compatibilidad.
    regimen_fiscal = forms.ChoiceField(
        choices=REGIMENES_FISCALES, initial="honorarios", label="Impuestos",
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = _choices_estado_activos()
        # Opcional en el POST: el autoguardado del detalle no siempre manda el
        # régimen (se conserva el actual si no llega).
        self.fields["regimen_fiscal"].required = False
        inst = getattr(self, "instance", None)
        if inst is not None and inst.pk:
            self.fields["regimen_fiscal"].initial = inst.regimen_fiscal
        self.order_fields([
            "nombre", "cliente", "descripcion", "estado",
            "fecha_inicio_dia", "fecha_inicio_hora",
            "fecha_compromiso_dia", "fecha_compromiso_hora",
            "regimen_fiscal",
        ])

    def save(self, commit=True):
        obj = super().save(commit=False)  # FechaHoraMixin: setea fechas, no guarda
        reg = self.cleaned_data.get("regimen_fiscal") or (obj.regimen_fiscal or "honorarios")
        obj.regimen_fiscal = reg
        obj.iva_exento = reg == "exento"  # sincroniza el campo legacy
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


# LC 2026-08-18: los campos de dinero de la tarjeta aceptan una CUENTA escrita
# («35+15+15», «15.75*100», «2400/12»). La regla es una sola para el precio y el
# costo, así que vive aquí y no duplicada en cada `clean_*`.
_OPERADORES = "+-*/"


def _cuenta_del_campo(crudo, etiqueta: str) -> tuple:
    """`(total, cuenta_escrita)` de un campo que admite cuentas.

    Vacío ⇒ `(None, "")`, que en estos campos significa «hereda del catálogo».
    La cuenta sólo se conserva escrita si de verdad es una cuenta y no un número
    pelón: guardar «195» como «cuenta» no le sirve a nadie.
    """
    from apps.los_proyectos.services_procesos import suma_expresion

    texto = (crudo or "").strip()
    if not texto:
        return None, ""
    total = suma_expresion(texto)
    if total is None:
        raise forms.ValidationError(
            f"{etiqueta} inválido. Usa un número o una cuenta como 15.75*100.")
    if total < 0:
        raise forms.ValidationError(f"{etiqueta} no puede ser negativo.")
    expr = texto[:120] if any(c in _OPERADORES for c in texto[1:]) else ""
    return total, expr


class ProyectoProductoForm(forms.ModelForm):
    servicio = forms.ModelChoiceField(
        queryset=Servicio.activos.all().select_related("categoria", "proveedor_principal").prefetch_related("proveedores"),
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
    # LC 2026-07-26: procesos de VENTA (Ponchado, arte…) — se le cobran al
    # cliente como líneas propias de la cotización. Mismo mecanismo: el front los
    # serializa aquí y la vista los sincroniza a ProyectoProductoVenta.
    ventas_json = forms.CharField(required=False, widget=forms.HiddenInput())
    # LC 2026-08-17: escalas de volumen (Opción B, C…). Mismo mecanismo que los
    # dos de arriba; las reglas viven en `services_procesos.escalas_normalizadas`.
    escalas_json = forms.CharField(required=False, widget=forms.HiddenInput())
    # El OJO de la Opción A: si esta opción se imprime en la cotización. Checkbox
    # escondido que el ojo de la cabecera prende y apaga (CSS puro, sin JS).
    visible_pdf = forms.BooleanField(
        required=False, initial=True, label="Se imprime en la cotización",
        widget=forms.CheckboxInput(attrs={"class": "peer sr-only",
                                          "data-visible-pdf": "1"}),
    )
    # required=False + clean (abajo): una cantidad vacía en CUALQUIER fila no debe
    # invalidar todo el formset del detalle y bloquear silenciosamente el toggle
    # "incluir" de otra fila (reporte Oscar: "el botón de incluir no jala").
    cantidad = forms.IntegerField(
        required=False, min_value=1, initial=1, label="Cant.",
        widget=forms.NumberInput(attrs={"class": "campo-angosto", "placeholder": "1"}),
    )
    # LC 2026-08-18 (Oscar): el precio también acepta una CUENTA, con las cuatro
    # operaciones. Igual que el costo: es un campo de texto —un `type=number` ni
    # deja teclear el `*`— y el total lo saca el SERVIDOR, así que el monto
    # guardado siempre concuerda con lo escrito, venga el POST de donde venga.
    precio_unitario = forms.CharField(
        required=False, label="Precio unit.",
        widget=forms.TextInput(attrs={
            "inputmode": "text", "autocomplete": "off",
            "placeholder": "catálogo", "class": "precio-unit",
            "title": "Acepta una cuenta: escribe 2400/12 y se calcula solo "
                     "(la cuenta se queda escrita).",
        }),
    )
    # LC 2026-08-12 (Oscar): «habilitemos que también se pueda escribir y
    # calcular, por ejemplo 15.75*100». Un `type=number` ni deja teclear el `*`,
    # así que es texto y el SERVIDOR saca el total (`limpiar_costo_unitario`),
    # igual que el costo de la impresión.
    costo_unitario = forms.CharField(
        required=False, label="Costo unit.",
        widget=forms.TextInput(attrs={
            "inputmode": "text", "autocomplete": "off",
            "placeholder": "catálogo", "class": "costo-unit",
            "title": "Acepta una cuenta: escribe 15.75*100 y se calcula solo "
                     "(la cuenta se queda escrita).",
        }),
    )
    merma = forms.IntegerField(
        required=False, min_value=0, initial=0, label="Merma",
        widget=forms.NumberInput(attrs={"class": "campo-angosto", "placeholder": "0"}),
    )
    incluir_en_calculo = forms.BooleanField(
        required=False, initial=True, label="Incluir en cálculo",
        widget=forms.CheckboxInput(attrs={"class": "peer sr-only", "data-incluir": "1"}),
    )
    # Fase 3 §2: orden del drag & drop. El front lo renumera por posición del DOM
    # al arrastrar / al enviar; así el orden persiste también en Nuevo/Editar (en
    # el detalle además está el endpoint de reordenado). Oculto y opcional.
    orden = forms.IntegerField(required=False, widget=forms.HiddenInput())
    # LC 2026-07: alias del producto para ESTE proyecto («TShirt Modelo Janet»).
    # Se revela con el botón de la etiqueta en la tarjeta abierta; viaja con el
    # autosave del detalle como cualquier otro campo del formset.
    nombre_proyecto = forms.CharField(
        required=False, max_length=150, label="Nombre en este proyecto",
        widget=forms.TextInput(attrs={
            "placeholder": "Cómo se llama aquí",
            "data-alias-input": "1",
        }),
    )
    # LC 2026-07-28 (Oscar): quitar la foto de la tarjeta es un cambio PENDIENTE,
    # no inmediato («si salgo del proyecto sin guardar, igual se queda
    # eliminada»). El componente `imagen_pegar.js` en modo diferido escribe "1"
    # aquí y el borrado se aplica al guardar (ver `save`). Mismo patrón que la
    # ficha del producto en el catálogo.
    imagen_quitar = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = ProyectoProducto
        fields = ["servicio", "nombre_proyecto", "variacion", "proveedor", "cantidad", "precio_unitario", "costo_unitario", "merma", "incluir_en_calculo", "visible_pdf", "nota", "orden"]
        # LC 2026-08-04 (Oscar): la «nota corta» es ahora la DESCRIPCIÓN del
        # elemento y alimenta su especificación en la cotización. Acepta varias
        # líneas y crece sola hacia arriba (`data-autogrow` + la fila alinea al
        # fondo, así que al crecer sube su etiqueta).
        labels = {"nota": "Descripción"}
        widgets = {
            # LC 2026-08-04 R3 (Oscar): letra chica (del tamaño del chip
            # «@Proveedor» de abajo) y tope de ~4 renglones con scroll interno —
            # `data-autogrow` lleva el tope en px, así una especificación larga
            # ya no estira la tarjeta sin fin. `min-h-0` gana al `min-h-[80px]`
            # de `.campo-form textarea` (utilities pisa components).
            "nota": forms.Textarea(attrs={
                "rows": 2,
                "data-autogrow": "84",
                "class": "resize-none overflow-y-auto min-h-0 px-2.5 py-1.5 text-[11px] leading-snug",
                "placeholder": "Color: Beige / Terracota\nCon bordado frontal…",
                "title": "Especificación de este elemento. Es lo que sale en la "
                         "cotización debajo del nombre del concepto.",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # LC Buzón §4: combobox type-to-search en Producto y Proveedor.
        for _c in ("servicio", "proveedor"):
            if _c in self.fields:
                self.fields[_c].widget.attrs["data-select-buscable"] = "1"
        # LC 2026-07-26 (Oscar): el Producto además se encuentra escribiendo el
        # PROVEEDOR o cualquier ALIAS con el que se vendió en otro proyecto. El
        # widget lo marca en `data-buscar` (los alias salen de UNA consulta
        # cacheada, sin N+1).
        if "servicio" in self.fields:
            from apps.el_catalogo.widgets import SelectProductoBuscable
            campo_srv = self.fields["servicio"]
            campo_srv.widget = SelectProductoBuscable()
            # OJO (mismo tropiezo de S-Proveedores-Bidireccional): el setter de
            # `queryset` es lo que propaga las `choices` AL WIDGET ACTUAL. Al
            # cambiar el widget hay que re-asignar el queryset o el `<select>`
            # sale vacío.
            campo_srv.queryset = campo_srv.queryset
        # LC 2026-07: el dropdown de Producto muestra «Nombre - Proveedor».
        def _etiqueta_servicio(s):
            prov = s.proveedor_default  # LC 2026-08-04: el principal explícito
            return f"{s.nombre} - {prov.razon_social}" if prov else s.nombre
        self.fields["servicio"].label_from_instance = _etiqueta_servicio
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
                    .select_related("categoria").prefetch_related("proveedores")
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
            # Si se capturó como cuenta, se vuelve a mostrar la cuenta escrita.
            if inst.costo_unitario_expr:
                self.initial["costo_unitario"] = inst.costo_unitario_expr
            if getattr(inst, "precio_unitario_expr", ""):
                self.initial["precio_unitario"] = inst.precio_unitario_expr

    def clean_costo_unitario(self):
        """El campo acepta un número o una CUENTA («15.75*100»).

        El total lo saca el SERVIDOR (LC 2026-08-12), igual que el costo de la
        impresión: así el monto guardado siempre concuerda con lo escrito,
        venga el POST de donde venga. Vacío ⇒ None (hereda el del catálogo).
        """
        total, self._costo_expr = _cuenta_del_campo(
            self.cleaned_data.get("costo_unitario"), "Costo")
        return total

    def clean_precio_unitario(self):
        """Igual que el costo: número o cuenta, y el total lo saca el servidor."""
        total, self._precio_expr = _cuenta_del_campo(
            self.cleaned_data.get("precio_unitario"), "Precio")
        return total

    def clean_merma(self):
        # merma es NOT NULL con default 0; el form vacío llega como None.
        return self.cleaned_data.get("merma") or 0

    def clean_cantidad(self):
        # cantidad es NOT NULL con default 1; vacío/None ⇒ 1 (no invalida la fila).
        return self.cleaned_data.get("cantidad") or 1

    def clean_orden(self):
        # orden es NOT NULL con default 0; vacío/None ⇒ 0 (Fase 3 §2).
        return self.cleaned_data.get("orden") or 0

    # La foto por versión (S-Ajustes-Ago12-B) SÍ admite líneas sin producto: el
    # producto pudo borrarse del catálogo después de cotizarse.
    exigir_servicio = True

    def clean(self):
        cleaned = super().clean()
        # El modelo exige servicio (NOT NULL). Una tarjeta nueva inline que se
        # llenó parcialmente (cantidad/precio) pero sin producto truena al
        # guardar; un error claro es mejor que un 500. Las filas intactas/vacías
        # las ignora el formset (has_changed=False), y las marcadas DELETE no se
        # validan.
        if self.exigir_servicio and not cleaned.get("servicio") and not self.cleaned_data.get("DELETE") and self.has_changed():
            self.add_error("servicio", "Elige un producto del catálogo.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.costo_unitario_expr = getattr(self, "_costo_expr", "") or ""
        obj.precio_unitario_expr = getattr(self, "_precio_expr", "") or ""
        if commit:
            obj.save()
            self.save_m2m()
            if (self.cleaned_data.get("imagen_quitar") or "") == "1":
                _desligar_imagen(obj)
        return obj


def _desligar_imagen(linea) -> None:
    """Desliga la foto que se ve en la tarjeta (borrado diferido, LC 2026-07-28).

    Prefiere quitar la PROPIA del uso: así la línea vuelve a heredar la del
    catálogo (el caso normal de «me equivoqué de foto en este proyecto»). Si no
    tiene propia, la que se ve es la del catálogo y es ésa la que se quita — el
    front lo confirma antes de pedirlo. **El archivo NO se borra de Drive**: el
    mismo file_id puede estar congelado en una cotización ya enviada. Mismo
    criterio que `views._quitar_imagen_linea`.
    """
    if linea.imagen_es_propia:
        linea.imagen_file_id = ""
        linea.imagen_url = ""
        linea.save(update_fields=["imagen_file_id", "imagen_url"])
        return
    srv = linea.servicio
    if srv is not None and (srv.imagen_file_id or "").strip():
        srv.imagen_file_id = ""
        srv.imagen_url = ""
        srv.save(update_fields=["imagen_file_id", "imagen_url", "actualizado_en"])


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


class ProyectoProductoVersionForm(ProyectoProductoForm):
    """La MISMA tarjeta, sobre la foto de una versión de cotización.

    S-Ajustes-Ago12-B. Hereda todos los campos declarados para que
    `_producto_card.html` funcione sin ramificarse; sólo cambian tres cosas:

    1. El producto NO es obligatorio (pudo borrarse del catálogo después).
    2. `procesos_json` / `ventas_json` son campos del MODELO (JSONField), pero el
       front los maneja como texto. Se quedan FUERA de `Meta.fields` —si
       entraran, `construct_instance` metería la cadena cruda en el JSONField— y
       se normalizan en `save()` con las mismas reglas que la línea viva.
    3. Los placeholders no dicen «catálogo»: en una foto, vacío es *desconocido*,
       no *heredado*.
    """

    exigir_servicio = False

    class Meta(ProyectoProductoForm.Meta):
        model = ProyectoProductoVersion

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import json as _json

        inst = getattr(self, "instance", None)
        if inst is not None:
            self.initial["procesos_json"] = _json.dumps(inst.procesos_json or [])
            self.initial["ventas_json"] = _json.dumps(inst.ventas_json or [])
            self.initial["escalas_json"] = _json.dumps(inst.escalas_json or [])
            # El padre rellena precio/costo con el «efectivo» cuando están vacíos
            # (para que la línea viva muestre el del catálogo). Aquí un vacío es
            # desconocido: mejor dejarlo vacío que escribir un 0.00 inventado.
            if inst.precio_unitario is None:
                self.initial.pop("precio_unitario", None)
            if inst.costo_unitario is None:
                self.initial.pop("costo_unitario", None)
        for campo in ("precio_unitario", "costo_unitario"):
            if campo in self.fields:
                self.fields[campo].widget.attrs["placeholder"] = "—"

    def save(self, commit=True):
        from .services_procesos import (
            escalas_normalizadas,
            procesos_normalizados,
            ventas_normalizadas,
        )

        # Salta el `save` del padre (su borrado diferido de imagen es de la línea
        # viva) y se queda con el de ModelForm.
        obj = super(ProyectoProductoForm, self).save(commit=False)
        obj.costo_unitario_expr = getattr(self, "_costo_expr", "") or ""
        obj.precio_unitario_expr = getattr(self, "_precio_expr", "") or ""
        procesos = procesos_normalizados(self.cleaned_data.get("procesos_json"))
        if procesos is not None:
            # Los montos se guardan como texto: el JSON no serializa `Decimal` y
            # un `float` perdería centavos.
            obj.procesos_json = [{**p, "costo": str(p["costo"])} for p in procesos]
        ventas = ventas_normalizadas(self.cleaned_data.get("ventas_json"))
        if ventas is not None:
            obj.ventas_json = [{
                "descripcion": v["descripcion"], "cantidad": v["cantidad"],
                "precio": str(v["precio_unitario"]),
                # La cuenta escrita también se congela (LC 2026-08-18): sin ella,
                # editar la pestaña de una versión la perdería y dejaría el total.
                "precio_expr": v["precio_expr"],
            } for v in ventas]
        # LC 2026-08-17: las escalas de volumen de esta versión. Los montos van
        # como texto (el JSON no serializa `Decimal`) y **el None se conserva**:
        # en una escala significa «hereda de la Opción A».
        escalas = escalas_normalizadas(self.cleaned_data.get("escalas_json"))
        if escalas is not None:
            def _txt(valor):
                return None if valor is None else str(valor)
            obj.escalas_json = [{
                **e,
                "precio_unitario": _txt(e["precio_unitario"]),
                "costo_unitario": _txt(e["costo_unitario"]),
                "impresion_costo": _txt(e["impresion_costo"]),
                "extras": e["extras_json"],
            } for e in escalas]
            for fila in obj.escalas_json:
                fila.pop("extras_json", None)
        if commit:
            obj.save()
        return obj


ProyectoProductoVersionFormSet = inlineformset_factory(
    Cotizacion, ProyectoProductoVersion, form=ProyectoProductoVersionForm,
    fk_name="cotizacion", extra=0, can_delete=True,
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
