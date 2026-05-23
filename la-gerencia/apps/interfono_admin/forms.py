from __future__ import annotations

from django import forms

from cuentas.models.usuario import Usuario
from lib.permisos import ROLES

AUDIENCIA_OPCIONES = [
    ("todos", "Todos los usuarios activos"),
    ("rol", "Por rol"),
    ("usuario", "Usuario individual"),
]


class EnvioInterfonoForm(forms.Form):
    audiencia_tipo = forms.ChoiceField(choices=AUDIENCIA_OPCIONES, initial="todos")
    audiencia_rol = forms.ChoiceField(choices=[(r, r) for r in ROLES], required=False)
    audiencia_usuario = forms.IntegerField(required=False)
    titulo = forms.CharField(max_length=80)
    cuerpo = forms.CharField(max_length=300, widget=forms.Textarea(attrs={"data-referencias": "1", "rows": 3}))
    url_destino = forms.URLField(required=False)

    def audiencia_resuelta(self) -> tuple[str, str]:
        """Devuelve (audiencia, label) listos para enviar_a_audiencia/InterfonoEnvio."""
        tipo = self.cleaned_data["audiencia_tipo"]
        if tipo == "todos":
            return "todos", "Todos los usuarios activos"
        if tipo == "rol":
            rol = self.cleaned_data.get("audiencia_rol") or ""
            return f"rol:{rol}", f"Rol: {rol}"
        if tipo == "usuario":
            uid = self.cleaned_data.get("audiencia_usuario")
            try:
                u = Usuario.objects.get(pk=uid)
                etiqueta = u.nombre_completo or u.email
            except Usuario.DoesNotExist:
                etiqueta = f"usuario#{uid}"
            return f"usuario:{uid}", etiqueta
        return "todos", "Todos los usuarios activos"

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("audiencia_tipo")
        if tipo == "rol" and not cleaned.get("audiencia_rol"):
            raise forms.ValidationError("Selecciona un rol.")
        if tipo == "usuario" and not cleaned.get("audiencia_usuario"):
            raise forms.ValidationError("Selecciona un usuario.")
        return cleaned
