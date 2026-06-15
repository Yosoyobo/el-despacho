from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from cuentas.managers import UsuarioManager

# V6 Bloque 10 (decisión Oscar): super_admin es el ÚNICO rol duro; todo lo
# demás se modela con roles personalizados (tabla Rol vía roles_extra) +
# permisos granulares. "miembro" es el rol primario neutro (sin defaults).
# "dueno/contador/disenador" quedan como valores LEGACY no asignables desde
# la UI — usuarios existentes y tests los conservan; los checks pasan por
# lib.permisos.roles_efectivos/tiene_rol, que reconocen ambas vías.
ROLES = (
    ("super_admin", "Super Admin"),
    ("miembro", "Miembro"),
    ("dueno", "Admin (legacy)"),
    ("contador", "Contador (legacy)"),
    ("disenador", "Diseñador (legacy)"),
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
    # S-LC-Feedback-V8: avatar subido por el usuario. Se guarda en Drive
    # (privado) y se sirve por un proxy autenticado; `avatar_url` apunta a ese
    # proxy. `avatar_drive_id` guarda el file_id para reemplazar/borrar.
    avatar_drive_id = models.CharField(max_length=128, blank=True, default="")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # S-Directorio-V1: ficha del empleado. Editable solo en La Gerencia; el
    # Taller la muestra read-only. Los checkins/ponchado viven en El Checador
    # (sprint aparte) — aquí solo el horario/oficina/modalidad declarados.
    MODALIDADES = (
        ("presencial", "Presencial"),
        ("remoto", "Home office"),
        ("hibrido", "Híbrido"),
    )
    puesto = models.CharField(max_length=120, blank=True, default="",
                              help_text="Cargo o puesto, ej. Auditor.")
    telefono = models.CharField(max_length=40, blank=True, default="")
    oficina = models.CharField(max_length=120, blank=True, default="",
                               help_text="Sede o ubicación de trabajo.")
    modalidad = models.CharField(max_length=12, choices=MODALIDADES, default="presencial")
    horario_inicio = models.TimeField(null=True, blank=True)
    horario_fin = models.TimeField(null=True, blank=True)
    dias_trabajo = models.CharField(max_length=80, blank=True, default="",
                                    help_text="Ej. Lunes a viernes.")

    # S-LC-Feedback-V7: jefe directo. Es quien aprueba los ajustes de horas de
    # este empleado en El Checador (el super_admin siempre puede como failsafe).
    # SET_NULL para no perder al empleado si se borra al jefe; no se permite
    # auto-referencia (se valida en el form).
    jefe_directo = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="subordinados",
        help_text="Aprueba los ajustes de horas de este empleado.")

    # S-LC-Feedback-V7: dirección + pin geográfico del empleado. Base para la
    # GEOCERCA del Checador (comparar la checada contra este punto + radio).
    # `geocerca_activa` enciende la fase; sin lat/lng no aplica.
    direccion = models.TextField(blank=True, default="",
                                 help_text="Dirección del empleado (texto libre).")
    geo_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geo_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geocerca_radio_m = models.PositiveIntegerField(
        default=150, help_text="Radio de la geocerca en metros.")
    geocerca_activa = models.BooleanField(
        default=False, help_text="Activa la validación de geocerca para este empleado.")

    # S-Chalan-Voz-Usuario: voz/estilo personal del usuario para Los Chalanes.
    # Capa ADITIVA — se concatena DESPUÉS de la voz institucional (PromptVoz),
    # solo afecta tono en flujos conversacionales (Dictado, chat). Nunca toca
    # permisos ni acciones permitidas (eso lo gobierna el rol en código). Vacío
    # = sin personalización. Se sanea al inyectarse (chalanes.voz).
    voz_chalan = models.TextField(blank=True, default="")

    # S-LC-Feedback-V11: formato de hora preferido por el usuario, aplicado a
    # TODAS las horas de la plataforma (filtro `hfmt`). Default 24h.
    FORMATO_HORA = (("24h", "24 horas (14:30)"), ("ampm", "AM/PM (2:30 p.m.)"))
    formato_hora = models.CharField(max_length=4, choices=FORMATO_HORA, default="24h")

    # S-LC-Feedback-V5 c7: roles personalizados adicionales (encima del
    # rol primario CharField). El user los puede tener N roles extra que
    # contribuyen permisos a la unión efectiva.
    roles_extra = models.ManyToManyField(
        "cuentas.Rol", blank=True, related_name="usuarios",
    )

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

    @property
    def tiene_pin(self) -> bool:
        """¿El empleado tiene un pin geográfico capturado?"""
        return self.geo_lat is not None and self.geo_lng is not None

    def distancia_a_m(self, lat, lng):
        """Distancia en metros del pin del empleado a (lat, lng). None si no hay
        pin o coords. Haversine — suficiente para una geocerca de oficina."""
        if not self.tiene_pin or lat is None or lng is None:
            return None
        from math import asin, cos, radians, sin, sqrt
        r = 6371000.0  # radio terrestre en metros
        la1, lo1, la2, lo2 = map(radians, (float(self.geo_lat), float(self.geo_lng), float(lat), float(lng)))
        h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
        return 2 * r * asin(sqrt(h))

    def dentro_de_geocerca(self, lat, lng):
        """True/False si (lat,lng) cae dentro del radio de la geocerca, o None si
        no hay pin/coords para evaluar."""
        d = self.distancia_a_m(lat, lng)
        if d is None:
            return None
        return d <= (self.geocerca_radio_m or 150)
