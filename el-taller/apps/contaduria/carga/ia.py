"""El Chalán revisa lo que se sube a la carga contable (estación `carga_contable`).

Decisión de Oscar: «usa el AI que tiene el taller para ayudar a procesar lo que
se está subiendo, para evitar que lo hardcodeado haga algo loco». Lo que una
regla fija no puede saber —si un retiro del banco es un gasto, un traspaso a
caja o el pago del IVA; qué cliente está detrás de un depósito; a qué factura
corresponde un cobro que podría ser de dos— se le pregunta a El Chalán.

Tres candados, para que la IA tampoco haga algo loco:

1. **Sólo propone.** Sus respuestas se enseñan en la vista previa, marcadas y con
   su confianza; nada se guarda hasta que una persona aplica.
2. **Se valida contra el catálogo.** El Chalán contesta con nombres y folios de
   las listas que se le dan; `motor` los resuelve contra la base y lo que no
   exista se descarta (nunca se confía en un id o nombre crudo del modelo).
3. **Una sola respuesta.** Se pregunta al subir (o al recalcular) y se guarda en
   `CargaContable.ia`; la vista previa y la aplicación leen lo guardado.

Si El Chalán no está configurado o no contesta, la carga sigue con las reglas de
siempre y lo avisa. Nunca lanza.
"""

from __future__ import annotations

import json
import logging
import re

log = logging.getLogger("despacho.contaduria.carga")

ESTACION = "carga_contable"
POR_LLAMADA = 40
MAX_LLAMADAS = 12          # 480 renglones; lo demás sigue con las reglas y se avisa
UMBRAL_CONFIANZA = 0.6

TIPOS = {"cobro", "ingreso", "gasto", "comision", "traspaso", "impuesto", "prestamo", "aportacion", "otro"}


def _parsear(texto: str) -> dict | None:
    if not texto:
        return None
    limpio = re.sub(r"^```(?:json)?", "", texto.strip()).strip()
    limpio = re.sub(r"```$", "", limpio).strip()
    m = re.search(r"\{.*\}", limpio, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _llamar(prompt: str, usuario) -> str:
    """El único punto que toca a Los Analistas (las pruebas lo sustituyen)."""
    from lib.analistas import analizar

    res = analizar(estacion=ESTACION, prompt=prompt, max_tokens=3500, temperatura=0.0,
                   actor_id=getattr(usuario, "pk", None))
    return res.texto


def _contexto(catalogo: dict) -> str:
    def lista(titulo, valores, maximo=150):
        valores = list(valores)[:maximo]
        return f"{titulo}:\n" + ("\n".join(f"- {v}" for v in valores) if valores else "- (ninguno)")

    return "\n\n".join([
        lista("CLIENTES", catalogo["clientes"], 200),
        lista("PROVEEDORES", catalogo["proveedores"], 200),
        lista("CENTROS DE COSTO (slug: nombre)", catalogo["centros"]),
        lista("FACTURAS POR COBRAR (folio · cliente · saldo · fecha)", catalogo["facturas"], 150),
        lista("CUENTAS CONTABLES para traspasos, impuestos, préstamos y aportaciones (código · nombre)",
              catalogo["cuentas"]),
    ])


_SISTEMA = (
    "Eres El Chalán contable de Learning Center, un despacho mexicano de diseño y maquila. "
    "Se está cargando la contabilidad que se llevó fuera del sistema. Te doy movimientos (de "
    "estados de cuenta del banco o de una plantilla) y catálogos. Para CADA movimiento di qué es.\n"
    "Tipos: cobro (depósito que paga una factura de la lista), ingreso (depósito de un cliente sin "
    "factura, o venta), gasto (compra o pago a proveedor), comision (comisión o cargo del banco), "
    "traspaso (dinero que pasa a otra cuenta propia: caja, otro banco, Stripe), impuesto (pago al "
    "SAT: IVA, ISR), prestamo, aportacion (de los socios), otro.\n"
    "Reglas: usa EXACTAMENTE los nombres, folios, slugs y códigos de las listas; si no aplica o no "
    "estás seguro, pon null. Un depósito sólo es 'cobro' si su monto cabe en el saldo de la "
    "factura. Si el movimiento trae 'candidatas', elige la factura SÓLO entre ellas. Si el "
    "movimiento trae 'solo_centro', sólo sugiere centro y proveedor. No inventes.\n"
    "Responde SOLO JSON estricto, sin texto fuera:\n"
    '{"movimientos": [{"id": <id>, "tipo": "<tipo>", "cliente": "<nombre>"|null, '
    '"factura": "<folio>"|null, "proveedor": "<nombre>"|null, "centro": "<slug>"|null, '
    '"cuenta": "<código>"|null, "concepto": "<descripción corta en español>", '
    '"confianza": 0.0-1.0}]}'
)


def revisar(pendientes: list[dict], catalogo: dict, usuario) -> tuple[dict, str]:
    """Pregunta a El Chalán por los `pendientes` (cada uno trae su `clave`).
    Devuelve `({clave: sugerencia}, aviso)`; el aviso es "" si todo salió bien."""
    if not pendientes:
        return {}, ""
    try:
        from chalanes.voz import preludio, reglas
        from lib.sanear import sanear_contexto

        voz, reglas_extra = preludio(ESTACION), reglas()
    except Exception:  # noqa: BLE001
        from lib.sanear import sanear_contexto

        voz, reglas_extra = "", ""
    contexto = _contexto(catalogo)
    sugerencias: dict[str, dict] = {}
    fallas = 0
    lotes = [pendientes[i:i + POR_LLAMADA] for i in range(0, len(pendientes), POR_LLAMADA)]
    for lote in lotes[:MAX_LLAMADAS]:
        por_id = {i: p for i, p in enumerate(lote, start=1)}
        movimientos = [{"id": i, **{k: v for k, v in p.items() if k != "clave"}} for i, p in por_id.items()]
        usuario_txt = (f"{contexto}\n\nMOVIMIENTOS:\n"
                       + json.dumps(movimientos, ensure_ascii=False, default=str))
        prompt = voz + _SISTEMA + reglas_extra + "\n\n" + sanear_contexto(usuario_txt, max_len=60000)
        try:
            crudo = _parsear(_llamar(prompt, usuario))
        except Exception as exc:  # noqa: BLE001 — la IA nunca tumba la carga
            log.warning("carga_contable: El Chalán no respondió: %s", str(exc)[:200])
            fallas += 1
            continue
        if not crudo or not isinstance(crudo.get("movimientos"), list):
            fallas += 1
            continue
        for s in crudo["movimientos"]:
            if not isinstance(s, dict):
                continue
            try:
                p = por_id.get(int(s.get("id")))
            except (TypeError, ValueError):
                continue
            if p is None:
                continue
            tipo = str(s.get("tipo") or "").strip().lower()
            try:
                confianza = max(0.0, min(1.0, float(s.get("confianza") or 0)))
            except (TypeError, ValueError):
                confianza = 0.0
            sugerencias[p["clave"]] = {
                "tipo": tipo if tipo in TIPOS else "otro",
                **{k: (str(s[k]).strip()[:200] if s.get(k) not in (None, "") else None)
                   for k in ("cliente", "factura", "proveedor", "centro", "cuenta", "concepto")},
                "confianza": round(confianza, 2),
            }
    avisos = []
    if fallas:
        avisos.append(f"El Chalán no pudo revisar {fallas} de {min(len(lotes), MAX_LLAMADAS)} tanda(s): esos "
                      "renglones siguen con las reglas de siempre. Puedes «Recalcular» más tarde.")
    if len(lotes) > MAX_LLAMADAS:
        avisos.append(f"Son muchos renglones: El Chalán revisó {MAX_LLAMADAS * POR_LLAMADA}; los demás van "
                      "con las reglas de siempre.")
    return sugerencias, " ".join(avisos)
