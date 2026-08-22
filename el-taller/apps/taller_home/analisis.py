"""El Análisis — lo que El Chalán ve, entiende y señala del negocio.

Cómo está armado, y por qué:

- **Los números son consultas.** Exactos, gratis y frescos cada vez que se abre
  la pantalla. Un reporte del negocio no se puede permitir que un modelo se
  equivoque en una cifra.
- **La lectura es de El Chalán.** El "qué significa esto" sí lo pone la IA, en
  UNA sola llamada al día para los nueve temas juntos (no una por tema). Se
  guarda en `LecturaAnalisis`; si el modelo no responde, la pantalla sale
  igual con sus cifras y sin opinión.
- **Las alertas son deterministas.** Cruzar un umbral no necesita IA: se
  compara contra lo configurado en Gerencia y ya. Por eso pueden correr a
  diario sin costo.

Cada quien ve los temas que su permiso alcanza (`negocio.dominios_para`).
"""

from __future__ import annotations

import json
import logging
from datetime import date

logger = logging.getLogger(__name__)

ESTACION = "analisis_negocio"

# Cuánto texto de hechos se le manda al modelo por tema.
MAX_CHARS_HECHOS = 1500

_SYSTEM = """\
Eres El Chalán de El Despacho, el sistema de Learning Center — un despacho
mexicano de diseño y maquila de productos promocionales.

Te paso los NÚMEROS REALES del negocio, ya calculados, agrupados por tema. Tu
trabajo NO es recalcular ni repetirlos: es decir QUÉ SIGNIFICAN y QUÉ HACER.

Para cada tema escribe 2 a 4 frases, en español llano, como se lo dirías al
dueño:
- Qué está pasando (lo notable, no todo).
- Por qué importa o a qué se debe, si los datos lo insinúan.
- Qué conviene hacer esta semana, concreto.

REGLAS DURAS:
- NO inventes cifras ni causas: usa SOLO lo que te di. Si un tema no trae
  datos, dilo en una frase y ya.
- Nada de relleno ("es importante monitorear…"), nada de listas de viñetas,
  nada de markdown. Frases completas.
- Si algo está mal, dilo directo y sin adornos.
- Cuando menciones dinero, usa las mismas cifras que te di.

Devuelve SIEMPRE un ÚNICO objeto JSON, sin texto fuera del JSON:
{"lecturas": {"<tema>": "<tu lectura>", ...}}
"""


def _cfg():
    from ajustes.models import ConfiguracionAnalisis
    return ConfiguracionAnalisis.obtener()


# ── Alertas: no necesitan IA ─────────────────────────────────────────────

def alertas(usuario=None) -> list[dict]:
    """Lo que cruzó un umbral y merece que alguien lo mire.

    Cada alerta: {clave, nivel, titulo, detalle, url?}. `nivel` ∈ rojo|amarillo.
    """
    from apps.taller_home.negocio import dominios_para

    cfg = _cfg()
    visibles = set(dominios_para(usuario)) if usuario is not None else None
    salida: list[dict] = []

    def puede(dominio: str) -> bool:
        return visibles is None or dominio in visibles

    # Cotizaciones armadas que nunca se mandaron / enviadas sin respuesta.
    if puede("ventas"):
        try:
            from apps.cotizaciones.embudo import embudo

            emb = embudo()
            if emb["sin_enviar"]:
                salida.append({
                    "clave": "cot_sin_enviar",
                    "nivel": "amarillo",
                    "titulo": f"{len(emb['sin_enviar'])} cotizaciones listas que nunca se mandaron",
                    "detalle": "; ".join(
                        f"{f['proyecto']} ({f['cliente']}, {f['dias']} días)"
                        for f in emb["sin_enviar"][:5]
                    ),
                    "url": "/cotizaciones/",
                })
            if emb["enfriadas"]:
                salida.append({
                    "clave": "cot_enfriadas",
                    "nivel": "amarillo",
                    "titulo": (
                        f"{len(emb['enfriadas'])} cotizaciones llevan más de "
                        f"{emb['dias_silencio']} días sin respuesta"
                    ),
                    "detalle": "; ".join(
                        f"{f['proyecto']} ({f['cliente']}, {f['dias']} días)"
                        for f in emb["enfriadas"][:5]
                    ),
                    "url": "/cotizaciones/",
                })
        except Exception:  # noqa: BLE001
            logger.warning("alertas: falló el embudo", exc_info=True)

    # Proyectos por debajo del margen sano o en pérdida.
    if puede("rentabilidad"):
        try:
            from apps.los_proyectos import rentabilidad as rent

            res = rent.resumen()
            if res["n_en_perdida"]:
                salida.append({
                    "clave": "proyectos_en_perdida",
                    "nivel": "rojo",
                    "titulo": f"{res['n_en_perdida']} proyectos están dejando pérdida",
                    "detalle": "; ".join(
                        f"{f['nombre']} ({f['margen_materiales_pct']:.0f}%)"
                        for f in res["en_perdida"][:5]
                    ),
                    "url": "/analisis/#rentabilidad",
                })
            if res["n_bajo_umbral"]:
                salida.append({
                    "clave": "proyectos_bajo_margen",
                    "nivel": "amarillo",
                    "titulo": (
                        f"{res['n_bajo_umbral']} proyectos están debajo del margen sano "
                        f"({res['margen_sano_pct']:.0f}%)"
                    ),
                    "detalle": "; ".join(
                        f"{f['nombre']} ({f['margen_materiales_pct']:.0f}%)"
                        for f in res["bajo_umbral"][:5]
                    ),
                    "url": "/analisis/#rentabilidad",
                })
        except Exception:  # noqa: BLE001
            logger.warning("alertas: falló la rentabilidad", exc_info=True)

    # Cobranza vencida y facturas con CFDI que nunca se emitieron.
    if puede("cobranza"):
        try:
            from apps.facturacion import services as fac_services
            from apps.tesoreria import services as tes_services

            hoy = date.today()
            vencido = 0.0
            atrasadas = []
            for f in tes_services.cxc_unificado():
                venc = f.get("fecha_vencimiento")
                if venc and (hoy - venc).days >= cfg.dias_mora_alerta:
                    vencido += float(f["saldo"])
                    atrasadas.append(f)
            if atrasadas:
                salida.append({
                    "clave": "cobranza_vencida",
                    "nivel": "rojo",
                    "titulo": (
                        f"${vencido:,.0f} llevan más de {cfg.dias_mora_alerta} días sin cobrarse"
                    ),
                    "detalle": "; ".join(
                        f"{f['cliente']} ${float(f['saldo']):,.0f}" for f in atrasadas[:5]
                    ),
                    "url": "/tesoreria/por-cobrar/",
                })
            fac = fac_services.kpis_landing()
            if fac.get("cfdi_sin_emitir"):
                salida.append({
                    "clave": "cfdi_sin_emitir",
                    "nivel": "amarillo",
                    "titulo": (
                        f"{fac['cfdi_sin_emitir']} facturas tienen su CFDI subido pero "
                        "siguen en borrador"
                    ),
                    "detalle": (
                        "Mientras estén así no generan cuenta por cobrar en Contaduría "
                        "ni reciben recordatorio de cobranza."
                    ),
                    "url": "/facturacion/",
                })
        except Exception:  # noqa: BLE001
            logger.warning("alertas: falló la cobranza", exc_info=True)

    # Cancelaciones sin motivo: sin eso no se puede aprender por qué se pierde.
    if puede("perdidos"):
        try:
            from apps.los_proyectos.models import Proyecto

            sin_motivo = Proyecto.objects.filter(
                estado="cancelado", archivado=False, motivo_cancelacion__isnull=True,
            ).count()
            if sin_motivo:
                salida.append({
                    "clave": "cancelados_sin_motivo",
                    "nivel": "amarillo",
                    "titulo": f"{sin_motivo} proyectos cancelados no dicen por qué",
                    "detalle": "Sin el motivo no se puede saber qué está tumbando el trabajo.",
                    "url": "/proyectos/cancelaciones/",
                })
        except Exception:  # noqa: BLE001
            logger.warning("alertas: falló el conteo de cancelaciones", exc_info=True)

    orden = {"rojo": 0, "amarillo": 1}
    return sorted(salida, key=lambda a: orden.get(a["nivel"], 9))


# ── La lectura del Chalán: una llamada, todos los temas ──────────────────

def generar_lectura(*, usuario=None, dry_run: bool = False) -> dict:
    """Le pide al Chalán que interprete los números. Una sola llamada."""
    from apps.taller_home.negocio import DOMINIOS, ETIQUETA_DOMINIO, hechos_de

    hechos: dict[str, dict] = {}
    for dominio in DOMINIOS:
        if dominio == "margenes":  # alias, no es un tema aparte
            continue
        datos = hechos_de(dominio, usuario)
        if datos["hechos"]:
            hechos[dominio] = datos

    if not hechos:
        return {"ok": False, "error": "Todavía no hay datos que analizar.", "creadas": 0}

    partes = [
        f"[{clave}] {ETIQUETA_DOMINIO.get(clave, clave)}\n"
        + datos["hechos"][:MAX_CHARS_HECHOS]
        for clave, datos in hechos.items()
    ]
    prompt = (
        "Estos son los números del negocio de hoy. Da tu lectura de cada tema.\n\n"
        + "\n\n".join(partes)
        + "\n\nTemas a los que debes responder: "
        + ", ".join(hechos)
    )

    if dry_run:
        return {"ok": True, "dry_run": True, "temas": list(hechos), "creadas": 0}

    # Mismo armado que el resto del repo: voz del despacho + instrucciones +
    # lo que el Chalán ya aprendió del negocio + reglas + los datos.
    from apps.el_dictado.conocimiento import bloque_contexto_negocio

    from chalanes.voz import preludio, reglas

    partes = [
        preludio(ESTACION),
        _SYSTEM,
        bloque_contexto_negocio(),
        reglas(),
        prompt,
    ]
    try:
        from lib.analistas import analizar

        respuesta = analizar(
            estacion=ESTACION,
            prompt="\n\n".join(p for p in partes if p),
            max_tokens=1400,
            temperatura=0.3,
            actor_id=getattr(usuario, "pk", None),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("El Análisis: la IA no respondió", exc_info=True)
        return {"ok": False, "error": f"El Chalán no pudo responder: {e}", "creadas": 0}

    lecturas = _parsear(respuesta.texto or "")
    if not lecturas:
        return {"ok": False, "error": "El Chalán respondió algo que no se pudo leer.",
                "creadas": 0}

    from apps.taller_home.models import LecturaAnalisis

    modelo = respuesta.modelo or ""
    creadas = 0
    for dominio, lectura in lecturas.items():
        if dominio not in hechos or not (lectura or "").strip():
            continue
        LecturaAnalisis.objects.create(
            dominio=dominio, texto=lectura.strip()[:4000], modelo_ia=modelo[:80],
        )
        creadas += 1
    return {"ok": True, "creadas": creadas, "temas": list(lecturas)}


def _parsear(texto: str) -> dict[str, str]:
    """Saca el JSON de la respuesta, tolerando que venga envuelto en fences."""
    limpio = (texto or "").strip()
    if limpio.startswith("```"):
        limpio = limpio.split("```")[1] if "```" in limpio[3:] else limpio[3:]
        limpio = limpio.removeprefix("json").strip()
    inicio, fin = limpio.find("{"), limpio.rfind("}")
    if inicio == -1 or fin == -1:
        return {}
    try:
        datos = json.loads(limpio[inicio:fin + 1])
    except (ValueError, TypeError):
        return {}
    lecturas = datos.get("lecturas") if isinstance(datos, dict) else None
    if not isinstance(lecturas, dict):
        return {}
    return {str(k): str(v) for k, v in lecturas.items() if v}


# ── Lo que consume la pantalla ───────────────────────────────────────────

def panorama(usuario) -> dict:
    """Todo lo que necesita El Análisis: temas visibles, cifras, lectura y alertas."""
    from apps.taller_home.models import LecturaAnalisis
    from apps.taller_home.negocio import ETIQUETA_DOMINIO, dominios_para, hechos_de

    visibles = [d for d in dominios_para(usuario) if d != "margenes"]
    lecturas = LecturaAnalisis.ultimas()

    temas = []
    for dominio in visibles:
        datos = hechos_de(dominio, usuario)
        lectura = lecturas.get(dominio)
        temas.append({
            "clave": dominio,
            "titulo": datos["titulo"] or ETIQUETA_DOMINIO.get(dominio, dominio),
            "lineas": [ln for ln in (datos["hechos"] or "").split("\n") if ln.strip()],
            "metricas": datos["metricas"],
            "lectura": lectura.texto if lectura else "",
            "lectura_en": lectura.generado_en if lectura else None,
        })

    ultima = max(
        (t["lectura_en"] for t in temas if t["lectura_en"]), default=None,
    )
    return {
        "temas": temas,
        "alertas": alertas(usuario),
        "ultima_lectura_en": ultima,
        "cfg": _cfg(),
    }
