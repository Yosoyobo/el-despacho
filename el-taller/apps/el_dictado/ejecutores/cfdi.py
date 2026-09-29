"""Ejecutores de los CFDI recibidos por correo (S-Pendientes-Sep28).

El Chalán ya podía VER los comprobantes pendientes (`cfdi_pendientes`); con
estos los puede RESOLVER, siempre tras la confirmación de una persona — el
preview/confirm de `services.aplicar` (regla §20). Nada se aplica solo.

Mismo contrato que `avanzados.py`: `(accion, usuario, contexto)`, lanza
`ValueError` con un mensaje en español si el payload no alcanza, la entidad no
existe o el usuario no tiene permiso (defensa en profundidad: el catálogo ya
filtra por permiso lo que se le ofrece al Chalán, aquí se re-chequea).

La lógica NO vive aquí: vive en `apps.facturacion.cfdi_recibidos`, que usan
también la pantalla de Tesorería y el modal de «Nuevo egreso». Así las tres
superficies aplican las mismas reglas — en particular la que evita contar un
gasto dos veces: si ya hay un egreso que casa con el comprobante, no se crea
otro a menos que se pida explícitamente.
"""

from __future__ import annotations

from . import _gate, registrar
from .avanzados import _egreso_por_codigo, _exigir, _factura_por_codigo, _fecha
from .basicos import _limpiar_slug, _ref_anterior, _resolver_proyecto, _resolver_usuario


def _cfdi(payload: dict):
    """El comprobante pedido: por folio fiscal (o su principio), serie-folio
    o id. Tiene que ser UNO."""
    from apps.facturacion import cfdi_recibidos

    ref = str(payload.get("cfdi") or payload.get("uuid") or "").strip()
    _exigir(bool(ref), "Falta `cfdi`: el folio fiscal (UUID) o la serie-folio del comprobante.")
    c = cfdi_recibidos.buscar(ref)
    _exigir(c is not None,
            f"No encontré un CFDI recibido con «{ref}». Consulta `cfdi_pendientes` "
            "para ver los que esperan dueño.")
    return c


def _proveedor(valor, contexto):
    """Proveedor por `@accion_N` (uno recién creado en el mismo dictado) o por
    nombre — sólo si el nombre apunta a UNO."""
    from apps.el_catalogo.models import Proveedor

    texto = _limpiar_slug(str(valor or "").strip())
    if not texto:
        return None
    pk = _ref_anterior(texto, contexto, "proveedor")
    if pk:
        return Proveedor.objects.filter(pk=pk).first()
    exacto = list(Proveedor.objects.filter(razon_social__iexact=texto, activo=True)[:2])
    if len(exacto) == 1:
        return exacto[0]
    from lib.nombres import normalizar

    buscado = normalizar(texto)
    iguales = [p for p in Proveedor.objects.filter(activo=True).only("pk", "razon_social")
               if normalizar(p.razon_social) == buscado]
    if len(iguales) == 1:
        return iguales[0]
    parecidos = list(Proveedor.objects.filter(razon_social__icontains=texto, activo=True)[:2])
    _exigir(len(parecidos) == 1,
            f"No hay un proveedor inequívoco «{texto}»"
            + (" (hay más de uno parecido)." if parecidos else "."))
    return parecidos[0]


@registrar("registrar_egreso_desde_cfdi")
def registrar_egreso_desde_cfdi(accion, usuario, contexto=None):
    """Registra el egreso de un CFDI de proveedor, o lo liga a uno existente.

    Payload: cfdi (folio fiscal o serie-folio), egreso_codigo? (liga a un
    egreso que ya existe en vez de crear otro), crear_nuevo? (true para crear
    aunque haya uno que casa), proveedor? (nombre o @accion_N, si su RFC no
    está en el catálogo), centro_de_costo_slug?, metodo?, estado_pago?,
    proyecto_slug?, pagado_por_slug?, descripcion?, fecha?.

    El monto es el TOTAL del comprobante, con IVA (como toda captura de
    egreso), y el proveedor es obligatorio (S-LC-julio).
    """
    _gate(usuario, "puede_ver_finanzas", "registrar egresos")
    # Y el permiso granular que pide la pantalla (§4 #20): a quien le quitaron
    # «capturar egresos» no se le abre por la puerta del Chalán.
    from apps.tesoreria.views_cfdi import puede_resolver_egresos

    _exigir(puede_resolver_egresos(usuario), "No tienes permiso para registrar egresos.")
    from apps.facturacion import cfdi_recibidos
    from apps.tesoreria.models import CentroDeCosto

    payload = accion.payload or {}
    c = _cfdi(payload)
    tipo = cfdi_recibidos.clasificar(c)
    _exigir(tipo != cfdi_recibidos.TIPO_PROPIO,
            f"El CFDI {c.referencia or c.uuid[:8]} es una factura NUESTRA, no un gasto: "
            "se liga a su factura con `ligar_cfdi_a_factura`.")

    try:
        codigo = str(payload.get("egreso_codigo") or "").strip()
        if codigo:
            egreso = _egreso_por_codigo(codigo)
            cfdi_recibidos.ligar_egreso(c, egreso, usuario)
            accion.entidad_tipo = "egreso"
            accion.entidad_id = egreso.pk
            return

        proveedor = _proveedor(payload.get("proveedor"), contexto) if payload.get("proveedor") else None
        proveedor = proveedor or cfdi_recibidos.proveedor_sugerido(c)
        _exigir(proveedor is not None,
                f"No sé qué proveedor es «{c.emisor_nombre or c.emisor_rfc}»: pásame `proveedor` "
                "(o créalo antes con `crear_proveedor` y usa @accion_N).")

        casan = cfdi_recibidos.egresos_que_casan(c, proveedor)
        if casan and not payload.get("crear_nuevo"):
            codigos = ", ".join(e.codigo for e in casan[:5])
            raise ValueError(
                f"Ya hay egresos que casan con este CFDI ({codigos}). Para no contar el "
                "gasto dos veces, propón ligarlo con `egreso_codigo`; si de verdad es "
                "otro gasto, manda `crear_nuevo: true`.")

        centro = None
        slug_centro = str(payload.get("centro_de_costo_slug") or "").strip().lower()
        if slug_centro:
            centro = CentroDeCosto.objects.filter(slug=slug_centro, activo=True).first()
            _exigir(centro is not None, f"Centro de costo `{slug_centro}` no encontrado.")

        proyecto = None
        if payload.get("proyecto_slug"):
            proyecto = _resolver_proyecto(str(payload["proyecto_slug"]), contexto)
        pagado_por = None
        if payload.get("pagado_por_slug"):
            pagado_por = _resolver_usuario(str(payload["pagado_por_slug"]).lower(), contexto)

        fecha = _fecha(payload) if payload.get("fecha") else None
        from lib.sanear import sanear_contexto

        descripcion = sanear_contexto(str(payload.get("descripcion") or "").strip())[:300]

        egreso = cfdi_recibidos.crear_egreso(
            c, actor=usuario, centro_de_costo=centro,
            metodo=str(payload.get("metodo") or ""),
            estado_pago=str(payload.get("estado_pago") or ""),
            proyecto=proyecto, proveedor=proveedor, descripcion=descripcion,
            fecha=fecha, pagado_por=pagado_por,
        )
    except cfdi_recibidos.CfdiNoResoluble as exc:
        raise ValueError(str(exc)) from exc

    if egreso.estado_pago == "por_reembolsar":
        from apps.tesoreria.push_handlers import notificar_reembolso_pendiente

        notificar_reembolso_pendiente(egreso, usuario)
    accion.entidad_tipo = "egreso"
    accion.entidad_id = egreso.pk


@registrar("ligar_cfdi_a_factura")
def ligar_cfdi_a_factura(accion, usuario, contexto=None):
    """Liga un CFDI nuestro (que no se pudo ligar solo) a su factura.

    Payload: cfdi (folio fiscal o serie-folio), factura_codigo (FAC-… o el
    folio F-…). El XML y el folio fiscal quedan guardados en la factura.
    """
    _gate(usuario, "puede_editar_facturacion", "ligar comprobantes a facturas")
    from apps.facturacion import cfdi_recibidos

    payload = accion.payload or {}
    c = _cfdi(payload)
    _exigir(cfdi_recibidos.clasificar(c) != cfdi_recibidos.TIPO_PROVEEDOR,
            "Ese CFDI es la factura de un PROVEEDOR (un gasto): se registra con "
            "`registrar_egreso_desde_cfdi`.")
    factura = _factura_por_codigo_o_folio(payload.get("factura_codigo") or payload.get("factura"))
    try:
        cfdi_recibidos.ligar_factura(c, factura, usuario)
    except cfdi_recibidos.CfdiNoResoluble as exc:
        raise ValueError(str(exc)) from exc
    accion.entidad_tipo = "factura"
    accion.entidad_id = factura.pk


def _factura_por_codigo_o_folio(valor):
    """Una factura por su código interno (FAC-…) o por su folio (F-106, F106)."""
    import re

    from apps.facturacion.models import Factura

    texto = str(valor or "").strip()
    _exigir(bool(texto), "Falta `factura_codigo` (FAC-… o el folio F-…).")
    m = re.fullmatch(r"[Ff]\s*-?\s*(\d+)", texto)
    if m:
        fac = Factura.objects.filter(folio_numero=int(m.group(1))).first()
        _exigir(fac is not None, f"No encontré la factura con folio {texto}.")
        return fac
    return _factura_por_codigo(texto)


__all__ = ["ligar_cfdi_a_factura", "registrar_egreso_desde_cfdi"]
