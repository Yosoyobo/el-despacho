"""El Chalán lee la Constancia de Situación Fiscal (estación `documento_cliente`).

Decisión de Oscar (2026-09-29): cuando un cliente sube su CSF, El Chalán propone
los datos fiscales para su ficha (RFC, razón social, régimen, código postal) **y
revisa que la constancia sea reciente**; los días se ajustan en La Gerencia →
Portal de clientes (`ConfiguracionPortal.csf_vigencia_dias`).

Los candados de siempre (`memory: la IA del Taller procesa lo subido`), para que
la IA tampoco haga algo loco:

1. **Sólo propone.** Lo que lee se guarda en `DocumentoCliente.ia` y se enseña
   marcado con 🤖 y su confianza. La ficha cambia únicamente cuando alguien del
   equipo pica «Aplicar a la ficha» (`aplicar`).
2. **Se valida contra el documento.** Si la constancia es un PDF con texto, cada
   dato que contesta El Chalán tiene que APARECER en ese texto: un RFC, un código
   postal o una fecha que no están en el PDF se descartan como inventados. El RFC
   además tiene que tener la forma del SAT.
3. **Una sola lectura.** Se pregunta al subir, en el fondo, y se guarda; la ficha
   y el portal leen lo guardado.

Sin El Chalán (sin llaves, o no contesta) el documento se guarda igual y queda
«no se pudo leer»: lo revisa una persona. Nunca lanza.
"""

from __future__ import annotations

import base64
import contextlib
import datetime as dt
import io
import json
import logging
import re
import unicodedata

from django.utils import timezone

logger = logging.getLogger(__name__)

ESTACION = "documento_cliente"
UMBRAL_CONFIANZA = 0.6
#: Cuánto texto se le manda. Una CSF son 2-3 páginas; lo demás es ruido.
MAX_TEXTO = 12000

RE_RFC = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
RE_CP = re.compile(r"^\d{5}$")
MESES = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7,
         "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}
RE_FECHA_LARGA = re.compile(r"(\d{1,2})\s+DE\s+([A-Z]+)\s+DE\s+(\d{4})")
RE_FECHA_CORTA = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})")


# ── Leer el archivo ─────────────────────────────────────────────────────────


def texto_de_pdf(contenido: bytes) -> str:
    """El texto de las primeras páginas, o "" si no trae (escaneado) o no abre."""
    try:
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(contenido))
        partes = []
        for pagina in lector.pages[:4]:
            partes.append(pagina.extract_text() or "")
            if sum(len(p) for p in partes) > MAX_TEXTO:
                break
        return "\n".join(partes).strip()[:MAX_TEXTO]
    except Exception:  # noqa: BLE001 — PDF roto o cifrado
        logger.info("csf: no se pudo sacar texto del PDF", exc_info=True)
        return ""


def _plano(texto: str) -> str:
    """Mayúsculas, sin acentos y con un solo espacio: para comparar contra el PDF."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).upper()
    return re.sub(r"\s+", " ", t).strip()


def fechas_en(texto: str) -> set[dt.date]:
    """Todas las fechas que trae el texto («15 DE ENERO DE 2026», «15/01/2026»)."""
    plano = _plano(texto)
    salida: set[dt.date] = set()
    for d, mes, a in RE_FECHA_LARGA.findall(plano):
        if mes in MESES:
            with contextlib.suppress(ValueError):
                salida.add(dt.date(int(a), MESES[mes], int(d)))
    for d, m, a in RE_FECHA_CORTA.findall(plano):
        with contextlib.suppress(ValueError):
            salida.add(dt.date(int(a), int(m), int(d)))
    return salida


# ── Preguntarle a El Chalán ─────────────────────────────────────────────────

_INSTRUCCIONES = (
    "Eres El Chalán de Learning Center, un despacho mexicano. Un cliente subió lo que dice ser "
    "su Constancia de Situación Fiscal (CSF) del SAT. Lee el documento y contesta SÓLO un JSON, "
    "sin texto antes ni después, con esta forma:\n"
    '{"es_csf": true, "rfc": "", "razon_social": "", "regimen_fiscal": "", '
    '"codigo_postal": "", "fecha_emision": "AAAA-MM-DD", "confianza": 0.0}\n\n'
    "Reglas:\n"
    "- es_csf: false si el documento NO es una Constancia de Situación Fiscal.\n"
    "- rfc: el RFC del contribuyente tal como aparece, sin espacios.\n"
    "- razon_social: la «Denominación/Razón Social» (persona moral) o el nombre completo "
    "(persona física), en mayúsculas y SIN el régimen de capital (sin «S.A. DE C.V.» si viene "
    "aparte en «Régimen Capital»).\n"
    "- regimen_fiscal: el régimen vigente (el de la tabla «Regímenes»); si hay varios, el primero. "
    "Con su clave si la trae, p. ej. «601 · General de Ley Personas Morales».\n"
    "- codigo_postal: el del domicilio fiscal, 5 dígitos.\n"
    "- fecha_emision: la de «Lugar y Fecha de Emisión», en formato AAAA-MM-DD.\n"
    "- Lo que no veas, déjalo vacío. NUNCA inventes un dato.\n"
    "- confianza: de 0 a 1, qué tan seguro estás de lo que leíste.\n"
)


def _llamar(prompt: str, imagenes: list[dict] | None = None) -> str:
    """El único punto que toca a Los Analistas (las pruebas lo sustituyen)."""
    from lib.analistas import analizar

    res = analizar(estacion=ESTACION, prompt=prompt, max_tokens=600, temperatura=0.0,
                   imagenes=imagenes or None)
    return res.texto


def _parsear(texto: str) -> dict | None:
    if not texto:
        return None
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        return None
    try:
        datos = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return datos if isinstance(datos, dict) else None


def _fecha_iso(valor) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(valor or "").strip()[:10])
    except ValueError:
        return None


def limpiar(crudo: dict, texto_fuente: str = "") -> tuple[dict, list[str]]:
    """Valida lo que contestó El Chalán. (datos, descartados).

    Con `texto_fuente` (PDF con texto) cada dato tiene que estar en el documento;
    sin él (una foto) sólo se revisa la forma.
    """
    plano = _plano(texto_fuente)
    plano_junto = plano.replace(" ", "")
    datos: dict = {}
    fuera: list[str] = []

    rfc = re.sub(r"[\s-]", "", str(crudo.get("rfc") or "")).upper()
    if rfc:
        if not RE_RFC.match(rfc):
            fuera.append(f"RFC «{rfc[:20]}» (no tiene la forma del SAT)")
        elif plano and rfc not in plano_junto:
            fuera.append(f"RFC «{rfc}» (no aparece en el documento)")
        else:
            datos["rfc"] = rfc

    razon = re.sub(r"\s+", " ", str(crudo.get("razon_social") or "")).strip().upper()[:200]
    if razon:
        if plano and _plano(razon) not in plano:
            fuera.append(f"razón social «{razon[:60]}» (no aparece en el documento)")
        else:
            datos["razon_social"] = razon

    regimen = re.sub(r"\s+", " ", str(crudo.get("regimen_fiscal") or "")).strip()[:120]
    if regimen:
        datos["regimen_fiscal"] = regimen

    cp = re.sub(r"\D", "", str(crudo.get("codigo_postal") or ""))
    if cp:
        if not RE_CP.match(cp):
            fuera.append(f"código postal «{cp[:10]}»")
        elif plano and cp not in plano_junto:
            fuera.append(f"código postal «{cp}» (no aparece en el documento)")
        else:
            datos["codigo_postal"] = cp

    fecha = _fecha_iso(crudo.get("fecha_emision"))
    if crudo.get("fecha_emision") and fecha is None:
        fuera.append("fecha de emisión (no se entendió)")
    elif fecha is not None:
        if plano and fecha not in fechas_en(texto_fuente):
            fuera.append(f"fecha de emisión {fecha.isoformat()} (no aparece en el documento)")
        else:
            datos["fecha_emision"] = fecha.isoformat()
    return datos, fuera


def revisar_vigencia(fecha_iso: str | None, limite_dias: int, hoy: dt.date | None = None) -> dict:
    """¿La constancia es reciente? `vigente` es None cuando no hay fecha que revisar."""
    hoy = hoy or timezone.localdate()
    fecha = _fecha_iso(fecha_iso)
    if fecha is None:
        return {"fecha_emision": "", "dias": None, "limite": limite_dias, "vigente": None,
                "motivo": "No se pudo leer la fecha de emisión."}
    dias = (hoy - fecha).days
    if dias < 0:
        return {"fecha_emision": fecha.isoformat(), "dias": dias, "limite": limite_dias,
                "vigente": None, "motivo": "La fecha de emisión es posterior a hoy: revísala a mano."}
    vigente = dias <= limite_dias
    motivo = "" if vigente else (f"Tiene {dias} días; pedimos una de máximo {limite_dias}. "
                                 "Descarga una nueva en el portal del SAT.")
    return {"fecha_emision": fecha.isoformat(), "dias": dias, "limite": limite_dias,
            "vigente": vigente, "motivo": motivo}


def _limite() -> int:
    try:
        from .models import ConfiguracionPortal

        return int(ConfiguracionPortal.obtener().csf_vigencia_dias or 30)
    except Exception:  # noqa: BLE001
        return 30


def leer(contenido: bytes, mime: str) -> tuple[str, dict]:
    """(ia_estado, ia). Nunca lanza."""
    from .models.documento import IA_LISTA, IA_SIN_LEER

    ahora = timezone.now().isoformat()
    texto = ""
    imagenes: list[dict] = []
    if mime == "application/pdf":
        texto = texto_de_pdf(contenido)
        if not texto:
            return IA_SIN_LEER, {"motivo": "El PDF no trae texto (parece escaneado): revísalo a mano.",
                                 "leido_en": ahora}
        prompt = f"{_INSTRUCCIONES}\nTEXTO DEL DOCUMENTO:\n{texto}"
    elif (mime or "").startswith("image/"):
        imagenes = [{"base64": base64.b64encode(contenido).decode("ascii"), "media_type": mime}]
        prompt = f"{_INSTRUCCIONES}\nEl documento va en la imagen."
    else:
        return IA_SIN_LEER, {"motivo": "Tipo de archivo que El Chalán no lee.", "leido_en": ahora}

    try:
        respuesta = _llamar(prompt, imagenes)
    except Exception as exc:  # noqa: BLE001 — sin llaves, sin presupuesto, caído
        logger.warning("csf: El Chalán no contestó: %s", exc)
        return IA_SIN_LEER, {"motivo": "El Chalán no está disponible: revísala a mano.", "leido_en": ahora}
    crudo = _parsear(respuesta)
    if crudo is None:
        return IA_SIN_LEER, {"motivo": "El Chalán no contestó algo que se pudiera leer.", "leido_en": ahora}
    if crudo.get("es_csf") is False:
        return IA_LISTA, {"es_csf": False, "datos": {}, "descartados": [], "confianza": 0.0,
                          "vigencia": {}, "origen": "pdf" if texto else "imagen", "leido_en": ahora,
                          "motivo": "El Chalán dice que este documento no es una Constancia de Situación Fiscal."}
    datos, fuera = limpiar(crudo, texto)
    try:
        confianza = max(0.0, min(1.0, float(crudo.get("confianza") or 0)))
    except (TypeError, ValueError):
        confianza = 0.0
    return IA_LISTA, {
        "es_csf": True, "datos": datos, "descartados": fuera, "confianza": round(confianza, 2),
        "vigencia": revisar_vigencia(datos.get("fecha_emision"), _limite()),
        "origen": "pdf" if texto else "imagen", "leido_en": ahora, "motivo": "",
    }


def procesar(doc_id: int) -> None:
    """Lee la CSF guardada y deja el resultado en el documento. Nunca lanza."""
    from .models import DocumentoCliente
    from .models.documento import IA_SIN_LEER

    try:
        doc = DocumentoCliente.objects.get(pk=doc_id)
    except DocumentoCliente.DoesNotExist:
        return
    try:
        from lib import almacen

        contenido, mime, _ = almacen.leer(doc.archivo)
        estado, ia = leer(contenido, doc.mime or mime)
    except Exception:  # noqa: BLE001
        logger.exception("csf: no se pudo leer el documento %s", doc_id)
        estado, ia = IA_SIN_LEER, {"motivo": "No se pudo abrir el archivo.",
                                   "leido_en": timezone.now().isoformat()}
    DocumentoCliente.objects.filter(pk=doc_id).update(ia_estado=estado, ia=ia)


# ── Aplicar a la ficha (El Taller) ──────────────────────────────────────────


def cambios_propuestos(doc) -> list[dict]:
    """Qué cambiaría en la ficha: [{campo, etiqueta, actual, nuevo}]. Vacío si
    no hay nada que proponer (o ya coincide)."""
    datos = doc.csf
    if not datos.get("rfc"):
        return []
    fila = doc.cliente.razones_sociales.filter(rfc=datos["rfc"]).first()
    etiquetas = {"rfc": "RFC", "razon_social": "Razón social", "regimen_fiscal": "Régimen fiscal",
                 "codigo_postal": "CP fiscal"}
    salida = []
    for campo, etiqueta in etiquetas.items():
        nuevo = datos.get(campo) or ""
        actual = getattr(fila, campo, "") if fila is not None else ""
        if nuevo and nuevo != actual:
            salida.append({"campo": campo, "etiqueta": etiqueta, "actual": actual, "nuevo": nuevo})
    return salida


def aplicar(doc, usuario) -> str:
    """Pasa a la ficha lo que leyó El Chalán. Devuelve el aviso para la persona.

    Si el cliente ya tiene una razón social con ese RFC, la actualiza; si no,
    agrega una (principal si es la primera). Después espeja la principal a los
    campos del cliente, como el formulario de la ficha.
    """
    from apps.la_cartera.models import ClienteRazonSocial
    from apps.la_cartera.services import espejar_razon_principal

    from .servicios import ErrorPortal

    datos = doc.csf
    if not datos.get("rfc"):
        raise ErrorPortal("El Chalán no leyó un RFC en esta constancia: no hay qué aplicar.")
    cliente = doc.cliente
    fila = cliente.razones_sociales.filter(rfc=datos["rfc"]).first()
    if fila is None:
        fila = ClienteRazonSocial(cliente=cliente, rfc=datos["rfc"],
                                  razon_social=datos.get("razon_social") or cliente.razon_social.upper(),
                                  principal=not cliente.razones_sociales.exists())
        creada = True
    else:
        creada = False
        if datos.get("razon_social"):
            fila.razon_social = datos["razon_social"]
    if datos.get("regimen_fiscal"):
        fila.regimen_fiscal = datos["regimen_fiscal"]
    if datos.get("codigo_postal"):
        fila.codigo_postal = datos["codigo_postal"]
    fila.save()
    espejar_razon_principal(cliente)
    doc.aplicado_por = usuario if getattr(usuario, "is_authenticated", False) else None
    doc.aplicado_en = timezone.now()
    doc.save(update_fields=["aplicado_por", "aplicado_en"])
    return (f"Listo: se agregó la razón social {fila.razon_social} ({fila.rfc}) a la ficha." if creada
            else f"Listo: se actualizó la razón social {fila.razon_social} ({fila.rfc}).")


__all__ = [
    "ESTACION",
    "UMBRAL_CONFIANZA",
    "aplicar",
    "cambios_propuestos",
    "fechas_en",
    "leer",
    "limpiar",
    "procesar",
    "revisar_vigencia",
    "texto_de_pdf",
]
