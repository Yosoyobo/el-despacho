"""Catálogo de cuentas contables.

Modelo basado en partida doble. Cada cuenta tiene:
- `tipo`: activo/pasivo/capital/ingreso/egreso (5 grupos contables clásicos)
- `naturaleza`: deudora (saldo normal por cargos) o acreedora (por abonos)
- `codigo`: jerárquico dot-separated (`1.1.01` → cuenta de Caja)

V1 no busca compatibilidad SAT exacta — es un libro interno de gestión
encima de Tesorería. El Despacho NO emite CFDI ni timbra (regla §16);
el contador externo timbra aparte y reconcilia su libro fiscal con
exports de este libro.
"""

from __future__ import annotations

from django.db import models

TIPO_CUENTA_CHOICES = (
    ("activo", "Activo"),
    ("pasivo", "Pasivo"),
    ("capital", "Capital"),
    ("ingreso", "Ingreso"),
    ("egreso", "Egreso"),
)

NATURALEZA_CHOICES = (
    ("deudora", "Deudora"),
    ("acreedora", "Acreedora"),
)


class CuentaContableActivasManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(activa=True)


class CuentaContable(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True)
    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=TIPO_CUENTA_CHOICES, db_index=True)
    naturaleza = models.CharField(max_length=20, choices=NATURALEZA_CHOICES)

    descripcion = models.CharField(max_length=300, blank=True, default="")

    # Slot semántico para hookpoints automáticos de Tesorería.
    # Valores conocidos: 'caja', 'banco', 'cxc', 'cxp', 'ingreso_ventas',
    # 'egreso_operativo', 'iva_trasladado', 'iva_retenido', 'isr_retenido'.
    # NULL si la cuenta no participa de hooks.
    slot = models.CharField(max_length=40, blank=True, default="", db_index=True)

    activa = models.BooleanField(default=True, db_index=True)

    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    activas = CuentaContableActivasManager()

    class Meta:
        db_table = "contaduria_cuenta_contable"
        ordering = ["codigo"]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nombre}"
