"""Form del Evento genérico del calendario (S-LC-Feedback-V13)."""

from __future__ import annotations

from apps.el_pizarron.models import Evento
from django import forms


class EventoForm(forms.ModelForm):
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
            "color": forms.TextInput(attrs={"type": "color", "class": "h-10 w-16 cursor-pointer p-1"}),
        }
        labels = {
            "titulo": "Título",
            "descripcion": "Descripción (opcional)",
            "fecha_inicio": "Desde",
            "fecha_fin": "Hasta",
            "color": "Color",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("fecha_inicio", "fecha_fin"):
            self.fields[campo].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        # `fecha_fin` opcional: vacío ⇒ mismo día (lo resuelve Evento.save).
        self.fields["fecha_fin"].required = False

    def clean(self):
        cleaned = super().clean()
        ini = cleaned.get("fecha_inicio")
        fin = cleaned.get("fecha_fin")
        if ini and fin and fin < ini:
            self.add_error("fecha_fin", "La fecha final no puede ser anterior a la inicial.")
        return cleaned
