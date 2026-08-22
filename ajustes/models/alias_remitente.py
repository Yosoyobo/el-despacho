"""AliasRemitente — el registro de las direcciones desde las que mandamos.

Existe porque **la app no puede comprobar sola si un alias quedó**: Gmail no
rechaza un remitente ajeno, lo reescribe en silencio (ver `lib.cartero`). Así
que hace falta un lugar donde quede escrito qué direcciones hacen falta dar de
alta a mano en Google y cuáles ya se comprobaron.

La lista de direcciones NECESARIAS no se captura: se **deriva** de lo que
declaran las plantillas (`PlantillaCorreo.remitente_email`). Esta tabla sólo
guarda lo que no se puede deducir — si alguien ya lo dio de alta y lo comprobó.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AliasRemitente(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    nombre = models.CharField(
        max_length=120, blank=True, default="",
        help_text="Nombre visible sugerido, ej. «Cobranza Learning Center».",
    )
    verificado = models.BooleanField(
        default=False,
        help_text="Marcado a mano tras mandar una prueba y comprobar de quién llegó.",
    )
    verificado_en = models.DateTimeField(null=True, blank=True)
    verificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="alias_verificados",
    )
    notas = models.CharField(max_length=200, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ajustes_alias_remitente"
        ordering = ["email"]
        verbose_name = "alias de remitente"
        verbose_name_plural = "alias de remitente"

    def __str__(self) -> str:
        return self.email

    def marcar_verificado(self, usuario) -> None:
        from django.utils import timezone
        self.verificado = True
        self.verificado_en = timezone.now()
        self.verificado_por = usuario
        self.save(update_fields=["verificado", "verificado_en", "verificado_por"])

    def desmarcar(self) -> None:
        self.verificado = False
        self.verificado_en = None
        self.verificado_por = None
        self.save(update_fields=["verificado", "verificado_en", "verificado_por"])


def remitentes_en_uso() -> list[dict]:
    """Qué direcciones hacen falta dar de alta en Google, y cómo van.

    Junta lo que declaran las plantillas con lo que ya se registró aquí. El
    orden pone arriba lo que falta hacer: primero lo que se usa y no está
    verificado, que es justo la lista que alguien tiene que ir a crear.
    """
    from ajustes.models.plantilla_correo import PlantillaCorreo

    usos: dict[str, list[str]] = {}
    for pl in PlantillaCorreo.objects.exclude(remitente_email="").order_by("nombre"):
        usos.setdefault(pl.remitente_email.strip().lower(), []).append(pl.nombre)

    registrados = {a.email.strip().lower(): a for a in AliasRemitente.objects.all()}

    filas = []
    for email in sorted(set(usos) | set(registrados)):
        alias = registrados.get(email)
        plantillas = usos.get(email, [])
        filas.append({
            "email": email,
            "nombre": (alias.nombre if alias else "") or "",
            "plantillas": plantillas,
            "en_uso": bool(plantillas),
            "verificado": bool(alias and alias.verificado),
            "verificado_en": alias.verificado_en if alias else None,
            "notas": alias.notas if alias else "",
            "registrado": alias is not None,
        })
    # Lo que falta, arriba: en uso y sin verificar.
    filas.sort(key=lambda f: (f["verificado"], not f["en_uso"], f["email"]))
    return filas


def faltan_por_dar_de_alta() -> list[str]:
    """Direcciones que una plantilla ya usa pero que nadie ha comprobado."""
    return [f["email"] for f in remitentes_en_uso() if f["en_uso"] and not f["verificado"]]
