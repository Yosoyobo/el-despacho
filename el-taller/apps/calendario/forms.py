"""Form del Evento genérico del calendario (S-LC-Feedback-V13)."""

from __future__ import annotations

from apps.el_pizarron.models import Evento
from django import forms

# LC 2026-07: paleta cerrada de 7 colores para eventos/tareas (reemplaza el
# selector RGB libre). HEX de la paleta TailAdmin del repo.
COLORES_EVENTO = (
    ("#465FFF", "Azul"),
    ("#12B76A", "Verde"),
    ("#F79009", "Ámbar"),
    ("#F04438", "Rojo"),
    ("#0BA5EC", "Cielo"),
    ("#EE46BC", "Rosa"),
    ("#667085", "Gris"),
)


class EventoForm(forms.ModelForm):
    color = forms.ChoiceField(
        choices=COLORES_EVENTO, initial="#465FFF", label="Color",
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )

    class Meta:
        model = Evento
        fields = ["titulo", "descripcion", "fecha_inicio", "fecha_fin", "color"]
        widgets = {
            "titulo": forms.TextInput(attrs={
                "data-referencias": "1",
                "placeholder": "Ej. Día feriado, Vacaciones de Ana, Inventario…",
            }),
            "descripcion": forms.Textarea(attrs={"rows": 2, "data-referencias": "1"}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date", "data-sin-quitar": "1"}, format="%Y-%m-%d"),
        }
        labels = {
            "titulo": "Título",
            "descripcion": "Descripción (opcional)",
            "fecha_inicio": "Desde",
            "fecha_fin": "Hasta",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("fecha_inicio", "fecha_fin"):
            self.fields[campo].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        # `fecha_fin` opcional: vacío ⇒ mismo día (lo resuelve Evento.save).
        self.fields["fecha_fin"].required = False
        # Si el evento traía un HEX fuera de la paleta (legacy), lo agregamos
        # como opción para no perder el valor al editar.
        actual = (self.initial.get("color") or getattr(self.instance, "color", "")) or ""
        if actual and actual not in dict(COLORES_EVENTO):
            self.fields["color"].choices = [*COLORES_EVENTO, (actual, "Actual")]

    def clean(self):
        cleaned = super().clean()
        ini = cleaned.get("fecha_inicio")
        fin = cleaned.get("fecha_fin")
        if ini and fin and fin < ini:
            self.add_error("fecha_fin", "La fecha final no puede ser anterior a la inicial.")
        return cleaned
