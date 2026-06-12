"""Siembra el código agrupador SAT (Anexo 24) por cuenta — BORRADOR.

Mapeo razonable por código de cuenta; el contador externo lo refina antes
de presentar al SAT. Idempotente: solo escribe si el campo está vacío, así
no pisa ediciones manuales ni se rompe al re-aplicar.
"""

from django.db import migrations

# Mapa por código de cuenta del seed. Si la cuenta no está aquí, cae al
# prefijo por tipo.
AGRUPADOR_POR_CODIGO = {
    "1.1.01": "101",   # Caja
    "1.1.02": "102",   # Bancos
    "1.1.03": "102",   # Saldo en Stripe (bancos)
    "1.1.04": "102",   # Saldo en MercadoPago (bancos)
    "1.2.01": "105",   # Clientes
    "1.2.02": "107",   # Deudores diversos
    "1.3.01": "118",   # IVA acreditable pagado
    "2.1.01": "201",   # Proveedores
    "2.1.02": "205",   # Acreedores diversos
    "2.1.03": "205",   # Reembolsos por pagar
    "2.2.01": "209",   # IVA trasladado
    "2.2.02": "216",   # ISR retenido por pagar
    "2.2.03": "216",   # IVA retenido por pagar
    "3.1.01": "301",   # Capital social
    "3.2.01": "304",   # Utilidades acumuladas
    "3.2.02": "305",   # Utilidad del ejercicio
    "4.1.01": "401",   # Ingresos por servicios
    "4.2.01": "402",   # Otros ingresos
    "5.1.01": "601",   # Gastos de operación
    "5.1.02": "501",   # Materia prima e insumos (costo de venta)
    "5.1.03": "501",   # Servicios externos (costo de venta)
    "5.1.04": "601",   # Renta
    "5.1.05": "601",   # Servicios públicos
    "5.1.06": "601",   # Sueldos y salarios
    "5.1.07": "601",   # Honorarios
    "5.1.08": "601",   # Software y suscripciones
    "5.1.09": "601",   # Viáticos y transporte
    "5.1.99": "601",   # Otros gastos
}

PREFIJO_POR_TIPO = {
    "activo": "100", "pasivo": "200", "capital": "300",
    "ingreso": "400", "egreso": "600",
}


def sembrar(apps, schema_editor):
    Cuenta = apps.get_model("contaduria", "CuentaContable")
    for c in Cuenta.objects.all():
        if (c.codigo_agrupador_sat or "").strip():
            continue
        valor = AGRUPADOR_POR_CODIGO.get(c.codigo) or PREFIJO_POR_TIPO.get(c.tipo, "")
        if valor:
            c.codigo_agrupador_sat = valor
            c.save(update_fields=["codigo_agrupador_sat"])


def revertir(apps, schema_editor):
    # No-op: no borramos el dato al revertir (es informativo).
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("contaduria", "0008_cuentacontable_codigo_agrupador_sat_and_more"),
    ]
    operations = [migrations.RunPython(sembrar, revertir)]
