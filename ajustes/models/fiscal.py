"""ConfiguracionFiscal — figuras fiscales editables por GUI (Gerencia).

Singleton (id=1). Centraliza las figuras fiscales del despacho para darles
flexibilidad: el régimen puede cambiar al crecer (RESICO PF → PM → General),
y con él las tasas de ISR/PTU y la base de cálculo. El IVA también vive aquí.

Lo consume:
- `apps.contaduria.reportes.estado_resultados` → estimación informativa de ISR
  y PTU (NO es cálculo fiscal real; eso lo hace el contador externo, regla §16).
- `apps.los_proyectos.Proyecto` → tasa de IVA para montos de proyecto/proveedor.

Regla del proyecto: si algo se puede configurar, vive en un GUI de Gerencia.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

REGIMEN_CHOICES = (
    ("resico_pf", "RESICO · Persona Física"),
    ("resico_pm", "RESICO · Persona Moral"),
    ("general_pm", "General de Ley · Persona Moral"),
    ("pf_actividad", "Persona Física con Actividad Empresarial"),
    ("rif", "RIF (Régimen de Incorporación Fiscal)"),
    ("otro", "Otro"),
)

# Base sobre la que se estima el ISR. RESICO PF tributa sobre ingresos
# cobrados (sin deducciones); los demás regímenes sobre la utilidad.
ISR_BASE_CHOICES = (
    ("ingresos", "Sobre ingresos"),
    ("utilidad", "Sobre la utilidad"),
)


class ConfiguracionFiscal(models.Model):
    # Singleton: siempre id=1 (ver obtener()).
    regimen = models.CharField(
        max_length=20, choices=REGIMEN_CHOICES, default="resico_pf",
        help_text="Régimen fiscal del despacho. Solo informativo + ayuda a elegir las tasas.",
    )
    isr_base = models.CharField(
        max_length=10, choices=ISR_BASE_CHOICES, default="ingresos",
        help_text="Sobre qué se estima el ISR: ingresos (RESICO PF) o utilidad.",
    )
    isr_tasa = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal("2.000"),
        help_text="% para estimar el ISR. RESICO PF ronda 1–2.5%; régimen general 30%.",
    )
    ptu_aplica = models.BooleanField(
        default=False,
        help_text="¿Se estima PTU? (normalmente no en RESICO PF sin empleados).",
    )
    ptu_tasa = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal("10.000"),
        help_text="% de PTU sobre la utilidad (estándar 10%).",
    )
    iva_tasa = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal("16.000"),
        help_text="% de IVA aplicable (estándar 16% en México).",
    )

    # ── Régimen de honorarios / Actividad Profesional (retenciones) ──────
    # Se usan cuando un proyecto/factura/cotización está en régimen
    # 'honorarios' (IVA y Retenciones). Defaults exactos de RESICO PF
    # profesional: ISR 1.25% del importe, retención de IVA 10.6667% del importe.
    #
    # Sprint Fiscal 2026-07 (Anexo 20 SAT): CADA impuesto se calcula de forma
    # 100% independiente = Base × tasa nominal / 100, y se redondea al final.
    # La retención de IVA dejó de calcularse como fracción (⅔) del IVA ya
    # redondeado (que no cuadraba con el PAC) y ahora usa su TASA NOMINAL sobre
    # la Base (10.6667% = ⅔ de 16%). Ej. 33,770 × 10.6667% = 3,602.14 (antes
    # 3,602.13). Ver lib/fiscal.desglose_honorarios.
    ret_isr_honorarios = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal("1.250"),
        help_text="% de retención de ISR sobre el importe (RESICO/honorarios: 1.25%).",
    )
    ret_iva_honorarios = models.DecimalField(
        max_digits=7, decimal_places=4, default=Decimal("10.6667"),
        help_text="% de retención de IVA sobre el importe/Base (RESICO/honorarios: 10.6667% = ⅔ del IVA 16%).",
    )
    # DEPRECADOS (Sprint Fiscal 2026-07): la retención de IVA ya no se calcula
    # como fracción num/den del IVA. Se conservan las columnas para no romper
    # migraciones/históricos; NO se usan en el cálculo ni en la GUI.
    # DEPRECADOS: ya no se usan en el cálculo (ver comentario arriba). El
    # help_text se conserva idéntico para no generar migración de estado.
    ret_iva_honorarios_num = models.PositiveSmallIntegerField(
        default=2,
        help_text="Numerador de la retención de IVA como fracción del IVA trasladado (⅔ → 2).",
    )
    ret_iva_honorarios_den = models.PositiveSmallIntegerField(
        default=3,
        help_text="Denominador de la retención de IVA como fracción del IVA trasladado (⅔ → 3).",
    )

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="config_fiscal_actualizadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajustes_configuracion_fiscal"
        verbose_name = "configuración fiscal"
        verbose_name_plural = "configuración fiscal"

    def __str__(self) -> str:
        return f"ConfiguracionFiscal({self.regimen})"

    # ── Helpers de tasa como fracción (0.16, 0.02, …) ────────────────────
    @property
    def iva_fraccion(self) -> Decimal:
        return (self.iva_tasa / Decimal("100")).quantize(Decimal("0.00001"))

    @property
    def isr_fraccion(self) -> Decimal:
        return (self.isr_tasa / Decimal("100")).quantize(Decimal("0.00001"))

    @property
    def ptu_fraccion(self) -> Decimal:
        return (self.ptu_tasa / Decimal("100")).quantize(Decimal("0.00001"))

    @classmethod
    def obtener(cls) -> ConfiguracionFiscal:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
