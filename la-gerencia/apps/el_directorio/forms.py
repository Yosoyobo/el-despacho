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
        fields = ["email", "nombre_completo", "rol", "is_active"]

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def save(self, commit=True):
        u = super().save(commit=False)
        pwd = self.cleaned_data.get("password")
        if pwd:
            u.set_password(pwd)
        elif not u.pk:
            # alta nueva sin password: marca cuenta inutilizable hasta SSO o reset
            u.set_unusable_password()
        if u.rol == "super_admin":
            u.is_staff = True
            u.is_superuser = True
        if commit:
            u.save()
        return u
