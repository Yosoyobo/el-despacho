"""El puente entre un documento de Paperless y a quién le pertenece.

Paperless sabe qué dice un documento; El Despacho sabe de quién es. Esta tabla
guarda la liga: este contrato es de este cliente, esta remisión es de este
proyecto, este comprobante es de este proveedor.

**Por qué la liga vive aquí y no en las etiquetas de Paperless.** Para pintar
la ficha de un cliente hay que saber qué papeleo tiene. Si eso viviera del otro
lado, cada ficha tendría que preguntarle a Paperless — más lenta, y con
Paperless caído la ficha se rompe. Es el mismo criterio de El Almacén: no
depender de un servicio externo para pintar una pantalla.

**El título se copia.** Si alguien borra el documento en Paperless, la fila
sigue diciendo qué era en lugar de quedar como un número huérfano — como
`CampanaEnvio.cliente_nombre` conserva a quién se le escribió.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class PapeleoLigado(models.Model):
    """Un documento de Paperless, ligado a exactamente UNA entidad."""

    documento_id = models.PositiveIntegerField(
        help_text="El id que le dio Paperless al documento.",
    )
    titulo = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Copia del título al ligarlo, para que la fila siga legible "
                  "si el documento desaparece del archivo.",
    )

    cliente = models.ForeignKey(
        "cartera.Cliente", null=True, blank=True, on_delete=models.CASCADE,
        related_name="papeleo",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", null=True, blank=True, on_delete=models.CASCADE,
        related_name="papeleo",
    )
    proveedor = models.ForeignKey(
        "el_catalogo.Proveedor", null=True, blank=True, on_delete=models.CASCADE,
        related_name="papeleo",
    )

    ligado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="papeleo_ligado",
    )
    automatico = models.BooleanField(
        default=False,
        help_text="La ligó la regla al entrar el documento, no una persona.",
    )
    ligado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "papeleo_ligado"
        verbose_name = "papeleo ligado"
        verbose_name_plural = "papeleo ligado"
        ordering = ["-ligado_en"]
        indexes = [models.Index(fields=["documento_id"])]
        constraints = [
            # Exactamente una entidad, garantizado por la BASE y no por una
            # promesa del código — el patrón de `Visita` (cliente XOR proveedor).
            models.CheckConstraint(
                name="papeleo_una_sola_entidad",
                condition=(
                    models.Q(cliente__isnull=False, proyecto__isnull=True,
                             proveedor__isnull=True)
                    | models.Q(cliente__isnull=True, proyecto__isnull=False,
                               proveedor__isnull=True)
                    | models.Q(cliente__isnull=True, proyecto__isnull=True,
                               proveedor__isnull=False)
                ),
            ),
            # Y no dos veces la misma liga. Van tres constraints parciales en
            # lugar de uno con las tres columnas porque en Postgres NULL nunca
            # es igual a NULL: un único constraint dejaría pasar duplicados.
            models.UniqueConstraint(
                fields=["documento_id", "cliente"], name="papeleo_unico_cliente",
                condition=models.Q(cliente__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["documento_id", "proyecto"], name="papeleo_unico_proyecto",
                condition=models.Q(proyecto__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["documento_id", "proveedor"], name="papeleo_unico_proveedor",
                condition=models.Q(proveedor__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.documento_id} → {self.a_quien or '(sin dueño)'}"

    @property
    def a_quien(self) -> str:
        """A nombre de quién está, en texto."""
        if self.cliente_id:
            return str(self.cliente)
        if self.proyecto_id:
            return str(self.proyecto)
        if self.proveedor_id:
            return str(self.proveedor)
        return ""

    @property
    def url_web(self) -> str:
        """Para abrirlo en Paperless. Vacío si no se configuró la dirección."""
        from lib import paperless

        return paperless.url_web(self.documento_id)
