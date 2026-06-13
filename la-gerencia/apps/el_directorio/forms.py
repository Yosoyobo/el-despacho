from django import forms

from cuentas.models.usuario import ROLES, Usuario


class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        min_length=10,
        help_text="Vacío = no cambia. Para alta nueva, obligatorio.",
    )
    rol = forms.ChoiceField(choices=ROLES)

    class Meta:
        model = Usuario
        # S-Directorio-V1: la ficha (puesto/teléfono/oficina/modalidad/horario)
        # se edita aquí en La Gerencia; el Taller solo la muestra read-only.
        fields = [
            "email", "nombre_completo", "rol", "is_active",
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
        # V6 Bloque 10 (decisión Oscar): solo super_admin y miembro son
        # asignables — todo lo demás se modela con roles personalizados (tabla
        # Rol) + permisos granulares. Si el usuario editado conserva un rol
        # legacy, se ofrece para no forzar el cambio en una edición ajena.
        asignables = [("super_admin", "Super Admin"), ("miembro", "Miembro")]
        actual = getattr(self.instance, "rol", None)
        if self.instance.pk and actual and actual not in {r[0] for r in asignables}:
            asignables.append((actual, dict(ROLES).get(actual, actual)))
        self.fields["rol"].choices = asignables

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
        # El rol super_admin gobierna los flags de Django. Hay que SET y CLEAR:
        # si no se limpian al degradar, el usuario conserva poderes de
        # superusuario aunque su rol ya no sea super_admin (bug del checkmark).
        es_super = u.rol == "super_admin"
        u.is_staff = es_super
        u.is_superuser = es_super
        if commit:
            u.save()
        return u
