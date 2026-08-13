from django.conf import settings
from django.db import models


class ServicioActivosManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(activo=True)


class Servicio(models.Model):
    """Servicio frecuente del despacho (precio base + unidad + categoría).
    Se usa como sugerencia al armar líneas de Cotización en S2b."""

    nombre = models.CharField(max_length=150, db_index=True)
    descripcion_default = models.TextField(blank=True, default="")
    # #12 (Sprint Fiscal 2026-07): unidad consolidada a 'pz'. Sin selector en
    # la UI; se conserva la columna por back-compat.
    unidad = models.CharField(max_length=30, default="pz")
    precio_base = models.DecimalField(max_digits=12, decimal_places=2)
    # S-LC-Feedback-V3: costo para cálculo de margen en proyectos/cotizaciones.
    costo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    categoria = models.ForeignKey(
        "el_catalogo.CategoriaServicio",
        on_delete=models.PROTECT,
        related_name="servicios",
    )
    activo = models.BooleanField(default=True, db_index=True)
    # LC 2026-07: imagen del producto (guardada en Google Drive, subcarpeta
    # "Productos"). Se sube por archivo o pegando desde el portapapeles.
    imagen_file_id = models.CharField(max_length=100, blank=True, default="")
    imagen_url = models.URLField(max_length=500, blank=True, default="")
    # S-LC-Feedback-V3: proveedores aplicables a este servicio.
    proveedores = models.ManyToManyField(
        "el_catalogo.Proveedor",
        blank=True,
        related_name="servicios",
    )
    # LC 2026-08-04 (Oscar): «el proveedor que se le pone a un proyecto los liga
    # de forma fuerte; si en un proyecto algo se asigna a otro proveedor, se le
    # liga también, pero el principal (primero) se mantiene».
    #
    # El «primero» NO podía ser el primero de la M2M: `Proveedor.Meta.ordering`
    # es alfabético, así que ligar un proveedor nuevo podía volverlo el primero
    # y cambiarle el default a todos los proyectos siguientes. Con este FK el
    # principal es explícito: los proveedores que se ligan desde un proyecto
    # entran a la M2M y NUNCA lo mueven (sólo lo ocupan si estaba vacío).
    proveedor_principal = models.ForeignKey(
        "el_catalogo.Proveedor",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="productos_principales",
        help_text="El que surte este producto por default. Los demás quedan como alternativas.",
    )
    # 2026-07: calculadora de costos por producto (usada solo por productos de
    # ciertos proveedores, p. ej. "Simil Cuero Plymouth"). Guarda los insumos
    # capturados: {"materiales": [4 montos], "sublimacion": [4 montos],
    # "mano_obra": monto, "factor": 2.2}. El subtotal (antes de IVA) alimenta
    # `precio_base`. Vacío = sin calculadora.
    detalles_costo = models.JSONField(default=dict, blank=True)
    # LC 2026-07-25 (Oscar): impresión + procesos adicionales del producto como
    # PLANTILLA. Misma forma que el `procesos_json` de la línea de proyecto:
    # [{"tipo": "impresion", "proveedor_id": N, "costo": "12.00", "por_pieza": true},
    #  {"tipo": "operativo", "descripcion": "Clavos", "costo": "30.00",
    #   "por_pieza": false, "proveedor_id": null}]
    # Al elegir el producto en un proyecto, la tarjeta se pre-llena con esto
    # (editable ahí). NO se suma a `costo` — el proyecto los cuenta aparte, así
    # que sumarlos aquí duplicaría el gasto.
    procesos_default = models.JSONField(default=list, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servicios_creados",
    )

    objects = models.Manager()
    activos = ServicioActivosManager()

    class Meta:
        db_table = "catalogo_servicio"
        ordering = ["categoria__orden", "nombre"]
        verbose_name = "servicio"
        verbose_name_plural = "servicios"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.categoria.nombre})"

    @property
    def proveedor_default(self):
        """Quién surte este producto por default (LC 2026-08-04).

        **Fuente única** del proveedor que se autocompleta en la tarjeta de
        producto y del que se muestra en la etiqueta del dropdown. Prefiere el
        `proveedor_principal` explícito; si no hay (catálogo viejo), cae al
        primero activo de la M2M — el comportamiento de siempre.
        """
        principal = self.proveedor_principal
        if principal is not None and principal.activo:
            return principal
        return next((p for p in self.proveedores.all() if p.activo), None)

    @property
    def fotos_ficha(self) -> list:
        """Los `file_id` que muestra la ficha del catálogo (LC 2026-08-12).

        Primero la foto del producto y luego las propias de sus usos en
        proyectos — las que se le pusieron a un alias («T-Shirt Modelo Janet»
        se ve distinta a la playera base). Sin repetir.

        Lee de `usos_con_foto` cuando la vista lo prefetcheó; sin eso consulta,
        así que **la lista siempre debe prefetchear** o son N+1.
        """
        fotos = [self.imagen_file_id] if self.imagen_file_id else []
        usos = getattr(self, "usos_con_foto", None)
        if usos is None:
            usos = self.en_proyectos.exclude(imagen_file_id="").only("imagen_file_id")
        for uso in usos:
            fid = getattr(uso, "imagen_file_id", "")
            if fid and fid not in fotos:
                fotos.append(fid)
        return fotos

    @property
    def margen_porcentaje(self) -> float:
        """Margen calculado (precio_base - costo) / precio_base × 100.

        Si precio_base es 0, devuelve 0. Si costo es 0, devuelve 100.
        """
        if not self.precio_base or self.precio_base <= 0:
            return 0.0
        return float((self.precio_base - self.costo) / self.precio_base * 100)
