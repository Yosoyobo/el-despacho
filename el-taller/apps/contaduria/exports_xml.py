"""Export fiscal XML — estilo SAT Anexo 24 (Contabilidad Electrónica).

Genera tres XML para que el contador externo los importe/refine: Catálogo
de cuentas, Balanza de comprobación y Pólizas del periodo. El Despacho NO
emite CFDI ni timbra (regla §16); estos XML son un **borrador** — el RFC
y el código agrupador SAT por cuenta deben verificarse antes de presentar
al SAT.

Decisiones pragmáticas (V1):
- RFC desde La Bóveda (slot `rfc_empresa`); si falta, usa el genérico
  `XAXX010101000` y se marca el borrador.
- Mes/Año se toman de la fecha `hasta`.
- Importes a 2 decimales; escapado seguro con saxutils.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from xml.sax.saxutils import escape, quoteattr

from django.db.models import Sum
from django.http import HttpResponse

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from . import services
from .models import Asiento, CuentaContable, Partida

FORMATOS_XML = ("xml_catalogo", "xml_balanza", "xml_polizas")
CERO = Decimal("0.00")
RFC_GENERICO = "XAXX010101000"

_NS = {
    "catalogo": "http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/CatalogoCuentas",
    "balanza": "http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/BalanzaComprobacion",
    "polizas": "http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/PolizasPeriodo",
}


def _rfc() -> str:
    try:
        from ajustes.models.credencial import Credencial
        return (Credencial.obtener("rfc_empresa") or "").strip() or RFC_GENERICO
    except Exception:  # noqa: BLE001
        return RFC_GENERICO


def _m(v) -> str:
    if v is None:
        return "0.00"
    return f"{Decimal(str(v)):.2f}"


def _natur(cuenta) -> str:
    return "D" if cuenta.naturaleza == "deudora" else "A"


def _nivel(codigo: str) -> int:
    return (codigo or "").count(".") + 1


def xml_catalogo(params: dict) -> str:
    hasta = params.get("_hasta") or date.today()
    rfc = _rfc()
    cuentas = CuentaContable.objects.all().order_by("codigo")
    if params.get("incluir_inactivas") not in ("1", "true", "on"):
        cuentas = cuentas.filter(activa=True)
    filas = []
    for c in cuentas:
        filas.append(
            f'  <catalogocuentas:Ctas CodAgrup={quoteattr(c.codigo_agrupador_sat or "")} '
            f'NumCta={quoteattr(c.codigo)} Desc={quoteattr(c.nombre)} '
            f'Nivel="{_nivel(c.codigo)}" Natur="{_natur(c)}"/>'
        )
    cuerpo = "\n".join(filas)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- BORRADOR — verificar RFC y código agrupador SAT antes de presentar -->\n"
        f'<catalogocuentas:Catalogo xmlns:catalogocuentas={quoteattr(_NS["catalogo"])} '
        f'Version="1.3" RFC={quoteattr(rfc)} Mes="{hasta.month:02d}" Anio="{hasta.year}">\n'
        f"{cuerpo}\n"
        "</catalogocuentas:Catalogo>\n"
    )


def xml_balanza(params: dict) -> str:
    desde = params.get("_desde")
    hasta = params.get("_hasta") or date.today()
    if desde is None:
        desde = hasta.replace(day=1)
    rfc = _rfc()
    dia_previo = desde - timedelta(days=1)

    filas = []
    cuentas = CuentaContable.objects.all().order_by("codigo")
    for c in cuentas:
        mov = (
            Partida.objects.filter(
                cuenta=c, asiento__anulado=False,
                asiento__fecha__gte=desde, asiento__fecha__lte=hasta,
            ).aggregate(d=Sum("cargo"), h=Sum("abono"))
        )
        debe = mov["d"] or CERO
        haber = mov["h"] or CERO
        saldo_ini = services.saldo_cuenta(c, hasta=dia_previo)
        saldo_fin = services.saldo_cuenta(c, hasta=hasta)
        if debe == CERO and haber == CERO and saldo_ini == CERO and saldo_fin == CERO:
            continue
        filas.append(
            f'  <BCE:Ctas NumCta={quoteattr(c.codigo)} SaldoIni="{_m(saldo_ini)}" '
            f'Debe="{_m(debe)}" Haber="{_m(haber)}" SaldoFin="{_m(saldo_fin)}"/>'
        )
    cuerpo = "\n".join(filas)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- BORRADOR — saldos del libro interno; verificar antes de presentar al SAT -->\n"
        f'<BCE:Balanza xmlns:BCE={quoteattr(_NS["balanza"])} '
        f'Version="1.3" RFC={quoteattr(rfc)} Mes="{hasta.month:02d}" Anio="{hasta.year}" '
        f'TipoEnvio="N">\n'
        f"{cuerpo}\n"
        "</BCE:Balanza>\n"
    )


def xml_polizas(params: dict) -> str:
    desde = params.get("_desde")
    hasta = params.get("_hasta") or date.today()
    if desde is None:
        desde = hasta.replace(day=1)
    rfc = _rfc()

    qs = Asiento.vigentes.filter(fecha__gte=desde, fecha__lte=hasta).prefetch_related(
        "partidas", "partidas__cuenta"
    ).order_by("fecha", "creado_en", "pk")

    bloques = []
    for a in qs:
        trans = []
        for p in a.partidas.all():
            trans.append(
                f'    <PLZ:Transaccion NumCta={quoteattr(p.cuenta.codigo)} '
                f'DesCta={quoteattr(p.cuenta.nombre)} '
                f'Concepto={quoteattr(p.descripcion or a.descripcion)} '
                f'Debe="{_m(p.cargo)}" Haber="{_m(p.abono)}"/>'
            )
        bloques.append(
            f'  <PLZ:Poliza NumUnIdenPol={quoteattr(a.codigo)} '
            f'Fecha="{a.fecha.isoformat()}" Concepto={quoteattr(a.descripcion)}>\n'
            + "\n".join(trans)
            + "\n  </PLZ:Poliza>"
        )
    cuerpo = "\n".join(bloques)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- BORRADOR — pólizas del libro interno; el contador refina antes del SAT -->\n"
        f'<PLZ:Polizas xmlns:PLZ={quoteattr(_NS["polizas"])} '
        f'Version="1.3" RFC={quoteattr(rfc)} Mes="{hasta.month:02d}" Anio="{hasta.year}" '
        f'TipoSolicitud="AF">\n'
        f"{cuerpo}\n"
        "</PLZ:Polizas>\n"
    )


_GENERADORES = {
    "xml_catalogo": xml_catalogo,
    "xml_balanza": xml_balanza,
    "xml_polizas": xml_polizas,
}


def responder_xml(formato: str, params: dict, *, actor=None) -> HttpResponse:
    gen = _GENERADORES.get(formato)
    if gen is None:
        raise ValueError(f"Formato XML desconocido: {formato}")
    contenido = gen(params)
    nombre = f"contaduria_{formato}_{date.today().isoformat()}.xml"
    resp = HttpResponse(contenido, content_type="application/xml; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{nombre}"'
    emitir(EventoPortavoz(
        tipo="contaduria.exportado_xml",
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={
            "formato": formato,
            "desde": params["_desde"].isoformat() if params.get("_desde") else "",
            "hasta": params["_hasta"].isoformat() if params.get("_hasta") else "",
        },
    ))
    return resp


# Nota: `escape` se reexporta por si algún caller lo necesita para texto libre.
__all__ = ["FORMATOS_XML", "responder_xml", "xml_catalogo", "xml_balanza",
           "xml_polizas", "escape"]
