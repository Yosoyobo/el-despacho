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
    # Un alias PERSONAL pertenece a alguien: sólo esa persona puede mandar
    # desde él. Vacío = departamental, lo puede usar todo el equipo.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="alias_propios",
        help_text="Si lo llenas, el alias es de esa persona y nadie más puede enviar desde él.",
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

    @property
    def es_personal(self) -> bool:
        """Un alias a nombre de una persona (alex@, jorge@), no del despacho."""
        return self.usuario_id is not None

    def puede_usarlo(self, usuario) -> bool:
        """Regla de Oscar: el alias personal sale a nombre de su dueño y de nadie más.

        Un departamental lo usa cualquiera que tenga permiso de mandar correo;
        un personal, sólo su dueño. Sin usuario (un cron, una regla automática)
        NUNCA se usa un personal: un correo que sale solo no puede ir firmado
        por alguien que ni se enteró.
        """
        if not self.es_personal:
            return True
        return usuario is not None and getattr(usuario, "pk", None) == self.usuario_id

    def como_remitente(self) -> str:
        """`Nombre <correo>` listo para El Cartero."""
        nombre = (self.nombre or "").strip()
        return f"{nombre} <{self.email}>" if nombre else self.email

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
            "usuario": alias.usuario if alias else None,
            "es_personal": bool(alias and alias.es_personal),
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


def disponibles_para(usuario) -> list[AliasRemitente]:
    """Direcciones desde las que ESTE usuario puede mandar.

    Los departamentales del despacho más su propio alias personal, si tiene.
    Sólo las verificadas: ofrecer una que Google va a reescribir sería prometer
    algo que no se cumple.
    """
    from django.db.models import Q

    if usuario is None:
        return list(AliasRemitente.objects.filter(verificado=True, usuario__isnull=True))
    return list(
        AliasRemitente.objects.filter(verificado=True)
        .filter(Q(usuario__isnull=True) | Q(usuario=usuario))
        .select_related("usuario")
    )


def remitente_para(plantilla, usuario=None, forzado: str = "") -> str:
    """Con qué remitente sale este correo. Fuente ÚNICA de la decisión.

    Orden: lo que se eligió a mano (si esa persona puede usarlo) → el alias de
    la plantilla (si puede usarlo) → el remitente general.

    La regla que hace todo esto seguro: **un alias personal ajeno se ignora en
    silencio y el correo sale del remitente general**, en vez de fallar. Así una
    plantilla que Jorge dejó con su alias la puede seguir mandando cualquiera,
    sólo que no a nombre de Jorge.
    """
    escogido = (forzado or "").strip().lower()
    if escogido:
        alias = AliasRemitente.objects.filter(email=escogido).select_related("usuario").first()
        if alias and alias.puede_usarlo(usuario):
            return alias.como_remitente()
        # Un alias que no le toca (o que no existe) no se respeta ni a medias.
        return ""

    declarado = (getattr(plantilla, "remitente_email", "") or "").strip().lower()
    if not declarado:
        return ""
    alias = AliasRemitente.objects.filter(email=declarado).select_related("usuario").first()
    if alias is not None and not alias.puede_usarlo(usuario):
        return ""  # personal de otra persona → sale del remitente general
    return plantilla.remitente_efectivo()
