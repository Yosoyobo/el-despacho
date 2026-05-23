from __future__ import annotations

from django import forms

from chalanes.models import Aprendizaje


class AprendizajeForm(forms.ModelForm):
    class Meta:
        model = Aprendizaje
        fields = ["frase_o_patron", "interpretacion_correcta", "peso", "activo"]
        widgets = {
            "frase_o_patron": forms.TextInput(attrs={
                "class": "w-full rounded-lg border-gray-300 text-sm dark:border-gray-700 dark:bg-gray-900",
                "placeholder": "la heladería",
                "maxlength": 300,
            }),
            "interpretacion_correcta": forms.Textarea(attrs={"data-referencias": "1", 
                "class": "w-full rounded-lg border-gray-300 text-sm dark:border-gray-700 dark:bg-gray-900",
                "rows": 3,
                "placeholder": "$heladeria-michoacana (el cliente activo más grande)",
            }),
            "peso": forms.NumberInput(attrs={
                "class": "w-32 rounded-lg border-gray-300 text-sm dark:border-gray-700 dark:bg-gray-900",
                "step": "0.1", "min": "0.1", "max": "5",
            }),
        }
        labels = {
            "frase_o_patron": "Frase o patrón",
            "interpretacion_correcta": "Interpretación correcta",
            "peso": "Peso (1.0 = normal)",
            "activo": "Activo",
        }
