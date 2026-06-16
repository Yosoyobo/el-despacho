from django import forms

from cuentas.models.usuario import Usuario


class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        min_length=10,
        help_text="Vacío = no cambia. Para alta nueva, obligatorio.",
    )
    # S-Roles-V2 (Oscar): el dropdown de "rol primario" se eliminó. Los roles se
    # asignan en UN solo lugar — los checkboxes de Roles (pestaña Permisos). El
    # rol primario (`Usuario.rol`) se DERIVA de esos roles en
    # `lib.permisos.sincronizar_rol_primario` (super_admin si tiene ese rol, si no
    # miembro). Aquí solo se editan datos de la ficha.

    class Meta:
        model = Usuario
        # S-Directorio-V1: la ficha (puesto/teléfono/oficina/modalidad/horario)
        # se edita aquí en La Gerencia; el Taller solo la muestra read-only.
        fields = [
            "email", "nombre_completo", "is_active",
            "puesto", "telefono", "oficina", "modalidad",
            "horario_inicio", "horario_fin", "dias_trabajo",
            # S-LC-Feedback-V7: jefe directo + dirección/pin/geocerca.
            "jefe_directo", "direccion",
            "geo_lat", "geo_lng", "geocerca_radio_m", "geocerca_activa",
        ]
        widgets = {
            "horario_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "horario_fin": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "dias_trabajo": forms.TextInput(attrs={"placeholder": "Ej. Lunes a viernes"}),
            "direccion": forms.Textarea(attrs={"rows": 2, "placeholder": "Calle, número, colonia…"}),
            "geo_lat": forms.NumberInput(attrs={"step": "any", "placeholder": "19.4326"}),
            "geo_lng": forms.NumberInput(attrs={"step": "any", "placeholder": "-99.1332"}),
            "geocerca_radio_m": forms.NumberInput(attrs={"min": 20, "max": 5000}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La ficha es opcional: `modalidad` tiene default y los demás son blank.
        # Sin esto, agregar `modalidad` (ChoiceField) rompería el alta/edición
        # de usuario que no la envíe.
        self.fields["modalidad"].required = False
        # S-LC-Feedback-V7: jefe directo opcional, solo usuarios activos, y
        # nunca uno mismo (se excluye del queryset cuando hay instancia).
        qs = Usuario.objects.filter(is_active=True).order_by("nombre_completo")
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["jefe_directo"].queryset = qs
        self.fields["jefe_directo"].required = False
        self.fields["jefe_directo"].empty_label = "— Sin jefe directo —"
        for f in ("direccion", "geo_lat", "geo_lng", "geocerca_radio_m", "geocerca_activa"):
            self.fields[f].required = False

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_modalidad(self):
        return self.cleaned_data.get("modalidad") or "presencial"

    def clean(self):
        cleaned = super().clean()
        jefe = cleaned.get("jefe_directo")
        if jefe and self.instance.pk and jefe.pk == self.instance.pk:
            self.add_error("jefe_directo", "Una persona no puede ser su propio jefe.")
        if cleaned.get("geocerca_activa") and (cleaned.get("geo_lat") is None or cleaned.get("geo_lng") is None):
            self.add_error("geocerca_activa", "Para activar la geocerca, captura primero el pin (lat/lng).")
        return cleaned

    def save(self, commit=True):
        u = super().save(commit=False)
        pwd = self.cleaned_data.get("password")
        if pwd:
            u.set_password(pwd)
        elif not u.pk:
            # alta nueva sin password: marca cuenta inutilizable hasta SSO o reset
            u.set_unusable_password()
        # S-Roles-V2: alta nueva arranca como "miembro" (neutro, sin permisos);
        # los roles se asignan después en la pestaña Permisos, y eso DERIVA el rol
        # vía sincronizar_rol_primario. En edición no se toca `rol` aquí (lo
        # gobiernan los roles). is_staff/is_superuser siguen el rol vigente.
        if not u.pk:
            u.rol = "miembro"
        es_super = u.rol == "super_admin"
        u.is_staff = es_super
        u.is_superuser = es_super
        if commit:
            u.save()
        return u
