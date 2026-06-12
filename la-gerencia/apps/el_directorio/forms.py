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
        ]
        widgets = {
            "horario_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "horario_fin": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "dias_trabajo": forms.TextInput(attrs={"placeholder": "Ej. Lunes a viernes"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La ficha es opcional: `modalidad` tiene default y los demás son blank.
        # Sin esto, agregar `modalidad` (ChoiceField) rompería el alta/edición
        # de usuario que no la envíe.
        self.fields["modalidad"].required = False
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
