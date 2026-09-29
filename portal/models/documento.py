"""DocumentoCliente — lo que un cliente le entrega al despacho por el portal.

Comprobantes de pago, Constancia de Situación Fiscal, acta constitutiva, poderes,
identificaciones… (Oscar, 2026-09-29: «que el cliente pueda subir documentación»).
Lo sube la persona desde La Recepción, o alguien del equipo desde la ficha del
cliente cuando le llegó por otro lado; los dos caminos terminan en esta tabla.

**El archivo vive en El Almacén** (`archivo` es su llave, el sha256 del
contenido) con espejo en Drive, como cualquier adjunto del repo. El nombre que
escribió el cliente no toca el disco.

**Nada se da por bueno solo.** El documento nace `recibido`; alguien del equipo
lo marca `aprobado` o lo `rechazado` con un motivo que el cliente ve para volver
a subirlo. Un comprobante de pago NO registra el cobro (decisión de Oscar: «sólo
avisa»): quien cobra lo registra en la factura, con el comprobante a la vista.

**La CSF la lee El Chalán** (`portal/csf.py`): propone RFC, razón social, régimen
y código postal para la ficha y revisa que la constancia sea reciente (los días
se ajustan en La Gerencia → Portal de clientes). Lo que lee se guarda en `ia` y
sólo cambia la ficha si una persona lo aplica (`aplicado_en`).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

TIPO_COMPROBANTE = "comprobante_pago"
TIPO_CSF = "csf"

TIPOS_DOCUMENTO = (
    (TIPO_COMPROBANTE, "Comprobante de pago"),
    (TIPO_CSF, "Constancia de Situación Fiscal (CSF)"),
    ("rfc", "Cédula del RFC"),
    ("acta_constitutiva", "Acta constitutiva"),
    ("poder_notarial", "Poder del representante legal"),
    ("identificacion", "Identificación oficial del representante"),
    ("comprobante_domicilio", "Comprobante de domicilio"),
    ("contrato", "Contrato firmado"),
    ("otro", "Otro documento"),
)
TIPOS_DICT = dict(TIPOS_DOCUMENTO)

ESTADO_RECIBIDO = "recibido"
ESTADO_APROBADO = "aprobado"
ESTADO_RECHAZADO = "rechazado"
ESTADOS_DOCUMENTO = (
    (ESTADO_RECIBIDO, "En revisión"),
    (ESTADO_APROBADO, "Revisado"),
    (ESTADO_RECHAZADO, "Rechazado"),
)

# Lo que El Chalán hizo con el documento (sólo aplica a la CSF).
IA_NO_APLICA = ""
IA_PENDIENTE = "pendiente"
IA_LISTA = "lista"
IA_SIN_LEER = "sin_leer"
IA_ESTADOS = (
    (IA_NO_APLICA, "No aplica"),
    (IA_PENDIENTE, "El Chalán la está leyendo"),
    (IA_LISTA, "Leída"),
    (IA_SIN_LEER, "No se pudo leer"),
)


class DocumentoCliente(models.Model):
    cliente = models.ForeignKey(
        "cartera.Cliente", on_delete=models.CASCADE, related_name="documentos_portal",
    )
    tipo = models.CharField(max_length=24, choices=TIPOS_DOCUMENTO, db_index=True)

    # Quién lo subió: la persona del cliente (portal) o alguien del equipo.
    acceso = models.ForeignKey(
        "portal.AccesoCliente", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documentos",
    )
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documentos_cliente_subidos",
    )

    # El Almacén.
    archivo = models.CharField(max_length=128)
    nombre_archivo = models.CharField(max_length=200)
    mime = models.CharField(max_length=100, blank=True, default="")
    tamano = models.PositiveIntegerField(default=0)
    espejo_drive = models.CharField(max_length=128, blank=True, default="")

    nota = models.TextField(blank=True, default="")
    # Sólo para el comprobante de pago: de qué factura es (opcional).
    factura = models.ForeignKey(
        "facturacion.Factura", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="comprobantes_cliente",
    )

    estado = models.CharField(max_length=12, choices=ESTADOS_DOCUMENTO,
                              default=ESTADO_RECIBIDO, db_index=True)
    motivo_rechazo = models.CharField(max_length=500, blank=True, default="")
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documentos_cliente_revisados",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)

    # El Chalán (CSF): lo que leyó, su confianza y la revisión de vigencia.
    ia_estado = models.CharField(max_length=10, choices=IA_ESTADOS, blank=True, default=IA_NO_APLICA)
    ia = models.JSONField(default=dict, blank=True)
    aplicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documentos_cliente_aplicados",
    )
    aplicado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_documento"
        verbose_name = "documento del cliente"
        verbose_name_plural = "documentos del cliente"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["cliente", "tipo", "-creado_en"],
                                name="portal_doc_cliente_tipo")]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} · cliente {self.cliente_id}"

    @property
    def tipo_nombre(self) -> str:
        return TIPOS_DICT.get(self.tipo, self.tipo)

    @property
    def es_imagen(self) -> bool:
        return (self.mime or "").startswith("image/")

    @property
    def quien_subio(self) -> str:
        if self.acceso_id and self.acceso is not None:
            return self.acceso.nombre_visible
        if self.subido_por_id and self.subido_por is not None:
            return self.subido_por.get_short_name() or self.subido_por.email
        return ""

    @property
    def csf(self) -> dict:
        """Lo que leyó El Chalán de la constancia, o {}."""
        return (self.ia or {}).get("datos") or {} if self.tipo == TIPO_CSF else {}

    @property
    def vigencia(self) -> dict:
        return (self.ia or {}).get("vigencia") or {} if self.tipo == TIPO_CSF else {}
