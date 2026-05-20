"""Catálogo de cuentas contables seed para La Contaduría V1.

Diseño SAT-style simplificado (~25 cuentas) suficiente para el flujo
de un despacho de diseño y maquila promocional. NO busca compatibilidad
exacta SAT — el contador externo timbra CFDI aparte.

Slots semánticos para hookpoints automáticos de Tesorería:
- `caja`: dinero en efectivo
- `banco`: cuentas de cheques y de inversión
- `cxc`: cuentas por cobrar (clientes)
- `cxp`: cuentas por pagar (proveedores)
- `reembolsos`: por reembolsar a empleados
- `ingreso_ventas`: ingresos por venta de servicios
- `egreso_operativo`: gastos generales de operación
"""

# (codigo, nombre, tipo, naturaleza, slot, descripcion)
CUENTAS_SEED = [
    # ── ACTIVOS ──
    ("1.1.01", "Caja", "activo", "deudora", "caja",
     "Efectivo en oficina y caja chica."),
    ("1.1.02", "Bancos", "activo", "deudora", "banco",
     "Cuentas de cheques y de inversión."),
    ("1.2.01", "Clientes", "activo", "deudora", "cxc",
     "Cuentas por cobrar a clientes B2B."),
    ("1.2.02", "Deudores diversos", "activo", "deudora", "",
     "Otros deudores no comerciales."),
    ("1.3.01", "IVA acreditable", "activo", "deudora", "iva_acreditable",
     "IVA pagado a proveedores, pendiente de acreditar."),

    # ── PASIVOS ──
    ("2.1.01", "Proveedores", "pasivo", "acreedora", "cxp",
     "Cuentas por pagar a proveedores."),
    ("2.1.02", "Acreedores diversos", "pasivo", "acreedora", "",
     "Otros acreedores no comerciales."),
    ("2.1.03", "Reembolsos por pagar", "pasivo", "acreedora", "reembolsos",
     "Gastos pagados por empleados pendientes de reembolso."),
    ("2.2.01", "IVA trasladado", "pasivo", "acreedora", "iva_trasladado",
     "IVA cobrado a clientes, pendiente de enterar."),
    ("2.2.02", "ISR retenido por pagar", "pasivo", "acreedora", "isr_retenido",
     "ISR retenido a terceros, pendiente de enterar."),
    ("2.2.03", "IVA retenido por pagar", "pasivo", "acreedora", "iva_retenido_pagar",
     "IVA retenido a terceros, pendiente de enterar."),

    # ── CAPITAL ──
    ("3.1.01", "Capital social", "capital", "acreedora", "",
     "Aportaciones de los socios."),
    ("3.2.01", "Utilidades acumuladas", "capital", "acreedora", "",
     "Utilidades de ejercicios anteriores no distribuidas."),
    ("3.2.02", "Utilidad del ejercicio", "capital", "acreedora", "",
     "Resultado del periodo en curso."),

    # ── INGRESOS ──
    ("4.1.01", "Ingresos por servicios", "ingreso", "acreedora", "ingreso_ventas",
     "Ingresos por servicios de diseño y maquila."),
    ("4.2.01", "Otros ingresos", "ingreso", "acreedora", "ingreso_otros",
     "Ingresos diversos no relacionados a la operación principal."),

    # ── EGRESOS ──
    ("5.1.01", "Gastos de operación", "egreso", "deudora", "egreso_operativo",
     "Gastos generales del despacho (default si no hay otra cuenta)."),
    ("5.1.02", "Materia prima e insumos", "egreso", "deudora", "egreso_insumos",
     "Materiales para producción de piezas promocionales."),
    ("5.1.03", "Servicios externos", "egreso", "deudora", "egreso_externos",
     "Maquila externa, impresión por terceros, freelancers."),
    ("5.1.04", "Renta de oficina", "egreso", "deudora", "egreso_renta",
     "Arrendamiento de oficina e instalaciones."),
    ("5.1.05", "Servicios públicos", "egreso", "deudora", "egreso_servicios",
     "Luz, agua, internet, teléfono."),
    ("5.1.06", "Sueldos y salarios", "egreso", "deudora", "egreso_nomina",
     "Nómina del equipo."),
    ("5.1.07", "Honorarios", "egreso", "deudora", "egreso_honorarios",
     "Honorarios profesionales (contador externo, etc.)."),
    ("5.1.08", "Software y suscripciones", "egreso", "deudora", "egreso_software",
     "Licencias de software, herramientas en la nube."),
    ("5.1.09", "Viáticos y transporte", "egreso", "deudora", "egreso_viaticos",
     "Gastos de movilidad del equipo."),
    ("5.1.99", "Otros gastos", "egreso", "deudora", "egreso_otros",
     "Gastos misceláneos no clasificables."),
]
