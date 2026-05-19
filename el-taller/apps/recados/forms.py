from __future__ import annotations

from django import forms

from .models import Recado


class RecadoForm(forms.ModelForm):
    """Form sin campo de destinatarios — eso se envía como listas paralelas
    en `request.POST.getlist(...)` y se resuelve en la vista (services.crear_recado)."""

    cuerpo = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 6,
            "data-referencias": "1",
            "placeholder": "Escribe tu recado… usa @persona, #proyecto, $cliente",
            "class": "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm "
                     "shadow-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 "
                     "dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100",
        }),
        max_length=8000,
        strip=True,
    )

    class Meta:
        model = Recado
        fields = ["cuerpo"]

    def clean_cuerpo(self):
        cuerpo = (self.cleaned_data.get("cuerpo") or "").strip()
        if not cuerpo:
            raise forms.ValidationError("El recado no puede estar vacío.")
        return cuerpo
