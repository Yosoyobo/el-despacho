"""La Carga Contable: la contabilidad que se llevó fuera, de un jalón.

Cada subida de la plantilla es una `CargaContable`. Nace en `borrador` con el
archivo original y su vista previa; al aplicarla guarda qué creó (para poder
deshacerla completa) y las claves de cada renglón (para que volver a subir el
mismo archivo no duplique nada).

El archivo se guarda en la fila —no en El Almacén— porque es evidencia de la
carga: si mañana alguien pregunta «¿de dónde salió este asiento?», la respuesta
es el Excel que lo trajo, byte por byte.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

ESTADO_BORRADOR = "borrador"
ESTADO_APLICADA = "aplicada"
ESTADO_DESHECHA = "deshecha"

ESTADOS_CARGA = (
    (ESTADO_BORRADOR, "Vista previa"),
    (ESTADO_APLICADA, "Aplicada"),
    (ESTADO_DESHECHA, "Deshecha"),
)


class CargaContable(models.Model):
    estado = models.CharField(max_length=12, choices=ESTADOS_CARGA,
                              default=ESTADO_BORRADOR, db_index=True)

    # La plantilla llena (opcional: una carga puede ser sólo estados de cuenta).
    nombre_archivo = models.CharField(max_length=200, blank=True, default="")
    archivo = models.BinaryField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True, default="", db_index=True)
    # ¿Los movimientos de los estados de cuenta que no vengan en la plantilla
    # ni estén en El Despacho se crean como ingresos/gastos?
    crear_desde_estados = models.BooleanField(default=True)

    fecha_arranque = models.DateField(null=True, blank=True)

    # La vista previa (o el resultado, ya aplicada): conteos por hoja, renglones
    # con su estado, diferencias de saldos y el balance resultante.
    resumen = models.JSONField(default=dict, blank=True)
    # Lo que se creó al aplicar: {"ingresos": [pk…], "egresos": […],
    # "facturas": […], "asientos": […], "clientes": […]}.
    creados = models.JSONField(default=dict, blank=True)
    # Lo que sugirió El Chalán (estación `carga_contable`), por clave de
    # renglón. Se pregunta UNA vez al subir (o al recalcular) y se guarda: la
    # vista previa y la aplicación leen esto, así la IA no cambia de opinión
    # entre lo que se vio y lo que se guarda.
    ia = models.JSONField(default=dict, blank=True)
    # Una clave por renglón importado. Volver a subir el mismo renglón lo
    # reconoce y lo salta.
    claves = models.JSONField(default=list, blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cargas_contables",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    aplicada_en = models.DateTimeField(null=True, blank=True)
    aplicada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cargas_contables_aplicadas",
    )

    deshecha_en = models.DateTimeField(null=True, blank=True)
    deshecha_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cargas_contables_deshechas",
    )
    motivo_deshacer = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        db_table = "contaduria_carga"
        ordering = ["-creado_en"]

    def __str__(self) -> str:
        return f"Carga #{self.pk} · {self.nombre_archivo or 'sin nombre'} ({self.estado})"

    @property
    def aplicada(self) -> bool:
        return self.estado == ESTADO_APLICADA


class EstadoCuentaCarga(models.Model):
    """Un estado de cuenta subido con la carga, con la cuenta a la que pertenece.
    Se guarda aunque no se pueda leer (un PDF): es evidencia de la carga."""

    carga = models.ForeignKey(CargaContable, on_delete=models.CASCADE, related_name="estados_cuenta")
    cuenta = models.ForeignKey("contaduria.CuentaContable", on_delete=models.PROTECT,
                               related_name="estados_cuenta_cargados")
    nombre = models.CharField(max_length=200, blank=True, default="")
    contenido = models.BinaryField()
    sha256 = models.CharField(max_length=64, db_index=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "contaduria_carga_estado_cuenta"
        ordering = ["carga", "orden", "pk"]

    def __str__(self) -> str:
        return f"{self.nombre} → {self.cuenta.codigo}"
