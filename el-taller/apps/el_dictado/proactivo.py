"""El Chalán proactivo (Fase 3) — propone, nunca actúa.

Los *scouts* (commands de cron) detectan condiciones de negocio dignas de
atención (facturas vencidas, proyectos estancados, mandados sin avance, …),
reúnen los HECHOS desde la DB, y le piden a El Chalán que (a) los redacte en una
sugerencia humana y (b) opcionalmente proponga acciones concretas. El resultado
se persiste como `PropuestaChalan` y, si hay escrituras, como un
`Dictado(origen='chalan_proactivo')` PENDIENTE que el usuario confirma en el
preview estándar — NUNCA se aplica solo.

Decisiones del sprint:
- **Costo al destinatario**: la llamada IA se atribuye con `actor_id=destinatario`
  (cuenta contra su presupuesto). Si su política es `topar` y ya rebasó, el gate
  de `lib.analistas` levanta `PresupuestoIAExcedido` y la propuesta simplemente
  no se genera esa corrida (degrada graciosamente).
- **Una sola llamada IA por propuesta** (no loop de herramientas): el scout ya
  trae los hechos, así que El Chalán solo los redacta + propone. Más barato y
  determinista. El loop con herramientas read-only queda como mejora futura.
- **Idempotencia**: `(usuario, clave_dedup)` único — re-correr el scout no
  duplica. Ej. `clave_dedup='factura_vencida:123'`.
"""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)

CATEGORIA_PUSH = "chalan_sugerencia"
ESTACION = "dictado"  # reusa el Cuadro de Chalanes de El Dictado (propone acciones)

_SYSTEM = """\
Eres El Chalán de El Despacho (Learning Center, diseño/maquila B2B). Estás
redactando una SUGERENCIA PROACTIVA para un miembro del equipo: detectaste algo
que conviene que revise. Tú solo PROPONES; el usuario decide y confirma. Nunca
afirmes que ya hiciste algo.

Te paso los HECHOS ya verificados (no inventes cifras ni estatus: usa solo lo
dado). Devuelve SIEMPRE un ÚNICO objeto JSON, sin texto fuera del JSON:

{ "texto": "<mensaje breve y accionable para el usuario, en español>",
  "acciones": [ { "tipo": "<tipo permitido>", "descripcion": "<corta>", "payload": { ... }, "confianza": 0.0-1.0 } ] }

- `texto`: 1-3 frases. Claro, directo, sin markdown pesado. Si solo informas,
  deja `acciones` vacío.
- `acciones`: SOLO si propones un cambio concreto y útil. Cada acción DEBE usar
  un `tipo` de la lista permitida; si no hay un tipo adecuado, no propongas
  acciones (deja la lista vacía). El usuario las revisa una por una.
"""


def _seccion_acciones(usuario) -> str:
    from lib.dictado_catalogo import COMANDOS_PROHIBIDOS, comandos_para
    lineas = ["TIPOS DE ACCIÓN PERMITIDOS:"]
    for c in comandos_para(usuario):
        lineas.append(f"- {c['tipo']}: payload = {c['payload']}")
    prohibidos = ", ".join(c["tipo"] for c in COMANDOS_PROHIBIDOS)
    lineas.append(f"PROHIBIDOS (nunca los emitas): {prohibidos}")
    return "\n".join(lineas)


def _redactar(destinatario, *, titulo: str, hechos: str, permitir_acciones: bool) -> dict:
    """Una llamada a El Chalán → `{ok, texto, acciones, provider}`. Nunca lanza."""
    from chalanes.voz import preludio, reglas
    from lib.sanear import sanear_contexto

    from .services import _parsear_json

    partes = [preludio(ESTACION, destinatario), _SYSTEM]
    if permitir_acciones:
        partes.append(_seccion_acciones(destinatario))
    else:
        partes.append("NO propongas acciones en esta sugerencia (deja `acciones` vacío).")
    partes.append(reglas())
    partes.append(f"\n[ASUNTO]\n{titulo}\n\n[HECHOS]\n{sanear_contexto(hechos, max_len=4000)}")
    prompt = "\n\n".join(p for p in partes if p)

    try:
        from lib.analistas import PresupuestoIAExcedido, analizar
        try:
            res = analizar(
                estacion=ESTACION, prompt=prompt,
                max_tokens=900, temperatura=0.3,
                actor_id=getattr(destinatario, "pk", None),
            )
        except PresupuestoIAExcedido:
            return {"ok": False, "texto": "", "acciones": [], "provider": ""}
    except Exception as exc:  # noqa: BLE001 — TodosFallaron, red, etc.
        logger.warning("propuesta proactiva u=%s falló: %s", getattr(destinatario, "pk", None), exc)
        return {"ok": False, "texto": "", "acciones": [], "provider": ""}

    parsed = _parsear_json(res.texto)
    if not isinstance(parsed, dict):
        return {"ok": False, "texto": "", "acciones": [], "provider": res.provider}
    texto = (parsed.get("texto") or "").strip()
    acciones = parsed.get("acciones") or []
    if not isinstance(acciones, list) or not permitir_acciones:
        acciones = []
    return {"ok": bool(texto), "texto": texto, "acciones": acciones, "provider": res.provider}


def _materializar_dictado(destinatario, *, titulo: str, hechos: str, ia: dict):
    """Crea un Dictado(origen='chalan_proactivo') PENDIENTE con las acciones
    propuestas (confirmada=False). Filtra TIPOS_PROHIBIDOS. Devuelve el Dictado o
    None si no quedó ninguna acción aplicable."""
    from .models import Dictado, DictadoAccion
    from .services import TIPOS_PROHIBIDOS, _apodo_de

    with transaction.atomic():
        dictado = Dictado.objects.create(
            autor=destinatario,
            texto_crudo=f"(El Chalán proactivo) {titulo}\n\n{hechos}"[:4000],
            estado="esperando_confirmacion",
            origen="chalan_proactivo",
            chalan=ia.get("provider", ""),
            chalan_apodo=_apodo_de(ia.get("provider", "")),
        )
        orden = 0
        for raw in ia.get("acciones") or []:
            if not isinstance(raw, dict):
                continue
            tipo = (raw.get("tipo") or "").strip()
            if not tipo or tipo in TIPOS_PROHIBIDOS:
                continue
            DictadoAccion.objects.create(
                dictado=dictado, orden=orden, tipo=tipo,
                descripcion=(raw.get("descripcion") or "")[:300],
                payload=raw.get("payload") or {},
                confianza=float(raw.get("confianza") or 1.0),
                confirmada=False,  # el usuario marca en el preview
            )
            orden += 1
        if orden == 0:
            # El modelo dijo "acciones" pero ninguna quedó aplicable → la
            # propuesta es solo informativa; descartamos el dictado vacío.
            dictado.delete()
            return None
    return dictado


def _push(destinatario, *, titulo: str, cuerpo: str, url: str, clave_dedup: str, origen_id: int) -> None:
    from lib.interfono import enviar_a_usuario
    try:
        enviar_a_usuario(
            destinatario, titulo=f"💡 {titulo}", cuerpo=cuerpo[:160], url=url,
            tag=f"chalan-prop-{clave_dedup}", categoria=CATEGORIA_PUSH,
            origen_modulo="chalan", origen_id=origen_id,
        )
    except Exception:  # noqa: BLE001 — un push roto no debe romper el scout
        logger.exception("push de propuesta proactiva falló u=%s", getattr(destinatario, "pk", None))


def proponer(*, destinatario, tipo: str, clave_dedup: str, titulo: str, hechos: str,
             url_base: str = "", permitir_acciones: bool = True):
    """Genera (si no existe) una `PropuestaChalan` para `destinatario`.

    - Idempotente por `(usuario, clave_dedup)`.
    - Llama a El Chalán (costo al destinatario). Si la IA cae o el usuario está
      topado, no crea nada y devuelve None (reintenta la próxima corrida).
    - Si la IA propone acciones, las materializa como Dictado pendiente y la
      propuesta enlaza a su preview; si no, enlaza a `url_base`.
    - Empuja un push por El Interfón (categoría `chalan_sugerencia`, opt-out).

    Devuelve la `PropuestaChalan` creada, o None.
    """
    from .models import PropuestaChalan

    if not destinatario or not getattr(destinatario, "is_active", False):
        return None
    if PropuestaChalan.objects.filter(usuario=destinatario, clave_dedup=clave_dedup).exists():
        return None

    ia = _redactar(destinatario, titulo=titulo, hechos=hechos, permitir_acciones=permitir_acciones)
    if not ia["ok"]:
        return None

    dictado = None
    if permitir_acciones and ia["acciones"]:
        dictado = _materializar_dictado(destinatario, titulo=titulo, hechos=hechos, ia=ia)

    url = f"/dictado/{dictado.pk}/preview" if dictado else (url_base or "/chalan/")
    try:
        prop = PropuestaChalan.objects.create(
            usuario=destinatario, tipo=tipo, clave_dedup=clave_dedup,
            titulo=titulo[:160], cuerpo=ia["texto"], url=url,
            dictado=dictado, chalan=ia.get("provider", ""), estado="pendiente",
        )
    except IntegrityError:
        # Carrera con otra corrida del scout → ya existe; respeta idempotencia.
        return None

    _push(destinatario, titulo=titulo, cuerpo=ia["texto"], url=url,
          clave_dedup=clave_dedup, origen_id=prop.pk)
    _emitir(destinatario, prop)
    return prop


def _emitir(destinatario, prop) -> None:
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="chalan.propuesta_generada",  # type: ignore[arg-type]
            actor_id=getattr(destinatario, "pk", None),
            actor_email=getattr(destinatario, "email", None),
            payload={"propuesta_id": prop.pk, "tipo": prop.tipo,
                     "con_acciones": bool(prop.dictado_id)},
        ))
    except Exception:  # noqa: BLE001
        logger.warning("emitir chalan.propuesta_generada falló", exc_info=True)
