"""ReglaCorreo — qué evento del sistema dispara qué plantilla.

Antes, los dos únicos correos automáticos (bienvenida y confirmación de pago)
estaban cableados en el código con un flag booleano cada uno. Aquí la relación
evento → plantilla se configura desde La Gerencia: se elige el evento, la
plantilla y el filtro que aplique, sin tocar código.

**Arrancan APAGADAS** (`activa=False`), igual que La Cobranza y los flags de
ConfiguracionCorreo. Un correo que sale solo hacia un cliente no debe
encenderse por el mero hecho de existir la fila.

Los disparos son best-effort: viven en `lib.reglas_correo` y se invocan desde
señales con `transaction.on_commit`. Un correo que falla JAMÁS tumba la
operación que lo originó (entregar un proyecto, aprobar una cotización…).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

# Cada evento declara qué filtro usa y qué variables garantiza. `filtro` dice
# qué campo de la regla lo acota; None = el evento no se filtra.
EVENTOS_CORREO = (
    ("proyecto_estado", "Un proyecto cambia de estado"),
    ("cotizacion_aprobada", "El cliente aprueba una cotización"),
    ("mandado_entregado", "Se marca una entrega como entregada"),
    ("mandado_en_camino", "El runner sale con una entrega"),
    ("cliente_dormido", "Un cliente lleva tiempo sin proyectos nuevos"),
)

# Metadatos por evento: qué necesita configurarse y qué recibe la plantilla.
META_EVENTOS: dict[str, dict] = {
    "proyecto_estado": {
        "filtro": "estado_slug",
        "ayuda_filtro": "Estado que dispara el aviso (ej. «entregado»). "
                        "Sin estado elegido, la regla no manda nada.",
        "variables": ["cliente", "empresa", "proyecto", "estado", "folio", "fecha"],
    },
    "cotizacion_aprobada": {
        "filtro": None,
        "ayuda_filtro": "",
        "variables": ["cliente", "empresa", "proyecto", "folio", "monto", "fecha"],
    },
    "mandado_entregado": {
        "filtro": None,
        "ayuda_filtro": "",
        "variables": ["cliente", "empresa", "proyecto", "mensaje", "fecha"],
    },
    "mandado_en_camino": {
        "filtro": None,
        "ayuda_filtro": "",
        # `posicion` y `llegada` salen de la ruta planeada cuando la entrega va
        # en una; si el runner salió sin ruta, llegan vacías y el correo se lee
        # igual. Una variable nunca falta: a lo mucho llega vacía.
        "variables": ["cliente", "empresa", "proyecto", "mensaje", "fecha",
                      "runner", "posicion", "llegada"],
    },
    "cliente_dormido": {
        "filtro": "dias",
        "ayuda_filtro": "Días sin un proyecto nuevo antes de mandar el correo.",
        "variables": ["cliente", "empresa", "fecha"],
    },
}


class ReglaCorreo(models.Model):
    evento = models.CharField(max_length=30, choices=EVENTOS_CORREO, db_index=True)
    plantilla = models.ForeignKey(
        "ajustes.PlantillaCorreo", on_delete=models.PROTECT,
        related_name="reglas",
        help_text="Plantilla que se manda cuando ocurre el evento.",
    )
    activa = models.BooleanField(
        default=False,
        help_text="Arranca apagada a propósito: enciéndela cuando la plantilla esté lista.",
    )
    # Filtros — cada evento usa el suyo (ver META_EVENTOS).
    estado_slug = models.SlugField(
        max_length=40, blank=True, default="",
        help_text="Sólo para «cambia de estado»: qué estado dispara el aviso.",
    )
    dias = models.PositiveIntegerField(
        default=90,
        help_text="Sólo para «cliente dormido»: días de silencio antes de escribirle.",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reglas_correo_creadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_regla_correo"
        ordering = ["evento", "pk"]
        verbose_name = "regla de correo"
        verbose_name_plural = "reglas de correo"
        constraints = [
            # Dos reglas iguales para el mismo evento+filtro mandarían el correo
            # dos veces. La base lo impide.
            models.UniqueConstraint(
                fields=["evento", "estado_slug"],
                name="regla_correo_unica_por_evento_y_estado",
            ),
        ]

    def __str__(self) -> str:
        return f"ReglaCorreo({self.evento} → {self.plantilla_id})"

    @property
    def meta(self) -> dict:
        return META_EVENTOS.get(self.evento, {})

    @property
    def esta_completa(self) -> bool:
        """False si le falta el filtro que su evento exige (no dispararía nada)."""
        filtro = self.meta.get("filtro")
        if filtro == "estado_slug":
            return bool(self.estado_slug)
        if filtro == "dias":
            return bool(self.dias)
        return True

    def descripcion_humana(self) -> str:
        """Cómo se lee la regla en la pantalla, en español llano."""
        if self.evento == "proyecto_estado":
            estado = self.estado_slug or "(falta elegir el estado)"
            return f"Cuando un proyecto pasa a «{estado}»"
        if self.evento == "cotizacion_aprobada":
            return "Cuando el cliente aprueba una cotización"
        if self.evento == "mandado_entregado":
            return "Cuando una entrega se marca como entregada"
        if self.evento == "cliente_dormido":
            return f"Cuando un cliente lleva {self.dias} días sin proyectos nuevos"
        return self.get_evento_display()

    @classmethod
    def activas_de(cls, evento: str):
        """Reglas encendidas de un evento, con su plantilla ya cargada."""
        return cls.objects.filter(
            evento=evento, activa=True, plantilla__activa=True,
        ).select_related("plantilla")


class CorreoEnviadoRegla(models.Model):
    """Bitácora de lo que mandó cada regla — y candado anti-repetición.

    Sin esto, «cliente dormido» le escribiría al mismo cliente cada vez que
    corre el cron, y un proyecto que rebota entre dos estados dispararía el
    aviso una y otra vez. La llave `referencia` identifica el hecho concreto
    (`proyecto:12:entregado`), así que un segundo intento se reconoce y se
    salta.
    """

    regla = models.ForeignKey(
        ReglaCorreo, on_delete=models.CASCADE, related_name="enviados",
    )
    referencia = models.CharField(max_length=120, db_index=True)
    destinatario = models.EmailField()
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=300, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ajustes_correo_enviado_regla"
        ordering = ["-creado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["regla", "referencia"],
                name="correo_regla_una_vez_por_referencia",
            ),
        ]

    def __str__(self) -> str:
        return f"CorreoEnviadoRegla({self.regla_id}, {self.referencia})"
