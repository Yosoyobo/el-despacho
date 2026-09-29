"""LinkPago — un enlace que el cliente abre para pagar en línea.

Tres orígenes (decisión de Oscar, 2026-09-29): el SALDO de una factura emitida,
el ANTICIPO de una cotización aprobada, o un MONTO LIBRE que alguien del
despacho escribe, ligado a un cliente o a un proyecto.

El monto es el TOTAL que se cobra, IVA incluido: lo que dice la factura, no la
base. Se congela al crear el link — si el saldo cambia, el link viejo se anula y
se hace otro (`services.link_para`), así el cliente nunca paga una cifra vieja.

**El token**: 32 bytes al azar (`secrets.token_urlsafe`), imposible de adivinar,
y en la URL viaja FIRMADO con la llave del servidor (`url_publica`). Un token
inventado o alterado ni siquiera llega a la base: la firma no cuadra y es 404.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import models
from django.utils import timezone

TIPOS_LINK = (
    ("factura", "Saldo de factura"),
    ("anticipo", "Anticipo de cotización"),
    ("libre", "Monto libre"),
)

ESTADOS_LINK = (
    ("vigente", "Vigente"),
    ("pagado", "Pagado"),
    ("anulado", "Anulado"),
    ("vencido", "Vencido"),
)

# Un link sirve un mes: suficiente para el ciclo de cobranza, corto para que un
# correo viejo no cobre algo que ya cambió. El de la cobranza se regenera solo.
DIAS_VIGENCIA = 30
SAL_FIRMA = "caja.link"
SEPARADOR = "."


def _token_nuevo() -> str:
    return secrets.token_urlsafe(32)


def _vence_default():
    return timezone.now() + timedelta(days=DIAS_VIGENCIA)


def _firmador() -> signing.Signer:
    return signing.Signer(salt=SAL_FIRMA, sep=SEPARADOR)


def token_de_url(firmado: str) -> str | None:
    """El token crudo de un segmento de URL firmado, o None si la firma no cuadra."""
    try:
        return _firmador().unsign(firmado or "")
    except signing.BadSignature:
        return None


class LinkPago(models.Model):
    token = models.CharField(max_length=64, unique=True, default=_token_nuevo, editable=False)
    tipo = models.CharField(max_length=10, choices=TIPOS_LINK, db_index=True)

    factura = models.ForeignKey(
        "facturacion.Factura", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="links_pago",
    )
    cotizacion = models.ForeignKey(
        "cotizaciones.Cotizacion", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="links_pago",
    )
    cliente = models.ForeignKey(
        "cartera.Cliente", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="links_pago",
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="links_pago",
    )

    # El TOTAL a cobrar (IVA incluido), congelado al crear el link.
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    concepto = models.CharField(max_length=200)
    moneda = models.CharField(max_length=3, default="MXN")

    estado = models.CharField(max_length=10, choices=ESTADOS_LINK, default="vigente", db_index=True)
    vence_en = models.DateTimeField(default=_vence_default)

    # Lo que la pasarela nos dio al abrir el cobro. Un link puede tener los dos:
    # el cliente elige con qué pagar.
    stripe_sesion_id = models.CharField(max_length=120, blank=True, default="")
    stripe_url = models.URLField(max_length=1000, blank=True, default="")
    stripe_sesion_expira = models.DateTimeField(null=True, blank=True)
    mp_preferencia_id = models.CharField(max_length=120, blank=True, default="")
    mp_url = models.URLField(max_length=1000, blank=True, default="")
    # Con cuál se pagó (vacío mientras no se paga).
    pasarela = models.CharField(max_length=12, blank=True, default="")

    pagado_en = models.DateTimeField(null=True, blank=True)
    anulado_en = models.DateTimeField(null=True, blank=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="links_pago_anulados",
    )
    motivo_anulacion = models.CharField(max_length=300, blank=True, default="")

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="links_pago_creados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "caja_link_pago"
        ordering = ["-creado_en"]
        verbose_name = "link de pago"
        verbose_name_plural = "links de pago"
        indexes = [
            models.Index(fields=["estado", "-creado_en"]),
            models.Index(fields=["factura", "estado"]),
            models.Index(fields=["cotizacion", "estado"]),
        ]

    def __str__(self) -> str:
        return f"LinkPago({self.pk}, {self.tipo}, ${self.monto}, {self.estado})"

    # ── URL pública ─────────────────────────────────────────────────────────

    @property
    def token_firmado(self) -> str:
        return _firmador().sign(self.token)

    def ruta_publica(self, sufijo: str = "") -> str:
        from django.urls import reverse
        nombre = {"": "caja:pagar", "gracias": "caja:pagar-gracias",
                  "cancelado": "caja:pagar-cancelado", "stripe": "caja:pagar-stripe",
                  "mercadopago": "caja:pagar-mercadopago"}[sufijo]
        return reverse(nombre, args=[self.token_firmado])

    def url_publica(self, sufijo: str = "") -> str:
        """La URL ABSOLUTA que se le manda al cliente."""
        base = getattr(settings, "TALLER_URL", "https://taller.learningcenter.mx/").rstrip("/")
        return f"{base}{self.ruta_publica(sufijo)}"

    # ── Estado derivado ─────────────────────────────────────────────────────

    @property
    def expirado(self) -> bool:
        return self.estado == "vigente" and self.vence_en is not None and self.vence_en <= timezone.now()

    @property
    def cobrable(self) -> bool:
        """¿Se le puede ofrecer al cliente pagar hoy?"""
        return self.estado == "vigente" and not self.expirado

    @property
    def pasarela_nombre(self) -> str:
        return {"stripe": "Stripe", "mercadopago": "MercadoPago"}.get(self.pasarela, self.pasarela)

    @property
    def referencia(self) -> str:
        """Lo que se muestra al cliente como «qué estoy pagando»."""
        if self.factura_id and self.factura:
            return f"Factura {self.factura.folio or self.factura.codigo}"
        if self.cotizacion_id and self.cotizacion:
            return f"Anticipo de {self.cotizacion.codigo}"
        return self.concepto
