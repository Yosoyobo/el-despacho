from apps.el_pizarron.models import Comentario, Tarea
from django import forms

from cuentas.models.usuario import Usuario


def _choices_estado_tarea():
    """Choices dinámicos desde EstadoTarea activos (configurable en Gerencia).
    Fallback a los sembrados si la DB no está migrada (tests aislados)."""
    from apps.el_pizarron.models.estado_tarea import EstadoTarea
    try:
        pares = [(e.slug, e.label) for e in EstadoTarea.objects.filter(activo=True)]
        if pares:
            return pares
    except Exception:
        pass
    from apps.el_pizarron.models.tarea import ESTADOS_TAREA
    return list(ESTADOS_TAREA)


class TareaForm(forms.ModelForm):
    asignada_a = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(is_active=True).order_by("nombre_completo"),
        required=True,
        empty_label="— Elige una persona —",
        label="Asignada a",
        error_messages={"required": "Asigna la tarea a alguien."},
    )
    # `<input type="date">` SOLO acepta ISO (YYYY-MM-DD) para mostrar y enviar.
    # Sin `format="%Y-%m-%d"` el widget rendea "18/06/2026" (locale es-mx), el
    # navegador lo rechaza y el campo queda en blanco al reabrir la edición —
    # por eso "hay que volver a escribir la fecha cada vez" (Bug Oscar 2026-06-17).
    fecha_compromiso = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        label="Fecha de compromiso",
        error_messages={"required": "Pon una fecha de compromiso."},
    )
    hora = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        input_formats=["%H:%M", "%H:%M:%S"],
        label="Hora (opcional)",
    )
    tipo = forms.ChoiceField(
        choices=Tarea._meta.get_field("tipo").choices,
        required=False,
        initial="tarea",
        label="Tipo",
    )
    # S-LC-Proyecto-V2: runner para entregas/recolecciones. `runner` vacío +
    # `runner_auto` ⇒ el sistema asigna el menos cargado. Solo aplica si el
    # tipo es entrega/recoger (se ignora en tareas normales).
    runner = forms.ModelChoiceField(
        queryset=Usuario.objects.none(), required=False,
        empty_label="— El sistema asigna (más cercano / menos cargado) —",
        label="Runner (entrega/recoger)",
    )
    runner_auto = forms.BooleanField(
        required=False, initial=True,
        label="Que el sistema/El Chalán asigne al runner más libre",
    )

    def clean_tipo(self):
        return self.cleaned_data.get("tipo") or "tarea"

    class Meta:
        model = Tarea
        fields = ["titulo", "descripcion", "estado", "prioridad", "tipo", "asignada_a", "fecha_compromiso", "hora"]
        widgets = {
            # S-LC-Feedback-V4: autocomplete @#$ en título y descripción.
            "titulo": forms.TextInput(attrs={"data-referencias": "1"}),
            "descripcion": forms.Textarea(attrs={"data-referencias": "1", "rows": 4}),
        }
        labels = {"tipo": "Tipo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El dropdown de runner lista a CUALQUIER usuario activo: la asignación
        # manual debe poder caer en quien sea, aunque no tenga el permiso de
        # runner (decisión Oscar 2026-06-17). La elegibilidad por permiso
        # `(runner, recibir)` solo gobierna la AUTO-asignación (cuando no se
        # especifica nadie) — ver runners.aplicar_desde_form / elegir_runner_auto.
        self.fields["runner"].queryset = (
            Usuario.objects.filter(is_active=True).order_by("nombre_completo")
        )
        # Al editar, refleja el estado actual del runner para que un guardado
        # sin tocar el bloque NO reasigne ni re-notifique (los campos no están
        # en Meta.fields, así que el ModelForm no los inicializa solo).
        if self.instance and self.instance.pk:
            self.fields["runner"].initial = self.instance.runner_id
            self.fields["runner_auto"].initial = self.instance.runner_auto
        # Estado dinámico (el campo del modelo ya no tiene choices). Si la
        # tarea está en un slug inactivo/huérfano, se conserva como opción
        # para no romper la edición. El form global (sin "estado" en fields)
        # deja el default del modelo.
        if "estado" in self.fields:
            choices = _choices_estado_tarea()
            actual = getattr(self.instance, "estado", None)
            if actual and actual not in {c[0] for c in choices}:
                from apps.el_pizarron.templatetags.tareas_extras import estado_label_tarea
                choices = [*choices, (actual, f"{estado_label_tarea(actual)} (inactivo)")]
            self.fields["estado"] = forms.ChoiceField(choices=choices, label="Estado")


class TareaGlobalForm(TareaForm):
    """Form "Nueva Tarea" sin proyecto fijo (V6 Bloque 2B): el usuario elige
    proyecto / persona / tipo con un click (chips), fecha en el calendario y
    hora opcional. El estado arranca en el default del modelo (pendiente)."""

    class Meta(TareaForm.Meta):
        fields = ["proyecto", "titulo", "descripcion", "prioridad", "tipo",
                  "asignada_a", "fecha_compromiso", "hora"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proyecto"].error_messages = {"required": "Elige un proyecto."}
        self.fields["prioridad"].required = False

    def clean_prioridad(self):
        return self.cleaned_data.get("prioridad") or "media"


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ["cuerpo", "es_interno"]
        widgets = {
            "cuerpo": forms.Textarea(attrs={"data-referencias": "1", "rows": 3}),
        }
