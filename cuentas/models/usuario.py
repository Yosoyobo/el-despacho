from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from cuentas.managers import UsuarioManager

ROLES = (
    ("super_admin", "Super Admin"),
    ("dueno", "Dueño"),
    ("contador", "Contador"),
    ("disenador", "Diseñador"),
)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Usuario único de El Despacho. Compartido entre La Gerencia, El Taller y La Recepción."""

    email = models.EmailField(unique=True, db_index=True)
    nombre_completo = models.CharField(max_length=200)
    rol = models.CharField(max_length=20, choices=ROLES, default="disenador", db_index=True)
    # Slug para el Sistema de Referencias (@). Auto-generado en save() si vacío.
    # Unicidad la garantiza la DB; ver lib.slug.generar_slug_usuario.
    slug = models.CharField(max_length=80, unique=True)

    # Vínculo Google SSO opcional. `google_sub` es el ID inmutable que Google
    # emite por usuario; sobrevive cambios de email del lado Google.
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    google_email = models.EmailField(null=True, blank=True)
    google_vinculado_en = models.DateTimeField(null=True, blank=True)
    # URLs no se benefician de un max_length arbitrario; TextField evita crashes
    # con URLs largas de Google Workspace que incluyen tokens/hashes (0004).
    avatar_url = models.TextField(blank=True, default="")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    ultimo_acceso_en = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre_completo"]

    objects = UsuarioManager()

    class Meta:
        db_table = "cuentas_usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["nombre_completo"]

    def save(self, *args, **kwargs):
        if not self.slug:
            from lib.slug import generar_slug_usuario
            self.slug = generar_slug_usuario(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre_completo} <{self.email}>"

    def get_full_name(self):
        return self.nombre_completo

    def get_short_name(self):
        return self.nombre_completo.split()[0] if self.nombre_completo else self.email

    @property
    def es_admin(self):
        return self.rol in ("super_admin", "dueno")

    @property
    def es_super_admin(self):
        return self.rol == "super_admin"
