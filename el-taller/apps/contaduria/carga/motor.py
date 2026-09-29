"""Motor de la carga contable: planear, ejecutar, deshacer.

**La vista previa y la aplicación son el mismo código.** `previsualizar` corre
la carga completa dentro de una transacción y la deshace al final; `aplicar` la
corre igual y la confirma. Así lo que se ve antes es exactamente lo que queda
después —mismo patrón que la vista previa de cotizaciones (2026.08.50)—, sin
una simulación paralela que pueda divergir. Lo que lo hace posible es
`lib.carga_masiva`: con la bandera puesta, los asientos que La Contaduría
normalmente difiere a `on_commit` se escriben en el acto, dentro de la misma
transacción, y los correos a clientes no salen.

**Cómo cuadra.** Los saldos declarados no se suman: se comparan. La apertura
registra la DIFERENCIA entre lo que el archivo dice que había al arrancar y lo
que El Despacho ya tenía a esa fecha (contra Utilidades acumuladas); la hoja
«Saldos hoy» registra la diferencia que quede al final (contra Ajustes de
captura). Por eso es seguro declarar un saldo aunque parte de su detalle ya
esté capturado: nunca se cuenta dos veces.

**Lo anterior al arranque no toca el año.** Una factura emitida antes de la
fecha de arranque que seguía sin cobrarse entra como cuenta por cobrar, pero su
ingreso va a Utilidades acumuladas, no a «Ingresos por servicios» del periodo;
lo mismo un gasto pendiente de antes (su costo ya ocurrió). Se hace dejando que
el asiento automático nazca como siempre y cambiándole la cuenta a esa partida.

**Nada a medias.** Con un solo renglón con error no se aplica: una
contabilidad cargada a medias es justo la que no cuadra.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from lib.carga_masiva import carga_masiva

from . import esquema as E
from . import ia as ia_mod
from . import lectura

CERO = Decimal("0.00")
UN_CENTAVO = Decimal("0.01")
TOLERANCIA_DIAS = 3

CREAR = "crear"
SALTAR = "saltar"
ERROR = "error"

# Cuentas cuyo saldo se enseña antes/después (por slot) + Utilidades acumuladas.
SLOTS_RESUMEN = ("caja", "banco", "stripe_saldo", "mp_saldo", "cxc", "cxp", "reembolsos",
                 "iva_trasladado", "iva_acreditable")


class CargaConErrores(Exception):
    def __init__(self, resultado: dict):
        super().__init__("La carga tiene renglones con error.")
        self.resultado = resultado


class CargaNoDeshacible(Exception):
    def __init__(self, motivos: list[str]):
        super().__init__("; ".join(motivos))
        self.motivos = motivos


class _Deshacer(Exception):
    """Sale de la transacción de la vista previa llevándose el resultado."""

    def __init__(self, resultado: dict):
        super().__init__()
        self.resultado = resultado


# ── Formato ──────────────────────────────────────────────────────────────

def _d(valor) -> str:
    return str(Decimal(valor or 0).quantize(UN_CENTAVO))


def _pesos(valor) -> str:
    return f"${Decimal(valor or 0):,.2f}"


def _pct(sug: dict) -> str:
    return f"confianza {int(round((sug.get('confianza') or 0) * 100))} %"


def _f(fecha: date | None) -> str:
    return fecha.strftime("%d/%m/%Y") if fecha else "—"


# ── Renglón del plan ─────────────────────────────────────────────────────

@dataclass
class Paso:
    hoja: str
    fila: int
    texto: str
    estado: str = CREAR
    mensajes: list[str] = field(default_factory=list)
    clave: str = ""
    ref: str = ""
    datos: dict = field(default_factory=dict)

    def error(self, msg: str) -> None:
        self.estado = ERROR
        self.mensajes.append(msg)

    def aviso(self, msg: str) -> None:
        self.mensajes.append(msg)

    def saltar(self, msg: str) -> None:
        if self.estado != ERROR:
            self.estado = SALTAR
        self.mensajes.append(msg)

    def como_dict(self) -> dict:
        return {"hoja": self.hoja, "fila": self.fila, "texto": self.texto, "estado": self.estado,
                "mensajes": self.mensajes, "ref": self.ref}


def _clave(hoja: str, valores: dict, ocurrencia: int) -> str:
    """Huella de un renglón: mismo contenido = misma clave. `ocurrencia`
    distingue dos renglones idénticos del mismo archivo (dos cafés del mismo
    precio el mismo día son dos gastos)."""
    limpio = {}
    for k, v in sorted(valores.items()):
        if k in ("forzar", "notas"):
            continue
        if isinstance(v, date):
            v = v.isoformat()
        elif isinstance(v, Decimal):
            v = _d(v)
        elif isinstance(v, str):
            v = lectura.normalizar(v)
        limpio[k] = v
    crudo = json.dumps([hoja, limpio, ocurrencia], sort_keys=True, default=str)
    return hashlib.sha1(crudo.encode("utf-8")).hexdigest()


# ── Catálogos precargados ────────────────────────────────────────────────

class _Catalogo:
    """Todo lo que el plan necesita resolver, cargado una vez."""

    def __init__(self, carga):
        from apps.contaduria.models import CargaContable, CuentaContable
        from apps.el_catalogo.models import Proveedor
        from apps.la_cartera.models import Cliente
        from apps.la_cartera.models.razon_social import ClienteRazonSocial
        from apps.los_proyectos.models import Proyecto
        from apps.tesoreria.models import CentroDeCosto
        from apps.tesoreria.models.egreso import METODOS_EGRESO, METODOS_REEMBOLSO
        from apps.tesoreria.models.ingreso import METODOS_INGRESO

        from cuentas.models.usuario import Usuario

        self.cuentas = list(CuentaContable.activas.order_by("codigo"))
        self.cuenta_codigo = {c.codigo: c for c in self.cuentas}
        self.cuenta_nombre = {lectura.normalizar(c.nombre): c for c in self.cuentas}
        self.cuenta_slot = {c.slot: c for c in self.cuentas if c.slot}

        self.clientes_nombre: dict[str, object] = {}
        self.clientes_rfc: dict[str, object] = {}
        for c in Cliente.objects.all():
            self.clientes_nombre.setdefault(lectura.normalizar(c.razon_social), c)
            if c.razon_social_fiscal:
                self.clientes_nombre.setdefault(lectura.normalizar(c.razon_social_fiscal), c)
            if c.rfc:
                self.clientes_rfc.setdefault(c.rfc.strip().upper(), c)
        for rs in ClienteRazonSocial.objects.select_related("cliente"):
            if rs.rfc:
                self.clientes_rfc.setdefault(rs.rfc.strip().upper(), rs.cliente)
            if rs.razon_social:
                self.clientes_nombre.setdefault(lectura.normalizar(rs.razon_social), rs.cliente)
        self.clientes_nuevos: dict[str, dict] = {}

        self.proveedores = {lectura.normalizar(p.razon_social): p for p in Proveedor.objects.all()}
        centros = list(CentroDeCosto.objects.filter(activo=True).order_by("nombre"))
        self.centros = {lectura.normalizar(c.nombre): c for c in centros}
        # El respaldo cuando nadie (ni El Chalán) dijo el centro: el comodín
        # («Otros», o uno «general»/«operación»), NUNCA el primero del alfabeto
        # (sería «Impuestos y comisiones» y ensuciaría ese centro).
        comodines = ("otros", "otro", "general", "operacion general", "gastos generales", "operacion")
        self.centro_default = (
            next((c for n in comodines for c in centros
                  if lectura.normalizar(c.nombre) == n or lectura.normalizar(c.slug) == n), None)
            or next((c for c in centros if c.naturaleza == "mixto"), None)
            or (centros[0] if centros else None)
        )
        self.proyectos = {p.codigo.upper(): p for p in Proyecto.objects.only("pk", "codigo", "nombre")}
        self.proyectos_nombre = {lectura.normalizar(p.nombre): p for p in self.proyectos.values()}
        self.usuarios = {u.email.lower(): u for u in Usuario.objects.filter(is_active=True)}

        def _mapa(opciones):
            m = {}
            for clave, etiqueta in opciones:
                m[lectura.normalizar(clave)] = clave
                m[lectura.normalizar(etiqueta)] = clave
            return m

        self.metodos_ingreso = _mapa(METODOS_INGRESO)
        self.metodos_gasto = _mapa(METODOS_EGRESO)
        self.metodos_reembolso = METODOS_REEMBOLSO
        self.estados_gasto = _mapa(E.ESTADOS_GASTO)
        self.regimenes = _mapa(E.REGIMENES_FACTURA)
        self.regimenes.update({"honorarios": "honorarios", "iva": "iva", "iva 16": "iva", "exento": "exento"})

        self.claves_previas: dict[str, int] = {}
        for pk, claves in (CargaContable.objects.filter(estado="aplicada")
                           .exclude(pk=getattr(carga, "pk", None)).values_list("pk", "claves")):
            for c in claves or []:
                self.claves_previas.setdefault(c, pk)

    def cuenta(self, texto: str):
        texto = (texto or "").strip()
        if not texto:
            return None
        codigo = re.split(r"\s*·\s*|\s+", texto, maxsplit=1)[0]
        return (self.cuenta_codigo.get(codigo)
                or self.cuenta_nombre.get(lectura.normalizar(texto))
                or self.cuenta_nombre.get(lectura.normalizar(texto.split("·", 1)[-1])))

    def cliente(self, nombre: str, rfc: str = ""):
        rfc = (rfc or "").strip().upper()
        if rfc and rfc in self.clientes_rfc:
            return self.clientes_rfc[rfc]
        n = lectura.normalizar(nombre)
        if n in self.clientes_nombre:
            return self.clientes_nombre[n]
        if n.upper() in self.clientes_rfc:  # escribieron el RFC en «Cliente»
            return self.clientes_rfc[n.upper()]
        return None

    def proyecto(self, texto: str):
        t = (texto or "").strip()
        if not t:
            return None
        return self.proyectos.get(t.upper()) or self.proyectos_nombre.get(lectura.normalizar(t))


# ── Facturas a las que se les puede ligar un cobro ───────────────────────

@dataclass
class _Cobrable:
    etiqueta: str                 # «F123» o «FAC-2026-0003»
    cliente_id: int | None
    cliente_nombre: str
    fecha: date
    saldo: Decimal
    factura: object = None        # la Factura (ya existente, o creada al ejecutar)
    paso: Paso | None = None      # si viene del archivo


def _folio_numero(texto: str) -> int | None:
    m = re.fullmatch(r"\s*[Ff]?\s*-?\s*0*(\d{1,9})\s*", texto or "")
    return int(m.group(1)) if m else None


# ── Plan ─────────────────────────────────────────────────────────────────

class _Plan:
    def __init__(self, libro: lectura.Libro, cat: _Catalogo, estados=(), crear_desde_estados: bool = True,
                 ia: dict | None = None):
        from apps.facturacion.models import Factura

        self.libro = libro
        self.cat = cat
        # Lo que El Chalán ya sugirió (por clave) y lo que falta preguntarle.
        self.ia = ia or {}
        self.pendientes_ia: list[dict] = []
        # [(nombre, cuenta, EstadoCuenta leído)]
        self.estados = list(estados)
        self.crear_desde_estados = crear_desde_estados
        self.movimientos: list[Paso] = []
        self.F = libro.arranque.fecha
        self.H = libro.hoy.fecha
        self.pasos: list[Paso] = []
        self.avisos: list[str] = []
        self.facturas: list[Paso] = []
        self.ingresos: list[Paso] = []
        self.gastos: list[Paso] = []
        self.polizas: list[Paso] = []
        self.saldos_arranque: list[Paso] = []
        self.saldos_hoy: list[Paso] = []

        # Índice de cobrables: facturas existentes con saldo (y las del
        # archivo, que se agregan al planearlas).
        self.cobrables: dict[str, _Cobrable] = {}
        self._cobrables_lista: list[_Cobrable] = []
        self.facturas_db = list(
            Factura.objects.select_related("cliente").order_by("pk")
        )
        for fac in self.facturas_db:
            if fac.estado not in ("emitida", "cobrada_parcial"):
                continue
            saldo = fac.saldo_pendiente
            if saldo <= 0:
                continue
            cob = _Cobrable(fac.folio or fac.codigo, fac.cliente_id, fac.cliente.razon_social,
                            fac.fecha_emision, saldo, factura=fac)
            self._registrar_cobrable(cob, fac.folio, fac.codigo, fac.cfdi_uuid,
                                     str(fac.folio_numero or ""))

        self._ocurrencias: dict[tuple, int] = {}
        self._usados_ingreso: set[int] = set()
        self._usados_egreso: set[int] = set()

    # -- utilidades --
    def _registrar_cobrable(self, cob: _Cobrable, *claves: str) -> None:
        self._cobrables_lista.append(cob)
        for k in claves:
            if k:
                self.cobrables[k.strip().upper()] = cob

    def _nuevo_paso(self, fila: lectura.Fila, texto: str) -> Paso:
        p = Paso(fila.hoja, fila.numero, texto)
        for e in fila.errores:
            p.error(e)
        firma = (fila.hoja, json.dumps({k: v for k, v in fila.valores.items() if k != "forzar"},
                                       sort_keys=True, default=str))
        n = self._ocurrencias.get(firma, 0)
        self._ocurrencias[firma] = n + 1
        p.clave = _clave(fila.hoja, fila.valores, n)
        if p.clave in self.cat.claves_previas:
            p.saltar(f"Ya se cargó en la carga #{self.cat.claves_previas[p.clave]}.")
        self.pasos.append(p)
        return p

    def _antes_del_arranque(self, fecha: date | None) -> bool:
        return bool(self.F and fecha and fecha < self.F)

    def armar(self) -> _Plan:
        self._planear_saldos()
        for fila in self.libro.renglones.get(E.HOJA_FACTURAS, []):
            self._planear_factura(fila)
        for fila in self.libro.renglones.get(E.HOJA_INGRESOS, []):
            self._planear_ingreso(fila)
        for fila in self.libro.renglones.get(E.HOJA_GASTOS, []):
            self._planear_gasto(fila)
        self._planear_polizas(self.libro.renglones.get(E.HOJA_POLIZAS, []))
        self._planear_estados()
        self._avisos_generales()
        return self

    # -- saldos --
    def _planear_saldos(self) -> None:
        for hoja, datos, destino in ((E.HOJA_ARRANQUE, self.libro.arranque, self.saldos_arranque),
                                     (E.HOJA_HOY, self.libro.hoy, self.saldos_hoy)):
            vistas: set[int] = set()
            fecha = datos.fecha
            for fila in datos.filas:
                v = fila.valores
                cuenta = self.cat.cuenta(v.get("cuenta") or "")
                p = Paso(hoja, fila.numero, f"{v.get('cuenta') or '—'} · {_pesos(v.get('saldo'))}")
                for e in fila.errores:
                    p.error(e)
                self.pasos.append(p)
                if datos.error_fecha:
                    p.error(f"La fecha de la hoja: {datos.error_fecha}.")
                elif fecha is None:
                    p.error("Falta la fecha de la hoja (celda B2).")
                if cuenta is None:
                    p.error(f"No encuentro la cuenta «{v.get('cuenta')}» en el catálogo.")
                elif cuenta.pk in vistas:
                    p.error(f"La cuenta {cuenta.codigo} viene dos veces en esta hoja.")
                else:
                    vistas.add(cuenta.pk)
                    if cuenta.tipo not in ("activo", "pasivo", "capital"):
                        p.error(f"{cuenta.codigo} es de resultados: su saldo sale de los movimientos, no se declara.")
                    elif hoja == E.HOJA_ARRANQUE and cuenta.slot in E.SLOTS_DEL_DETALLE:
                        p.aviso(f"{cuenta.nombre}: lo normal es que salga de las facturas o los gastos "
                                "pendientes. Si la declaras, sólo se registra la diferencia.")
                if hoja == E.HOJA_HOY and fecha and self.F and fecha < self.F:
                    p.error("La fecha de «Saldos hoy» es anterior a la fecha de arranque.")
                p.datos = {"cuenta": cuenta, "saldo": v.get("saldo") or CERO, "fecha": fecha}
                destino.append(p)

    # -- facturas --
    def _planear_factura(self, fila: lectura.Fila) -> None:
        v = fila.valores
        total = v.get("total")
        p = self._nuevo_paso(fila, f"{v.get('folio') or 's/folio'} · {v.get('cliente') or '—'} · "
                                   f"{_f(v.get('fecha'))} · {_pesos(total)}")
        self.facturas.append(p)
        forzar = bool(v.get("forzar"))
        fecha = v.get("fecha")

        folio_txt = (v.get("folio") or "").strip()
        folio = _folio_numero(folio_txt) if folio_txt else None
        if folio_txt and folio is None:
            p.aviso(f"El folio «{folio_txt}» no es F###: se guarda en las notas.")
        uuid = (v.get("uuid") or "").strip().upper()

        cliente = self.cat.cliente(v.get("cliente") or "", v.get("rfc") or "")
        nombre_cliente = (v.get("cliente") or "").strip()
        if cliente is None and nombre_cliente:
            clave_n = lectura.normalizar(nombre_cliente)
            if clave_n not in self.cat.clientes_nuevos:
                self.cat.clientes_nuevos[clave_n] = {"razon_social": nombre_cliente,
                                                     "rfc": (v.get("rfc") or "").strip().upper()[:13]}
                p.aviso(f"Se dará de alta el cliente «{nombre_cliente}» en La Cartera.")

        if total is not None and total <= 0:
            p.error("El total debe ser mayor a cero.")
        regimen_txt = v.get("regimen") or ""
        regimen = self.cat.regimenes.get(lectura.normalizar(regimen_txt), None) if regimen_txt else "honorarios"
        if regimen is None:
            p.error(f"Régimen «{regimen_txt}» no reconocido (Honorarios, IVA 16 % o Exento).")
        elif regimen == "iva" and _tasa_iva() is None:
            p.error("No hay una tasa de IVA trasladado del 16 % activa en Los Ajustes.")

        previo = self._antes_del_arranque(fecha)
        cobrado = v.get("cobrado_antes") or CERO
        if cobrado < 0:
            p.error("«Cobrado antes del arranque» no puede ser negativo.")
        if cobrado > 0 and not previo:
            p.error("«Cobrado antes del arranque» es sólo para facturas anteriores a la fecha de arranque; "
                    "los cobros de las demás van en la hoja 2 Ingresos.")
        if total and cobrado > total:
            p.error("Lo cobrado antes del arranque es mayor que el total.")
        if previo and total and total - cobrado <= 0 and not forzar:
            p.saltar("Ya estaba cobrada completa antes del arranque: no hay nada que cargar.")
        proyecto = self.cat.proyecto(v.get("proyecto") or "")
        if v.get("proyecto") and proyecto is None:
            p.aviso(f"No encuentro el proyecto «{v.get('proyecto')}»: se carga sin proyecto.")

        # ¿Ya existe?
        if p.estado != ERROR:
            existente = None
            if folio is not None:
                existente = next((f for f in self.facturas_db if f.folio_numero == folio), None)
                if existente is not None and existente.estado == "cancelada":
                    p.error(f"El folio F{folio} ya lo usa {existente.codigo} (cancelada). "
                            "Quita el folio o cámbialo.")
                    existente = None
                elif existente is None and any(
                    o is not p and o.datos.get("folio") == folio for o in self.facturas
                ):
                    p.error(f"El folio F{folio} viene dos veces en la hoja.")
            if existente is None and uuid:
                existente = next((f for f in self.facturas_db if (f.cfdi_uuid or "").upper() == uuid), None)
            if existente is None and cliente is not None and total and fecha and not forzar:
                existente = next((
                    f for f in self.facturas_db
                    if f.estado != "cancelada" and f.cliente_id == cliente.pk
                    and abs(f.fecha_emision - fecha).days <= TOLERANCIA_DIAS
                    and abs(Decimal(str(f.calcular_totales()["total"])) - total) <= UN_CENTAVO
                ), None)
            if existente is not None:
                p.saltar(f"Ya está en El Despacho como {existente.folio_display} ({existente.codigo}).")
                p.ref = existente.codigo
                self._registrar_cobrable_si_falta(p, existente, folio_txt, uuid)

        p.datos = {"folio": folio, "folio_txt": folio_txt, "uuid": uuid, "cliente": cliente,
                   "cliente_nombre": nombre_cliente, "rfc": (v.get("rfc") or "").strip().upper()[:13],
                   "concepto": (v.get("concepto") or "").strip(), "fecha": fecha,
                   "vencimiento": v.get("vencimiento") or (fecha + timedelta(days=30) if fecha else None),
                   "total": total, "regimen": regimen or "honorarios", "cobrado": cobrado,
                   "previo": previo, "proyecto": proyecto}
        if p.estado == CREAR:
            cob = _Cobrable(f"F{folio}" if folio else (folio_txt or nombre_cliente), getattr(cliente, "pk", None),
                            nombre_cliente, fecha, (total or CERO) - cobrado, paso=p)
            self._registrar_cobrable(cob, f"F{folio}" if folio else "", str(folio or ""), uuid, folio_txt)

    def _registrar_cobrable_si_falta(self, p: Paso, fac, folio_txt: str, uuid: str) -> None:
        for k in (folio_txt, uuid, fac.codigo, fac.folio):
            if k and k.strip().upper() in self.cobrables:
                return
        cob = _Cobrable(fac.folio or fac.codigo, fac.cliente_id, fac.cliente.razon_social,
                        fac.fecha_emision, fac.saldo_pendiente, factura=fac)
        self._registrar_cobrable(cob, folio_txt, uuid, fac.codigo, fac.folio)

    # -- ingresos --
    def _planear_ingreso(self, fila: lectura.Fila) -> None:
        from apps.tesoreria.models import Ingreso

        v = fila.valores
        monto, fecha = v.get("monto"), v.get("fecha")
        p = self._nuevo_paso(fila, f"{_f(fecha)} · {(v.get('descripcion') or '')[:60]} · {_pesos(monto)}")
        self.ingresos.append(p)
        forzar = bool(v.get("forzar"))

        if monto is not None and monto <= 0:
            p.error("El monto debe ser positivo (los retiros van en la hoja 3 Gastos).")
        if self._antes_del_arranque(fecha):
            p.error(f"Es anterior a la fecha de arranque ({_f(self.F)}): lo de antes entra en los saldos "
                    "de la hoja 1 (o como «Cobrado antes del arranque» de su factura).")
        metodo_txt = v.get("metodo") or ""
        metodo = self.cat.metodos_ingreso.get(lectura.normalizar(metodo_txt)) if metodo_txt else "transferencia"
        if metodo is None:
            p.error(f"Método «{metodo_txt}» no reconocido.")
        cliente = None
        if v.get("cliente"):
            cliente = self.cat.cliente(v["cliente"])
            if cliente is None:
                p.aviso(f"«{v['cliente']}» no está en La Cartera: el ingreso se carga sin cliente.")
        proyecto = self.cat.proyecto(v.get("proyecto") or "")
        if v.get("proyecto") and proyecto is None:
            p.aviso(f"No encuentro el proyecto «{v.get('proyecto')}»: se carga sin proyecto.")

        # ¿Ya está capturado?
        if p.estado == CREAR and monto and fecha and not forzar:
            dup = (Ingreso.vigentes.filter(monto=monto, fecha__range=(fecha - timedelta(days=TOLERANCIA_DIAS),
                                                                        fecha + timedelta(days=TOLERANCIA_DIAS)))
                   .exclude(pk__in=self._usados_ingreso).order_by("fecha").first())
            if dup is not None:
                self._usados_ingreso.add(dup.pk)
                p.saltar(f"Ya está en El Despacho como {dup.codigo} ({_f(dup.fecha)}).")
                p.ref = dup.codigo

        # ¿Qué factura paga?
        cobrable = None
        if p.estado == CREAR and monto:
            ref_fac = (v.get("factura") or "").strip()
            if ref_fac:
                cobrable = (self.cobrables.get(ref_fac.upper())
                            or self.cobrables.get(f"F{_folio_numero(ref_fac)}" if _folio_numero(ref_fac) else ""))
                if cobrable is None:
                    p.error(f"No encuentro la factura «{ref_fac}» con saldo por cobrar (ni en El Despacho ni en la hoja 4).")
            elif not forzar:
                candidatas = [
                    c for c in self._cobrables_lista
                    if abs(c.saldo - monto) <= UN_CENTAVO and (fecha is None or c.fecha is None or c.fecha <= fecha)
                    and (cliente is None or c.cliente_id == cliente.pk)
                ]
                if len(candidatas) == 1:
                    cobrable = candidatas[0]
                    p.aviso(f"Se liga sola como cobro de {cobrable.etiqueta} (mismo monto"
                            f"{' y cliente' if cliente else ''}).")
                elif len(candidatas) > 1:
                    cobrable = self._desempate_ia(p, candidatas, v)
            if cobrable is not None:
                if monto > cobrable.saldo + UN_CENTAVO:
                    p.error(f"Excede lo que falta por cobrar de {cobrable.etiqueta} ({_pesos(cobrable.saldo)}).")
                    cobrable = None
                else:
                    cobrable.saldo -= monto
                    if cliente is None and cobrable.cliente_id:
                        cliente = getattr(cobrable.factura, "cliente", None) or cliente
        p.datos = {"monto": monto, "fecha": fecha, "metodo": metodo or "transferencia",
                   "descripcion": (v.get("descripcion") or "").strip(), "cliente": cliente,
                   "proyecto": proyecto, "incluye_iva": bool(v.get("incluye_iva")),
                   "referencia": (v.get("referencia") or "").strip(), "cobrable": cobrable}

    # -- gastos --
    def _planear_gasto(self, fila: lectura.Fila) -> None:
        from apps.tesoreria.models import Egreso

        v = fila.valores
        monto, fecha = v.get("monto"), v.get("fecha")
        p = self._nuevo_paso(fila, f"{_f(fecha)} · {(v.get('descripcion') or '')[:60]} · {_pesos(monto)}")
        self.gastos.append(p)
        forzar = bool(v.get("forzar"))

        if monto is not None and monto <= 0:
            p.error("El monto debe ser positivo.")
        metodo_txt = v.get("metodo") or ""
        metodo = self.cat.metodos_gasto.get(lectura.normalizar(metodo_txt)) if metodo_txt else "transferencia"
        if metodo is None:
            p.error(f"«¿Cómo se pagó?»: «{metodo_txt}» no reconocido.")
        estado_txt = v.get("estado") or ""
        if estado_txt:
            estado = self.cat.estados_gasto.get(lectura.normalizar(estado_txt))
            if estado is None:
                p.error(f"Estado «{estado_txt}» no reconocido (Pagado, Pendiente de pago, Por reembolsar).")
        else:
            estado = "por_reembolsar" if metodo in self.cat.metodos_reembolso else "pagado"
        previo = self._antes_del_arranque(fecha)
        if previo and estado == "pagado":
            p.error(f"Es anterior a la fecha de arranque ({_f(self.F)}) y ya estaba pagado: lo de antes entra "
                    "en los saldos de la hoja 1.")
        elif previo:
            p.aviso("Anterior al arranque: queda como pendiente de pago, sin tocar los gastos del periodo.")

        centro_txt = v.get("centro") or ""
        centro = self.cat.centros.get(lectura.normalizar(centro_txt)) if centro_txt else self.cat.centro_default
        proveedor_ia = None
        if not centro_txt and p.estado == CREAR:
            centro, proveedor_ia = self._centro_ia(p, v, centro)
        if centro is None:
            p.error(f"Centro de costo «{centro_txt}» no existe." if centro_txt
                    else "No hay ningún centro de costo activo: crea uno en La Gerencia → Catálogos.")
        proveedor = (self.cat.proveedores.get(lectura.normalizar(v.get("proveedor") or "")) if v.get("proveedor")
                     else proveedor_ia)
        pagado_por = None
        if v.get("pagado_por"):
            pagado_por = self.cat.usuarios.get(v["pagado_por"].strip().lower())
            if pagado_por is None:
                p.error(f"No hay un usuario activo con el correo «{v['pagado_por']}».")
        elif estado == "por_reembolsar":
            p.aviso("Sin «Quién lo pagó» no aparece en Reembolsos por persona.")
        proyecto = self.cat.proyecto(v.get("proyecto") or "")
        if v.get("proyecto") and proyecto is None:
            p.aviso(f"No encuentro el proyecto «{v.get('proyecto')}»: se carga sin proyecto.")

        if p.estado == CREAR and monto and fecha and not forzar:
            dup = (Egreso.vigentes.filter(monto=monto, fecha__range=(fecha - timedelta(days=TOLERANCIA_DIAS),
                                                                       fecha + timedelta(days=TOLERANCIA_DIAS)))
                   .exclude(pk__in=self._usados_egreso).order_by("fecha").first())
            if dup is not None:
                self._usados_egreso.add(dup.pk)
                p.saltar(f"Ya está en El Despacho como {dup.codigo} ({_f(dup.fecha)}).")
                p.ref = dup.codigo
        p.datos = {"monto": monto, "fecha": fecha, "metodo": metodo or "transferencia", "estado": estado or "pagado",
                   "descripcion": (v.get("descripcion") or "").strip(), "proveedor": proveedor,
                   "proveedor_nombre": (v.get("proveedor") or "").strip(), "centro": centro,
                   "pagado_por": pagado_por, "proyecto": proyecto, "incluye_iva": bool(v.get("incluye_iva")),
                   "previo": previo}

    # -- pólizas --
    def _planear_polizas(self, filas: list[lectura.Fila]) -> None:
        grupos: dict[str, list[lectura.Fila]] = {}
        for fila in filas:
            clave = lectura.normalizar(fila.valores.get("poliza") or "") or f"fila-{fila.numero}"
            grupos.setdefault(clave, []).append(fila)
        for clave, grupo in grupos.items():
            primera = grupo[0]
            valores = {f"{i}:{k}": val for i, f in enumerate(grupo) for k, val in f.valores.items()}
            sintetica = lectura.Fila(E.HOJA_POLIZAS, primera.numero, valores,
                                     [f"fila {f.numero}: {e}" for f in grupo for e in f.errores])
            cargos = sum((f.valores.get("cargo") or CERO for f in grupo), CERO)
            abonos = sum((f.valores.get("abono") or CERO for f in grupo), CERO)
            p = self._nuevo_paso(sintetica, f"Póliza {primera.valores.get('poliza') or '—'} · "
                                            f"{_f(primera.valores.get('fecha'))} · {_pesos(cargos)}")
            self.polizas.append(p)
            fechas = {f.valores.get("fecha") for f in grupo}
            fecha = primera.valores.get("fecha")
            if len(fechas) > 1:
                p.error("Los renglones de una misma póliza deben tener la misma fecha.")
            if self._antes_del_arranque(fecha):
                p.error(f"Es anterior a la fecha de arranque ({_f(self.F)}): lo de antes entra en los saldos.")
            if len(grupo) < 2:
                p.error("Una póliza necesita al menos dos renglones (cargo y abono).")
            partidas = []
            for i, f in enumerate(grupo):
                cuenta = self.cat.cuenta(f.valores.get("cuenta") or "")
                cargo, abono = f.valores.get("cargo") or CERO, f.valores.get("abono") or CERO
                if cuenta is None:
                    p.error(f"fila {f.numero}: no encuentro la cuenta «{f.valores.get('cuenta')}».")
                if cargo < 0 or abono < 0:
                    p.error(f"fila {f.numero}: cargo y abono van en positivo.")
                if (cargo > 0) == (abono > 0):
                    p.error(f"fila {f.numero}: lleva cargo O abono (uno de los dos).")
                partidas.append({"cuenta": cuenta, "cargo": cargo, "abono": abono, "orden": i,
                                 "descripcion": (f.valores.get("concepto") or "")[:200]})
            if cargos != abonos:
                p.error(f"No cuadra: cargos {_pesos(cargos)} ≠ abonos {_pesos(abonos)}.")
            p.datos = {"poliza": primera.valores.get("poliza") or clave, "fecha": fecha, "partidas": partidas,
                       "concepto": next((f.valores.get("concepto") for f in grupo if f.valores.get("concepto")), "")}

    # -- estados de cuenta --
    def _planear_estados(self) -> None:
        """Cada movimiento del banco: ¿ya viene en la plantilla? ¿ya está en El
        Despacho? Si no, se crea (depósito → ingreso, retiro → gasto). El saldo
        del último día sirve de comprobación de esa cuenta."""
        from apps.tesoreria.models import Egreso, Ingreso

        declaradas_hoy = {p.datos["cuenta"].pk for p in self.saldos_hoy if p.datos.get("cuenta") is not None}
        usados_plantilla: set[int] = set()
        vistos_por_archivo: dict[tuple, int] = {}
        antes = 0
        for i, (nombre, cuenta, ec) in enumerate(self.estados):
            if ec.error:
                self.avisos.append(f"Estado de cuenta «{nombre}»: {ec.error}")
                continue
            for m in ec.movimientos:
                if self._antes_del_arranque(m.fecha):
                    antes += 1
                    continue
                fila = lectura.Fila(E.HOJA_ESTADOS, m.fila, {
                    "archivo": nombre, "cuenta": cuenta.codigo, "fecha": m.fecha, "monto": m.monto,
                    "descripcion": m.descripcion, "saldo": m.saldo, "referencia": m.referencia})
                p = self._nuevo_paso(fila, f"{nombre} · {_f(m.fecha)} · {m.descripcion[:50]} · "
                                           f"{'+' if m.monto > 0 else '−'}{_pesos(abs(m.monto))}")
                self.movimientos.append(p)
                es_ingreso = m.monto > 0
                monto = abs(m.monto)
                p.datos = {"tipo": "ingreso" if es_ingreso else "gasto", "cuenta": cuenta, "fecha": m.fecha,
                           "monto": monto, "descripcion": m.descripcion or "Movimiento del estado de cuenta",
                           "referencia": m.referencia, "_signo": 1 if es_ingreso else -1}
                if p.estado != CREAR:
                    continue
                # El mismo movimiento en dos estados de cuenta que se enciman.
                huella = (cuenta.pk, m.fecha, m.monto, lectura.normalizar(m.descripcion), m.saldo)
                if huella in vistos_por_archivo and vistos_por_archivo[huella] != i:
                    p.saltar("Repetido en otro estado de cuenta de la misma carga.")
                    continue
                vistos_por_archivo.setdefault(huella, i)
                # ¿Viene en la plantilla?
                gemelo = self._gemelo_en_plantilla(p, es_ingreso, usados_plantilla)
                if gemelo is not None:
                    usados_plantilla.add(id(gemelo))
                    p.saltar(f"Ya viene en la plantilla ({gemelo.hoja}, fila {gemelo.fila}).")
                    continue
                # ¿Ya está en El Despacho?
                rango = (m.fecha - timedelta(days=TOLERANCIA_DIAS), m.fecha + timedelta(days=TOLERANCIA_DIAS))
                modelo, usados = (Ingreso, self._usados_ingreso) if es_ingreso else (Egreso, self._usados_egreso)
                dup = (modelo.vigentes.filter(monto=monto, fecha__range=rango)
                       .exclude(pk__in=usados).order_by("fecha").first())
                if dup is not None:
                    usados.add(dup.pk)
                    p.saltar(f"Ya está en El Despacho como {dup.codigo} ({_f(dup.fecha)}).")
                    p.ref = dup.codigo
                    continue
                if not self.crear_desde_estados:
                    p.saltar("No se crea: elegiste no crear lo que sólo viene en el estado de cuenta.")
                    continue
                self._clasificar_movimiento(p, es_ingreso, m)
            final = ec.saldo_final
            if final is not None and cuenta.pk not in declaradas_hoy and not self._antes_del_arranque(final[0]):
                declaradas_hoy.add(cuenta.pk)
                p = Paso(E.HOJA_HOY, 0, f"{cuenta.codigo} · {_pesos(final[1])} (saldo final de «{nombre}»)")
                p.datos = {"cuenta": cuenta, "saldo": final[1], "fecha": final[0]}
                self.pasos.append(p)
                self.saldos_hoy.append(p)
        if antes:
            self.avisos.append(f"{antes} movimiento{'s' if antes != 1 else ''} de los estados de cuenta "
                               f"son anteriores al arranque ({_f(self.F)}): no se cargan, van en los saldos.")

    # -- El Chalán --
    def _sugerencia(self, p: Paso, payload: dict) -> dict | None:
        """La sugerencia guardada de El Chalán para este renglón, o `None` (y lo
        deja pendiente de preguntar). Sólo cuenta si pasa el umbral."""
        sug = self.ia.get(p.clave)
        if sug is None:
            self.pendientes_ia.append({"clave": p.clave, **payload})
            return None
        if (sug.get("confianza") or 0) < ia_mod.UMBRAL_CONFIANZA:
            p.aviso(f"🤖 El Chalán no estuvo seguro ({_pct(sug)}): va con la regla de siempre; revísalo.")
            return None
        return sug

    def _clasificar_movimiento(self, p: Paso, es_ingreso: bool, m) -> None:
        """Qué es un movimiento que sólo trae el banco. Lo propone El Chalán;
        se valida contra el catálogo; si no hay respuesta válida, regla de siempre."""
        d = p.datos
        sug = self._sugerencia(p, {
            "origen": "estado de cuenta", "cuenta": d["cuenta"].codigo, "fecha": d["fecha"].isoformat(),
            "monto": _d(m.monto), "descripcion": d["descripcion"], "referencia": d["referencia"],
        })
        if sug is not None:
            tipo = sug["tipo"]
            if es_ingreso and tipo == "cobro" and sug.get("factura"):
                cob = self.cobrables.get(sug["factura"].upper())
                if cob is not None and d["monto"] <= cob.saldo + UN_CENTAVO:
                    cob.saldo -= d["monto"]
                    d.update(tipo="cobro", cobrable=cob)
                    p.aviso(f"🤖 El Chalán: es el cobro de {cob.etiqueta} ({_pct(sug)}).")
                    return
            if tipo in ("traspaso", "impuesto", "prestamo", "aportacion", "otro") and sug.get("cuenta"):
                contra = self.cat.cuenta(sug["cuenta"])
                if (contra is not None and contra.pk != d["cuenta"].pk
                        and contra.tipo in ("activo", "pasivo", "capital")):
                    d.update(tipo="asiento", contra=contra, concepto=sug.get("concepto") or d["descripcion"])
                    p.aviso(f"🤖 El Chalán: {tipo} con {contra.codigo} {contra.nombre}, no es ingreso ni gasto "
                            f"({_pct(sug)}).")
                    return
            if es_ingreso and tipo in ("cobro", "ingreso"):
                cliente = self.cat.cliente(sug.get("cliente") or "") if sug.get("cliente") else None
                d["cliente"] = cliente
                p.aviso("🤖 El Chalán: ingreso" + (f" de {cliente}" if cliente else " sin cliente")
                        + f" ({_pct(sug)}).")
                return
            if not es_ingreso and tipo in ("gasto", "comision"):
                centro = self._centro_valido(sug.get("centro")) or self.cat.centro_default
                prov = self.cat.proveedores.get(lectura.normalizar(sug.get("proveedor") or ""))
                if centro is not None:
                    d.update(centro=centro, proveedor=prov, concepto=sug.get("concepto"))
                    p.aviso(f"🤖 El Chalán: {'comisión del banco' if tipo == 'comision' else 'gasto'} de "
                            f"«{centro}»" + (f", proveedor {prov}" if prov else "") + f" ({_pct(sug)}).")
                    return
            p.aviso(f"🤖 El Chalán dijo «{tipo}», pero no con datos del catálogo: va con la regla de siempre.")
        # Regla de siempre.
        if es_ingreso:
            p.aviso("Sólo viene en el estado de cuenta: se crea como ingreso sin cliente.")
        elif self.cat.centro_default is None:
            p.error("No hay ningún centro de costo activo para crear este gasto.")
        else:
            d["centro"] = self.cat.centro_default
            p.aviso(f"Sólo viene en el estado de cuenta: se crea como gasto de «{self.cat.centro_default}». "
                    "Si era otra cosa (traspaso, impuesto), agrégalo a la plantilla y vuelve a subir.")

    def _centro_valido(self, texto):
        if not texto:
            return None
        n = lectura.normalizar(texto)
        return self.cat.centros.get(n) or next(
            (c for c in self.cat.centros.values() if lectura.normalizar(c.slug) == n), None)

    def _centro_ia(self, p: Paso, v: dict, default):
        """Gasto de la plantilla sin centro de costo: que El Chalán lo sugiera."""
        sug = self._sugerencia(p, {"origen": "plantilla", "solo_centro": True, "fecha": str(v.get("fecha")),
                                   "monto": _d(v.get("monto")), "descripcion": v.get("descripcion") or "",
                                   "proveedor": v.get("proveedor") or ""})
        if sug is None:
            return default, None
        centro = self._centro_valido(sug.get("centro"))
        prov = self.cat.proveedores.get(lectura.normalizar(sug.get("proveedor") or "")) if not v.get("proveedor") else None
        if centro is None:
            return default, prov
        p.aviso(f"🤖 El Chalán sugiere el centro «{centro}»" + (f" y el proveedor {prov}" if prov else "")
                + f" ({_pct(sug)}).")
        return centro, prov

    def _desempate_ia(self, p: Paso, candidatas: list, v: dict):
        """Un cobro que podría ser de varias facturas: El Chalán elige ENTRE ellas."""
        sug = self._sugerencia(p, {
            "origen": "plantilla", "fecha": str(v.get("fecha")), "monto": _d(v.get("monto")),
            "descripcion": v.get("descripcion") or "", "cliente": v.get("cliente") or "",
            "referencia": v.get("referencia") or "", "candidatas": [c.etiqueta for c in candidatas[:6]],
        })
        elegida = None
        if sug is not None and sug.get("factura"):
            elegida = next((c for c in candidatas if c.etiqueta.upper() == sug["factura"].upper()), None)
        if elegida is not None:
            p.aviso(f"🤖 El Chalán: entre {', '.join(c.etiqueta for c in candidatas[:4])}, es {elegida.etiqueta} "
                    f"({_pct(sug)}).")
            return elegida
        p.error("Podría ser el cobro de " + ", ".join(c.etiqueta for c in candidatas[:4])
                + ": escribe cuál en «Factura que paga» (o «Sí» en Forzar para cargarlo suelto).")
        return None

    def catalogo_ia(self) -> dict:
        """Lo que El Chalán necesita ver para contestar con datos reales."""
        vistos = set()
        facturas = []
        for c in self._cobrables_lista:
            if id(c) in vistos or c.saldo <= 0:
                continue
            vistos.add(id(c))
            facturas.append(f"{c.etiqueta} · {c.cliente_nombre} · {_d(c.saldo)} · {c.fecha}")
        return {
            "clientes": sorted({getattr(c, "razon_social", "") for c in self.cat.clientes_nombre.values()} - {""}),
            "proveedores": sorted(p.razon_social for p in self.cat.proveedores.values()),
            "centros": [f"{c.slug}: {c.nombre}" for c in self.cat.centros.values()],
            "facturas": facturas,
            "cuentas": [f"{c.codigo} · {c.nombre}" for c in self.cat.cuentas
                        if c.tipo in ("activo", "pasivo", "capital")],
        }

    def _gemelo_en_plantilla(self, p: Paso, es_ingreso: bool, usados: set[int]):
        """El renglón de la plantilla (o partida de póliza) que es este mismo
        movimiento: mismo monto, ±3 días, misma dirección."""
        d = p.datos
        for q in (self.ingresos if es_ingreso else self.gastos):
            if id(q) in usados or q.estado == ERROR or not q.datos.get("fecha"):
                continue
            if q.datos.get("monto") == d["monto"] and abs((q.datos["fecha"] - d["fecha"]).days) <= TOLERANCIA_DIAS:
                return q
        firmado = d["monto"] if es_ingreso else -d["monto"]
        for q in self.polizas:
            if id(q) in usados or q.estado == ERROR or not q.datos.get("fecha"):
                continue
            if abs((q.datos["fecha"] - d["fecha"]).days) > TOLERANCIA_DIAS:
                continue
            for x in q.datos.get("partidas", []):
                if x["cuenta"] is not None and x["cuenta"].pk == d["cuenta"].pk and x["cargo"] - x["abono"] == firmado:
                    return q
        return None

    def _avisos_generales(self) -> None:
        from apps.contaduria.models import CierrePeriodo

        if self.libro.hojas_faltantes:
            self.avisos.append("No vienen las hojas: " + ", ".join(self.libro.hojas_faltantes)
                               + ". Se cargó lo demás.")
        if (self.libro.arranque.filas or self.saldos_arranque) and self.F is None:
            self.avisos.append("La hoja 1 trae saldos pero no la fecha de arranque (celda B2).")
        fechas = [p.datos.get("fecha") for p in self.pasos if p.estado == CREAR and p.datos.get("fecha")]
        if self.saldos_arranque and self.F:
            fechas.append(self.F)
        if fechas:
            desde, hasta = min(fechas), max(fechas)
            cierres = CierrePeriodo.objects.filter(reabierto=False, desde__lte=hasta, hasta__gte=desde)
            for c in cierres:
                self.avisos.append(f"Hay un cierre de periodo del {_f(c.desde)} al {_f(c.hasta)}: lo que se cargue "
                                   "en esas fechas lo mueve. Reábrelo y ciérralo otra vez al terminar.")

    @property
    def errores(self) -> int:
        return sum(1 for p in self.pasos if p.estado == ERROR)


# ── Ejecución ────────────────────────────────────────────────────────────

def _tasa_iva():
    from ajustes.models.tasa import TasaImpositiva

    return (TasaImpositiva.objects.filter(tipo="trasladado", activa=True, porcentaje=Decimal("16"))
            .order_by("orden").first())


def _saldos_resumen(cat: _Catalogo) -> dict[str, dict]:
    from apps.contaduria.services import saldo_cuenta

    salida = {}
    cuentas = [cat.cuenta_slot[s] for s in SLOTS_RESUMEN if s in cat.cuenta_slot]
    ua = cat.cuenta_codigo.get(E.CODIGO_UTILIDADES_ACUMULADAS)
    if ua is not None:
        cuentas.append(ua)
    for c in cuentas:
        salida[c.codigo] = {"nombre": c.nombre, "saldo": _d(saldo_cuenta(c))}
    return salida


def _reubicar(referencia: str, de, a, nota: str) -> None:
    """Cambia de cuenta la partida `de` del asiento automático `referencia`
    (lo anterior al arranque va a Utilidades acumuladas, no al periodo)."""
    from apps.contaduria.models import Asiento, Partida

    asiento = Asiento.vigentes.filter(referencia_externa=referencia).first()
    if asiento is None:
        raise RuntimeError(f"No se generó el asiento automático de {referencia}: revisa el catálogo de cuentas.")
    Partida.objects.filter(asiento=asiento, cuenta=de).update(cuenta=a)
    Asiento.objects.filter(pk=asiento.pk).update(descripcion=f"{asiento.descripcion} · {nota}"[:300])


def _estado_por_cobro(fac) -> None:
    from apps.facturacion.services import recalcular_monto_cobrado

    recalcular_monto_cobrado(fac)
    total = fac.calcular_totales()["total"]
    if fac.monto_cobrado + UN_CENTAVO >= total:
        fac.estado = "cobrada_total"
    elif fac.monto_cobrado > 0:
        fac.estado = "cobrada_parcial"
    else:
        fac.estado = "emitida"
    fac.save(update_fields=["estado", "monto_cobrado", "actualizado_en"])


class _Ejecucion:
    def __init__(self, plan: _Plan, carga, actor):
        self.plan = plan
        self.cat = plan.cat
        self.carga = carga
        self.actor = actor if getattr(actor, "is_authenticated", False) else None
        self.creados: dict[str, list] = {"ingresos": [], "egresos": {}, "facturas": [], "asientos": [],
                                         "clientes": [], "facturas_tocadas": []}
        self.utilidades = self.cat.cuenta_codigo.get(E.CODIGO_UTILIDADES_ACUMULADAS)
        self.apertura: dict = {}
        self.cuadre: dict = {}

    def correr(self) -> None:
        if self.plan.F and self.utilidades is None and (self.plan.saldos_arranque or any(
                p.datos.get("previo") for p in self.plan.facturas + self.plan.gastos)):
            raise RuntimeError(f"Falta la cuenta {E.CODIGO_UTILIDADES_ACUMULADAS} Utilidades acumuladas.")
        for p in self.plan.facturas:
            if p.estado == CREAR:
                self._factura(p)
        for p in self.plan.ingresos:
            if p.estado == CREAR:
                self._ingreso(p)
        for p in self.plan.gastos:
            if p.estado == CREAR:
                self._gasto(p)
        for p in self.plan.polizas:
            if p.estado == CREAR:
                self._poliza(p)
        for p in self.plan.movimientos:
            if p.estado == CREAR:
                self._movimiento_banco(p)
        self.apertura = self._diferencias(self.plan.saldos_arranque, apertura=True)
        self.cuadre = self._diferencias(self.plan.saldos_hoy, apertura=False)

    # -- clientes --
    def _cliente_para(self, p: Paso):
        if p.datos.get("cliente") is not None:
            return p.datos["cliente"]
        from apps.la_cartera.models import Cliente

        clave = lectura.normalizar(p.datos["cliente_nombre"])
        ya = self.cat.clientes_nombre.get(clave)
        if ya is not None:
            return ya
        datos = self.cat.clientes_nuevos.get(clave) or {"razon_social": p.datos["cliente_nombre"], "rfc": ""}
        cli = Cliente.objects.create(
            razon_social=datos["razon_social"][:200], rfc=datos["rfc"], estado="activo",
            notas=f"Alta automática por la carga contable #{self.carga.pk}.", creado_por=self.actor,
        )
        self.cat.clientes_nombre[clave] = cli
        self.creados["clientes"].append(cli.pk)
        return cli

    # -- factura --
    def _factura(self, p: Paso) -> None:
        from apps.facturacion.models import Factura, FacturaImpuesto
        from apps.facturacion.models.factura import _generar_codigo
        from apps.facturacion.services import fijar_total_con_impuestos
        from apps.tesoreria.models import Ingreso

        d = p.datos
        cli = self._cliente_para(p)
        notas = f"Importada con la carga contable #{self.carga.pk}."
        if d["folio_txt"] and d["folio"] is None:
            notas += f" Folio original: {d['folio_txt']}."
        fac = Factura(
            cliente=cli, proyecto=d["proyecto"], concepto=d["concepto"][:200], titulo=d["concepto"][:200],
            estado="borrador", fecha_emision=d["fecha"], fecha_vencimiento=d["vencimiento"],
            regimen_fiscal=d["regimen"], folio_numero=d["folio"], cfdi_uuid=d["uuid"][:40],
            notas=notas, creado_por=self.actor,
        )
        # Se inserta sin `save()`: éste inventa un folio F### cuando viene vacío,
        # y una factura importada sin folio debe quedar «Sin información».
        with transaction.atomic():
            fac.codigo = _generar_codigo(d["fecha"].year)
            Factura.objects.bulk_create([fac])
        if d["regimen"] == "iva":
            FacturaImpuesto.objects.create(factura=fac, tasa=_tasa_iva())
        fijar_total_con_impuestos(fac, d["total"])
        fac.estado = "emitida"
        fac.emitida_en = timezone.now()
        fac.emitida_por = self.actor
        fac.save(update_fields=["estado", "emitida_en", "emitida_por", "actualizado_en"])
        if d["previo"]:
            _reubicar(f"facturacion.factura:{fac.pk}", self.cat.cuenta_slot.get("ingreso_ventas"),
                      self.utilidades, "anterior al arranque")
        self.creados["facturas"].append(fac.pk)
        if d["cobrado"] > 0:
            ing = Ingreso.objects.create(
                factura=fac, monto=d["cobrado"], subtotal=d["cobrado"], fecha=self.plan.F - timedelta(days=1),
                metodo="otro", descripcion=f"Cobrado antes del arranque · {fac.folio or fac.codigo}",
                cliente=cli, proyecto=d["proyecto"], creado_por=self.actor,
            )
            _reubicar(f"tesoreria.ingreso:{ing.pk}", self.cat.cuenta_slot.get("banco"),
                      self.utilidades, "anterior al arranque")
            self.creados["ingresos"].append(ing.pk)
            _estado_por_cobro(fac)
        p.ref = f"{fac.folio_display} · {fac.codigo}"
        # Los cobros de la hoja 2 la encuentran por aquí.
        for cob in self.plan._cobrables_lista:
            if cob.paso is p:
                cob.factura = fac

    # -- ingreso --
    def _ingreso(self, p: Paso) -> None:
        from apps.tesoreria.forms import _desglosar_total
        from apps.tesoreria.models import Ingreso

        d = p.datos
        monto, subtotal = _desglosar_total(d["monto"], d["incluye_iva"])
        fac = d["cobrable"].factura if d["cobrable"] is not None else None
        ing = Ingreso.objects.create(
            monto=monto, subtotal=subtotal, incluye_iva=d["incluye_iva"], fecha=d["fecha"],
            descripcion=d["descripcion"][:300], cliente=d["cliente"] or getattr(fac, "cliente", None),
            proyecto=d["proyecto"] or getattr(fac, "proyecto", None), metodo=d["metodo"],
            referencia_externa=d["referencia"][:100], factura=fac, creado_por=self.actor,
        )
        self.creados["ingresos"].append(ing.pk)
        if fac is not None:
            if fac.pk not in self.creados["facturas"] and fac.pk not in self.creados["facturas_tocadas"]:
                self.creados["facturas_tocadas"].append(fac.pk)
            _estado_por_cobro(fac)
        p.ref = ing.codigo + (f" → {fac.folio_display}" if fac is not None else "")

    # -- gasto --
    def _gasto(self, p: Paso) -> None:
        from apps.tesoreria.forms import _desglosar_total
        from apps.tesoreria.models import Egreso

        d = p.datos
        monto, subtotal = _desglosar_total(d["monto"], d["incluye_iva"])
        prov = d["proveedor"]
        eg = Egreso.objects.create(
            monto=monto, subtotal=subtotal, incluye_iva=d["incluye_iva"], fecha=d["fecha"],
            descripcion=d["descripcion"][:300], proveedor=prov,
            proveedor_nombre=(prov.razon_social if prov else (d["proveedor_nombre"] or "Gasto operativo"))[:200],
            centro_de_costo=d["centro"], proyecto=d["proyecto"], pagado_por=d["pagado_por"],
            estado_pago=d["estado"], metodo=d["metodo"], creado_por=self.actor,
        )
        if d["previo"]:
            _reubicar(f"tesoreria.egreso:{eg.pk}", self.cat.cuenta_slot.get("egreso_operativo"),
                      self.utilidades, "anterior al arranque")
        self.creados["egresos"][str(eg.pk)] = eg.estado_pago
        p.ref = eg.codigo

    # -- movimiento que sólo venía en el estado de cuenta --
    def _movimiento_banco(self, p: Paso) -> None:
        from apps.contaduria.services import crear_asiento
        from apps.contaduria.signals import _cuenta_efectivo_o_banco, _cuenta_salida_egreso
        from apps.tesoreria.models import Egreso, Ingreso

        d = p.datos
        cuenta = d["cuenta"]
        if d["tipo"] == "asiento":
            # Entra dinero: cargo a la cuenta del estado de cuenta; sale: abono.
            monto = d["monto"]
            destino, origen = (cuenta, d["contra"]) if d["_signo"] > 0 else (d["contra"], cuenta)
            partidas = [{"cuenta": destino, "cargo": monto, "orden": 0}, {"cuenta": origen, "abono": monto, "orden": 1}]
            asiento = crear_asiento(
                descripcion=f"{d['concepto'] or d['descripcion']} (estado de cuenta)"[:300], partidas=partidas,
                fecha=d["fecha"], origen="carga", creado_por=self.actor, idempotente=False,
                referencia_externa=f"contaduria.carga:{self.carga.pk}:banco:{p.clave[:16]}",
            )
            self.creados["asientos"].append(asiento.pk)
            p.ref = asiento.codigo
            return
        if d["tipo"] in ("ingreso", "cobro"):
            metodo = {"caja": "efectivo", "stripe_saldo": "stripe", "mp_saldo": "mercadopago"}.get(
                cuenta.slot, "transferencia")
            fac = d["cobrable"].factura if d.get("cobrable") is not None else None
            ing = Ingreso.objects.create(
                monto=d["monto"], subtotal=d["monto"], fecha=d["fecha"], descripcion=d["descripcion"][:300],
                metodo=metodo, referencia_externa=d["referencia"][:100], creado_por=self.actor,
                cliente=d.get("cliente") or getattr(fac, "cliente", None), factura=fac,
                proyecto=getattr(fac, "proyecto", None),
            )
            if fac is not None:
                if fac.pk not in self.creados["facturas"] and fac.pk not in self.creados["facturas_tocadas"]:
                    self.creados["facturas_tocadas"].append(fac.pk)
                _estado_por_cobro(fac)
            natural = _cuenta_efectivo_o_banco(metodo)
            if natural is not None and natural.pk != cuenta.pk:
                _reubicar(f"tesoreria.ingreso:{ing.pk}", natural, cuenta, f"estado de cuenta {cuenta.codigo}")
            self.creados["ingresos"].append(ing.pk)
            p.ref = ing.codigo
            return
        metodo = "efectivo" if cuenta.slot == "caja" else "transferencia"
        prov = d.get("proveedor")
        eg = Egreso.objects.create(
            monto=d["monto"], subtotal=d["monto"], fecha=d["fecha"], descripcion=d["descripcion"][:300],
            proveedor=prov, proveedor_nombre=(prov.razon_social if prov else "Gasto operativo")[:200],
            centro_de_costo=d.get("centro") or self.cat.centro_default,
            estado_pago="pagado", metodo=metodo, creado_por=self.actor,
        )
        natural = _cuenta_salida_egreso(metodo, "pagado")
        if natural is not None and natural.pk != cuenta.pk:
            _reubicar(f"tesoreria.egreso:{eg.pk}", natural, cuenta, f"estado de cuenta {cuenta.codigo}")
        self.creados["egresos"][str(eg.pk)] = eg.estado_pago
        p.ref = eg.codigo

    # -- póliza --
    def _poliza(self, p: Paso) -> None:
        from apps.contaduria.services import crear_asiento

        d = p.datos
        asiento = crear_asiento(
            descripcion=f"Póliza {d['poliza']} · {d['concepto']}".strip(" ·")[:300],
            partidas=[x for x in d["partidas"]], fecha=d["fecha"], origen="carga",
            referencia_externa=f"contaduria.carga:{self.carga.pk}:poliza:{lectura.normalizar(str(d['poliza']))}"[:120],
            creado_por=self.actor, idempotente=False,
        )
        self.creados["asientos"].append(asiento.pk)
        p.ref = asiento.codigo

    # -- apertura y cuadre --
    def _diferencias(self, pasos: list[Paso], *, apertura: bool) -> dict:
        """Registra la diferencia entre lo declarado y lo que El Despacho tiene.
        Un asiento por fecha: la apertura tiene una sola; el cuadre puede traer
        varias (la hoja «Saldos hoy» y el último día de cada estado de cuenta)."""
        validos = [p for p in pasos if p.estado != ERROR and p.datos.get("cuenta") is not None]
        if not validos:
            return {}
        contra = self.utilidades if apertura else self._cuenta_ajuste()
        fechas = sorted({p.datos["fecha"] for p in validos})
        resultado = {"fecha": fechas[-1].isoformat(), "fecha_texto": " · ".join(_f(f) for f in fechas),
                     "lineas": [], "contra_codigo": contra.codigo if contra else "",
                     "contra_nombre": contra.nombre if contra else "", "contra": "0.00", "asiento": ""}
        total_contra = CERO
        asientos = []
        for fecha in fechas:
            grupo = [p for p in validos if p.datos["fecha"] == fecha]
            neto, codigo = self._diferencias_de(grupo, fecha, contra, apertura, resultado["lineas"])
            total_contra += neto
            if codigo:
                asientos.append(codigo)
        resultado["contra"] = _d(total_contra)
        resultado["asiento"] = ", ".join(asientos)
        if apertura and total_contra and any(
                p.datos["cuenta"].codigo == E.CODIGO_UTILIDADES_ACUMULADAS for p in validos):
            self.plan.avisos.append(
                f"La apertura no cuadra por {_pesos(abs(total_contra))}: lo que tienes ≠ lo que debes + tu "
                "capital. La diferencia quedó en Utilidades acumuladas; revísala con el contador.")
        return resultado

    def _cuenta_ajuste(self):
        from apps.contaduria.wizards import _obtener_o_crear_cuenta_ajuste

        return _obtener_o_crear_cuenta_ajuste()

    def _diferencias_de(self, grupo, fecha, contra, apertura, lineas) -> tuple[Decimal, str]:
        from apps.contaduria.services import crear_asiento, saldo_cuenta

        # La apertura compara contra lo que había al TERMINAR el día anterior.
        corte = fecha - timedelta(days=1) if apertura else fecha
        partidas = []
        for i, p in enumerate(grupo):
            cuenta, declarado = p.datos["cuenta"], p.datos["saldo"]
            sistema = saldo_cuenta(cuenta, hasta=corte)
            dif = (declarado - sistema).quantize(UN_CENTAVO)
            lineas.append({"codigo": cuenta.codigo, "nombre": cuenta.nombre, "fecha_texto": _f(fecha),
                           "declarado": _d(declarado), "sistema": _d(sistema), "diferencia": _d(dif)})
            p.ref = "cuadra" if dif == 0 else f"{'+' if dif > 0 else '−'}{_pesos(abs(dif))}"
            if dif == 0:
                continue
            # Sube el saldo: cargo si es deudora, abono si es acreedora.
            lado = "cargo" if (cuenta.naturaleza == "deudora") == (dif > 0) else "abono"
            partidas.append({"cuenta": cuenta, lado: abs(dif), "orden": i, "descripcion": "Diferencia"})
        cargos = sum((Decimal(x.get("cargo") or 0) for x in partidas), CERO)
        abonos = sum((Decimal(x.get("abono") or 0) for x in partidas), CERO)
        neto = (cargos - abonos).quantize(UN_CENTAVO)
        if neto > 0:
            partidas.append({"cuenta": contra, "abono": neto, "orden": len(partidas), "descripcion": "Contrapartida"})
        elif neto < 0:
            partidas.append({"cuenta": contra, "cargo": -neto, "orden": len(partidas), "descripcion": "Contrapartida"})
        if len(partidas) < 2:
            return neto, ""  # nada que registrar (o sólo la propia contrapartida)
        sufijo = "apertura" if apertura else f"cuadre:{fecha.isoformat()}"
        # La apertura se fecha al cierre del día anterior al arranque: es el
        # saldo con el que ese día EMPIEZA, y así una segunda carga que compare
        # contra el mismo corte la ve y no la registra otra vez.
        asiento = crear_asiento(
            descripcion=(f"Saldos de arranque al {_f(fecha)}" if apertura
                         else f"Cuadre contra saldos reales al {_f(fecha)}"),
            partidas=partidas, fecha=corte, origen="apertura" if apertura else "ajuste",
            referencia_externa=f"contaduria.carga:{self.carga.pk}:{sufijo}",
            creado_por=self.actor, idempotente=False,
        )
        self.creados["asientos"].append(asiento.pk)
        return neto, asiento.codigo

def _cxc_contra_facturas(cat: _Catalogo) -> dict:
    """¿El libro y las facturas dicen lo mismo de lo que deben los clientes?"""
    from apps.contaduria.services import saldo_cuenta
    from apps.facturacion.models import Factura

    cxc = cat.cuenta_slot.get("cxc")
    libro = saldo_cuenta(cxc) if cxc else CERO
    facturas = sum((f.saldo_pendiente for f in Factura.objects.filter(estado__in=["emitida", "cobrada_parcial"])),
                   CERO)
    return {"libro": _d(libro), "facturas": _d(facturas), "diferencia": _d(libro - facturas)}


def _ejecutar(libro: lectura.Libro, estados, carga, actor) -> tuple[dict, dict, list[str]]:
    from apps.contaduria import reportes

    cat = _Catalogo(carga)
    hoy = date.today()
    antes = _saldos_resumen(cat)
    balance_antes = reportes.balance_general(hasta=hoy)
    plan = _Plan(libro, cat, estados, crear_desde_estados=getattr(carga, "crear_desde_estados", True),
                 ia=getattr(carga, "ia", None)).armar()
    ej = _Ejecucion(plan, carga, actor)
    ej.correr()
    despues = _saldos_resumen(cat)
    balance = reportes.balance_general(hasta=hoy)

    conteos = {}
    for hoja in (E.HOJA_ARRANQUE, E.HOJA_FACTURAS, E.HOJA_INGRESOS, E.HOJA_GASTOS, E.HOJA_POLIZAS,
                 E.HOJA_ESTADOS, E.HOJA_HOY):
        del_hoja = [p for p in plan.pasos if p.hoja == hoja]
        conteos[hoja] = {k: sum(1 for p in del_hoja if p.estado == k) for k in (CREAR, SALTAR, ERROR)}
    saldos = [{"codigo": k, "nombre": v["nombre"], "antes": v["saldo"], "despues": despues.get(k, v)["saldo"]}
              for k, v in antes.items()]
    resultado = {
        "fecha_arranque": plan.F.isoformat() if plan.F else "",
        "fecha_arranque_texto": _f(plan.F),
        "fecha_hoy_texto": _f(plan.H),
        "errores": plan.errores,
        "conteos": conteos,
        "pasos": [p.como_dict() for p in plan.pasos],
        "avisos": plan.avisos,
        "apertura": ej.apertura,
        "cuadre": ej.cuadre,
        "saldos": saldos,
        "cxc": _cxc_contra_facturas(cat),
        "clientes_nuevos": [c["razon_social"] for c in cat.clientes_nuevos.values()],
        "balance": {"activo": _d(balance["total_activo"]), "pasivo": _d(balance["total_pasivo"]),
                    "capital": _d(balance["total_capital"]), "utilidad": _d(balance["utilidad_periodo"]),
                    "descuadre": _d(balance["descuadre"]), "descuadre_antes": _d(balance_antes["descuadre"])},
    }
    claves = [p.clave for p in plan.pasos if p.estado == CREAR and p.clave]
    resultado["ia"] = {"revisados": sum(1 for p in plan.pasos if p.clave in plan.ia),
                       "sin_revisar": len(plan.pendientes_ia)}
    # Para preguntarle a El Chalán fuera de la transacción (ver `_preguntar_ia`).
    resultado["_pendientes_ia"] = plan.pendientes_ia
    resultado["_catalogo_ia"] = plan.catalogo_ia() if plan.pendientes_ia else {}
    return resultado, ej.creados, claves


# ── API ──────────────────────────────────────────────────────────────────

def _leer(carga) -> tuple[lectura.Libro, list]:
    """La plantilla (si la hay) y los estados de cuenta de una carga."""
    from . import estado_cuenta

    libro = lectura.leer(bytes(carga.archivo)) if carga.archivo else lectura.Libro()
    estados = [(e.nombre, e.cuenta, estado_cuenta.leer(bytes(e.contenido), e.nombre))
               for e in carga.estados_cuenta.select_related("cuenta")]
    return libro, estados


def nueva(*, plantilla: bytes | None = None, nombre_plantilla: str = "", estados=(),
          crear_desde_estados: bool = True, actor):
    """Registra lo subido como carga en borrador y le calcula su vista previa.

    `estados`: [{"contenido": bytes, "nombre": str, "cuenta": CuentaContable}].
    Lanza `PlantillaInvalida` si la plantilla no se puede leer, antes de guardar nada.
    """
    from apps.contaduria.models import CargaContable, EstadoCuentaCarga

    estados = [e for e in estados if e.get("contenido")]
    if not plantilla and not estados:
        raise lectura.PlantillaInvalida("Sube la plantilla llena, uno o varios estados de cuenta, o las dos cosas.")
    libro = lectura.leer(plantilla) if plantilla else lectura.Libro()
    with transaction.atomic():
        carga = CargaContable.objects.create(
            nombre_archivo=(nombre_plantilla or "")[:200], archivo=plantilla or None,
            sha256=hashlib.sha256(plantilla).hexdigest() if plantilla else "",
            fecha_arranque=libro.arranque.fecha, crear_desde_estados=crear_desde_estados,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        for i, e in enumerate(estados):
            EstadoCuentaCarga.objects.create(
                carga=carga, cuenta=e["cuenta"], nombre=(e.get("nombre") or f"estado-{i + 1}")[:200],
                contenido=e["contenido"], sha256=hashlib.sha256(e["contenido"]).hexdigest(), orden=i,
            )
    carga.resumen = previsualizar(carga, actor, preguntar_ia=True)
    carga.save(update_fields=["resumen", "ia"])
    return carga


def _correr_y_deshacer(libro, estados, carga, actor) -> dict:
    try:
        with carga_masiva(), transaction.atomic():
            resultado, _, _ = _ejecutar(libro, estados, carga, actor)
            raise _Deshacer(resultado)
    except _Deshacer as salida:
        return salida.resultado


def previsualizar(carga, actor, *, preguntar_ia: bool = False) -> dict:
    """Corre la carga completa y la deshace. Devuelve lo que PASARÍA.

    Con `preguntar_ia`, lo que haga falta clasificar se le pregunta a El Chalán
    (FUERA de la transacción: una llamada de red no debe tener la base
    bloqueada) y se corre otra vez con sus respuestas. Las respuestas quedan en
    `carga.ia` (quien llama guarda la carga)."""
    libro, estados = _leer(carga)
    resultado = _correr_y_deshacer(libro, estados, carga, actor)
    aviso_ia = ""
    if preguntar_ia and resultado["_pendientes_ia"]:
        nuevas, aviso_ia = ia_mod.revisar(resultado["_pendientes_ia"], resultado["_catalogo_ia"], actor)
        if nuevas:
            carga.ia = {**(carga.ia or {}), **nuevas}
            resultado = _correr_y_deshacer(libro, estados, carga, actor)
    if aviso_ia:
        resultado["avisos"].append(aviso_ia)
    elif resultado["_pendientes_ia"]:
        resultado["avisos"].append(
            f"{len(resultado['_pendientes_ia'])} renglón(es) sin revisar por El Chalán: van con las reglas de "
            "siempre. «Recalcular» le vuelve a preguntar.")
    return _limpio(resultado, "vista_previa")


def _limpio(resultado: dict, modo: str) -> dict:
    resultado.pop("_pendientes_ia", None)
    resultado.pop("_catalogo_ia", None)
    resultado["modo"] = modo
    return resultado


def aplicar(carga, actor) -> dict:
    """La carga de verdad. Todo o nada: con un error, no se guarda nada."""
    from apps.contaduria.models import CargaContable

    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz

    with carga_masiva(), transaction.atomic():
        carga = CargaContable.objects.select_for_update().get(pk=carga.pk)
        if carga.estado != "borrador":
            raise ValueError("Esta carga ya no está en vista previa.")
        libro, estados = _leer(carga)
        resultado, creados, claves = _ejecutar(libro, estados, carga, actor)
        if resultado["errores"]:
            raise CargaConErrores(_limpio(resultado, "vista_previa"))
        _limpio(resultado, "aplicada")
        carga.estado = "aplicada"
        carga.resumen = resultado
        carga.creados = creados
        carga.claves = claves
        carga.fecha_arranque = libro.arranque.fecha
        carga.aplicada_en = timezone.now()
        carga.aplicada_por = actor if getattr(actor, "is_authenticated", False) else None
        carga.save()
    with contextlib.suppress(Exception):  # el aviso nunca tumba lo ya guardado
        emitir(EventoPortavoz(
            tipo="contaduria.carga_aplicada", actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", None),
            payload={"carga_id": carga.pk, "conteos": resultado["conteos"],
                     "fecha_arranque": resultado["fecha_arranque"]},
        ))
    return resultado


def deshacer(carga, actor, motivo: str) -> None:
    """Anula todo lo que creó una carga aplicada. No crea asientos de reverso:
    los asientos de la carga quedan anulados (visibles, fuera de los saldos),
    igual que los ingresos, gastos y facturas."""
    from apps.contaduria.models import Asiento, CargaContable
    from apps.facturacion.models import Factura
    from apps.tesoreria.models import Egreso, Ingreso

    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz

    motivo = (motivo or "").strip()
    if not motivo:
        raise CargaNoDeshacible(["Escribe por qué se deshace."])
    ahora = timezone.now()
    actor_ok = actor if getattr(actor, "is_authenticated", False) else None
    with transaction.atomic():
        carga = CargaContable.objects.select_for_update().get(pk=carga.pk)
        if carga.estado != "aplicada":
            raise CargaNoDeshacible(["Sólo se deshace una carga aplicada."])
        cr = carga.creados or {}
        ingresos = [int(x) for x in cr.get("ingresos", [])]
        egresos = {int(k): v for k, v in (cr.get("egresos") or {}).items()}
        facturas = [int(x) for x in cr.get("facturas", [])]
        tocadas = [int(x) for x in cr.get("facturas_tocadas", [])]

        motivos = []
        ajenos = Ingreso.vigentes.filter(factura_id__in=facturas).exclude(pk__in=ingresos)
        for ing in ajenos.select_related("factura")[:10]:
            motivos.append(f"{ing.factura.folio_display} ya tiene un cobro registrado después ({ing.codigo}).")
        for eg in Egreso.objects.filter(pk__in=list(egresos)):
            if not eg.anulado and eg.estado_pago != egresos[eg.pk]:
                motivos.append(f"{eg.codigo} cambió de estado después de la carga ({eg.get_estado_pago_display()}).")
        if motivos:
            raise CargaNoDeshacible(motivos)

        texto = f"Deshecha la carga contable #{carga.pk}: {motivo}"[:300]
        refs = []
        for pk in ingresos:
            refs += [f"tesoreria.ingreso:{pk}", f"tesoreria.ingreso.anulacion:{pk}"]
        for pk in egresos:
            refs += [f"tesoreria.egreso:{pk}", f"tesoreria.egreso.anulacion:{pk}"]
        for pk in facturas:
            refs += [f"facturacion.factura:{pk}", f"facturacion.factura.cancelacion:{pk}"]
        (Asiento.vigentes.filter(Q(pk__in=cr.get("asientos", [])) | Q(referencia_externa__in=refs))
         .update(anulado=True, anulado_en=ahora, anulado_por=actor_ok, motivo_anulacion=texto))
        Ingreso.objects.filter(pk__in=ingresos, anulado=False).update(
            anulado=True, anulado_en=ahora, anulado_por=actor_ok, motivo_anulacion=texto)
        Egreso.objects.filter(pk__in=list(egresos), anulado=False).update(
            anulado=True, anulado_en=ahora, anulado_por=actor_ok, motivo_anulacion=texto)
        # El folio se libera: volver a cargar la misma factura no debe chocar
        # con su fantasma cancelado.
        for fac in Factura.objects.filter(pk__in=facturas):
            nota = f"{fac.notas}\n{texto}" + (f" (folio F{fac.folio_numero})" if fac.folio_numero else "")
            Factura.objects.filter(pk=fac.pk).update(
                estado="cancelada", cancelada_en=ahora, cancelada_por=actor_ok, motivo_cancelacion=texto,
                folio_numero=None, monto_cobrado=CERO, notas=nota.strip())
        for fac in Factura.objects.filter(pk__in=tocadas).exclude(estado="cancelada"):
            with carga_masiva():
                _estado_por_cobro(fac)

        carga.estado = "deshecha"
        carga.deshecha_en = ahora
        carga.deshecha_por = actor_ok
        carga.motivo_deshacer = motivo[:300]
        carga.claves = []
        carga.save(update_fields=["estado", "deshecha_en", "deshecha_por", "motivo_deshacer", "claves"])
    with contextlib.suppress(Exception):
        emitir(EventoPortavoz(tipo="contaduria.carga_deshecha", actor_id=getattr(actor, "id", None),
                              actor_email=getattr(actor, "email", None),
                              payload={"carga_id": carga.pk, "motivo": motivo[:200]}))
