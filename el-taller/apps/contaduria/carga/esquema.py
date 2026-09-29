"""Hojas y columnas de la plantilla de carga contable.

Quien genera el Excel (`plantilla`) y quien lo lee (`lectura`) leen de aquí:
cambiar un título en un lado sin el otro es imposible.

Las columnas se reconocen por su título normalizado (sin acentos, sin
mayúsculas, sin «*»), y cada una acepta alias: si alguien pega un estado de
cuenta con «Importe» en vez de «Monto total», se entiende igual.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Nombres de hoja ──────────────────────────────────────────────────────
HOJA_LEEME = "Léeme"
HOJA_ARRANQUE = "1 Arranque"
HOJA_INGRESOS = "2 Ingresos"
HOJA_GASTOS = "3 Gastos"
HOJA_FACTURAS = "4 Facturas"
HOJA_POLIZAS = "5 Pólizas"
HOJA_HOY = "6 Saldos hoy"
HOJA_LISTAS = "Listas"
# No es una hoja de la plantilla: agrupa los movimientos de los estados de
# cuenta subidos junto con ella.
HOJA_ESTADOS = "Estados de cuenta"

# Fila del encabezado en las hojas de renglones (1 = título, 2 = ayuda).
FILA_ENCABEZADO = 3
# En las hojas de saldos: la fecha va en B2 y el encabezado en la fila 4.
CELDA_FECHA = "B2"
FILA_ENCABEZADO_SALDOS = 4


@dataclass(frozen=True)
class Columna:
    clave: str
    titulo: str
    tipo: str = "texto"          # texto | fecha | monto | si_no | lista
    requerido: bool = False
    ayuda: str = ""
    ancho: int = 18
    lista: str = ""              # nombre de la lista desplegable (hoja Listas)
    estricta: bool = True        # False = la lista sugiere, pero acepta otro valor
    alias: tuple[str, ...] = field(default_factory=tuple)


# ── Valores de las listas cerradas ───────────────────────────────────────
# (clave interna, etiqueta que ve la persona). Las de métodos salen de los
# modelos de Tesorería para no inventar una tercera versión.
SI_NO = (("si", "Sí"), ("no", "No"))

ESTADOS_GASTO = (
    ("pagado", "Pagado"),
    ("pendiente", "Pendiente de pago"),
    ("por_reembolsar", "Por reembolsar"),
)

REGIMENES_FACTURA = (
    ("honorarios", "Honorarios (IVA y retenciones)"),
    ("iva", "IVA 16 %"),
    ("exento", "Exento"),
)


# ── Hojas de renglones ───────────────────────────────────────────────────
COLUMNAS_INGRESOS = (
    Columna("fecha", "Fecha", "fecha", True, "El día que entró el dinero.", 12),
    Columna("descripcion", "Descripción", "texto", True, "Qué fue: «Pago de Heladería X», «Venta de mostrador».", 38,
            alias=("concepto",)),
    Columna("monto", "Monto total", "monto", True, "Lo que entró, con IVA si lo trae.", 14,
            alias=("monto", "importe", "deposito", "abono", "cantidad")),
    Columna("metodo", "Método", "lista", False, "Vacío = Transferencia.", 16, lista="metodos_ingreso"),
    Columna("cliente", "Cliente", "lista", False, "Nombre como está en La Cartera (o su RFC).", 28,
            lista="clientes", estricta=False),
    Columna("proyecto", "Proyecto", "texto", False, "Código LC-0000 del proyecto, si aplica.", 12),
    Columna("factura", "Factura que paga", "texto", False, "Folio (F123) o UUID. Vacío: se liga sola si es inequívoco.", 18,
            alias=("folio factura", "factura")),
    Columna("incluye_iva", "¿Incluye IVA?", "si_no", False, "Vacío = No.", 10, lista="si_no"),
    Columna("referencia", "Referencia del banco", "texto", False, "Folio o clave de rastreo del movimiento.", 20,
            alias=("referencia", "rastreo", "folio banco")),
    Columna("forzar", "Forzar", "si_no", False, "«Sí» para cargarlo aunque parezca repetido.", 9, lista="si_no"),
)

COLUMNAS_GASTOS = (
    Columna("fecha", "Fecha", "fecha", True, "El día del gasto.", 12),
    Columna("descripcion", "Descripción", "texto", True, "Qué se compró o pagó.", 38, alias=("concepto",)),
    Columna("monto", "Monto total", "monto", True, "Lo que salió, con IVA si lo trae.", 14,
            alias=("monto", "importe", "retiro", "cargo", "cantidad")),
    Columna("proveedor", "Proveedor", "lista", False, "Como está en el catálogo. Vacío = gasto operativo.", 26,
            lista="proveedores", estricta=False),
    Columna("centro", "Centro de costo", "lista", False, "Vacío = el primero de operación general.", 20,
            lista="centros"),
    Columna("metodo", "¿Cómo se pagó?", "lista", False, "Vacío = Transferencia empresa.", 22,
            lista="metodos_gasto", alias=("metodo", "forma de pago")),
    Columna("estado", "Estado", "lista", False, "Pagado, Pendiente de pago o Por reembolsar. Vacío = Pagado.", 18,
            lista="estados_gasto"),
    Columna("pagado_por", "Quién lo pagó (correo)", "texto", False, "Sólo para reembolsos: el correo de quien puso el dinero.", 26,
            alias=("pagado por", "quien lo pago")),
    Columna("proyecto", "Proyecto", "texto", False, "Código LC-0000 del proyecto, si aplica.", 12),
    Columna("incluye_iva", "¿Incluye IVA?", "si_no", False, "Vacío = No.", 10, lista="si_no"),
    Columna("forzar", "Forzar", "si_no", False, "«Sí» para cargarlo aunque parezca repetido.", 9, lista="si_no"),
)

COLUMNAS_FACTURAS = (
    Columna("folio", "Folio", "texto", False, "F123 (o sólo 123). Vacío = «Sin información».", 10),
    Columna("uuid", "UUID del CFDI", "texto", False, "Folio fiscal, si lo tienes.", 38, alias=("uuid", "folio fiscal")),
    Columna("cliente", "Cliente", "lista", True, "Si no existe en La Cartera, se da de alta.", 28,
            lista="clientes", estricta=False),
    Columna("rfc", "RFC del cliente", "texto", False, "Ayuda a encontrarlo (y a darlo de alta bien).", 15),
    Columna("concepto", "Concepto", "texto", True, "Lo que dice la factura.", 34, alias=("descripcion",)),
    Columna("fecha", "Fecha de emisión", "fecha", True, "", 12, alias=("fecha", "emision")),
    Columna("vencimiento", "Vencimiento", "fecha", False, "Vacío = 30 días después.", 12),
    Columna("total", "Total del CFDI", "monto", True, "El importe final de la factura, ya con impuestos.", 14,
            alias=("total", "importe", "monto")),
    Columna("regimen", "Régimen", "lista", False, "Vacío = Honorarios (lo de siempre en LC).", 26, lista="regimenes"),
    Columna("cobrado_antes", "Cobrado antes del arranque", "monto", False,
            "Sólo facturas ANTERIORES a la fecha de arranque: cuánto ya habían pagado.", 16),
    Columna("proyecto", "Proyecto", "texto", False, "Código LC-0000 del proyecto, si aplica.", 12),
    Columna("forzar", "Forzar", "si_no", False, "«Sí» para cargarla aunque parezca repetida.", 9, lista="si_no"),
)

COLUMNAS_POLIZAS = (
    Columna("poliza", "Póliza", "texto", True, "Un número o nombre: los renglones con la misma póliza forman un asiento.", 10,
            alias=("poliza", "numero", "asiento")),
    Columna("fecha", "Fecha", "fecha", True, "", 12),
    Columna("cuenta", "Cuenta", "lista", True, "Del catálogo de La Contaduría.", 34, lista="cuentas"),
    Columna("cargo", "Cargo", "monto", False, "Debe.", 14, alias=("debe",)),
    Columna("abono", "Abono", "monto", False, "Haber.", 14, alias=("haber",)),
    Columna("concepto", "Concepto", "texto", False, "", 34, alias=("descripcion",)),
)

# ── Hojas de saldos (arranque y hoy) ─────────────────────────────────────
COLUMNAS_SALDOS = (
    Columna("cuenta", "Cuenta", "lista", True, "", 34, lista="cuentas"),
    Columna("saldo", "Saldo", "monto", False, "Vacío = no lo sé / no tocar. 0 = vale cero.", 16,
            alias=("saldo real", "saldo")),
    Columna("notas", "Notas", "texto", False, "Para ti; no se importa.", 40),
)

HOJAS_RENGLONES = {
    HOJA_INGRESOS: COLUMNAS_INGRESOS,
    HOJA_GASTOS: COLUMNAS_GASTOS,
    HOJA_FACTURAS: COLUMNAS_FACTURAS,
    HOJA_POLIZAS: COLUMNAS_POLIZAS,
}

HOJAS_SALDOS = (HOJA_ARRANQUE, HOJA_HOY)

# Slots que NO se precargan en «1 Arranque»: su saldo sale del detalle de las
# hojas 3 y 4 (facturas por cobrar, gastos por pagar, reembolsos). Declararlos
# también no rompe nada —la diferencia se calcula contra lo ya cargado—, pero
# un saldo de clientes sin facturas detrás no se puede cobrar en El Taller.
SLOTS_DEL_DETALLE = frozenset({"cxc", "cxp", "reembolsos"})

# Cuenta contra la que cierra la apertura (lo acumulado antes del arranque).
CODIGO_UTILIDADES_ACUMULADAS = "3.2.01"
