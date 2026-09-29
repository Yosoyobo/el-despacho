"""Helpers de fecha/hora con zona horaria de México."""

import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ_MX = ZoneInfo("America/Mexico_City")


def ahora_mx() -> datetime:
    return datetime.now(TZ_MX)


def a_mx(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("Datetime sin tzinfo no se puede convertir a MX")
    return dt.astimezone(TZ_MX)


# ── Fechas escritas en español (LC 2026-09-28) ──────────────────────────────
# La tarea rápida de la tarjeta de producto («@jorge revisar el bordado el
# viernes») se crea SIN IA, así que la fecha la saca esto: un reconocedor chico,
# determinista y probado, no un intérprete. Sólo entiende las formas que la gente
# de verdad escribe al apuntar un pendiente; lo que no reconozca se queda en el
# título, que es el lado seguro (una fecha inventada es peor que ninguna).

_DIAS_SEMANA = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}
_MESES = {
    "enero": 1, "ene": 1, "febrero": 2, "feb": 2, "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4, "mayo": 5, "may": 5, "junio": 6, "jun": 6,
    "julio": 7, "jul": 7, "agosto": 8, "ago": 8, "septiembre": 9,
    "setiembre": 9, "sept": 9, "sep": 9, "octubre": 10, "oct": 10,
    "noviembre": 11, "nov": 11, "diciembre": 12, "dic": 12,
}

# Lo que suele ir antes de la fecha y también se quita del título:
# «para el viernes», «antes del 15/10», «este jueves», «el próximo lunes».
_PREFIJO = (r"(?:(?:para|antes\s+del?|hasta\s+el|a\s+mas\s+tardar\s+el)\s+)?"
            r"(?:el\s+|este\s+|esta\s+)?(?:proximo\s+|proxima\s+)?")
_ANTES = r"(?<![\w/-])"
_DESPUES = r"(?![\w/-])"
_NOMBRES_MES = "|".join(sorted(_MESES, key=len, reverse=True))

_PATRONES = (
    ("pasado", re.compile(_ANTES + _PREFIJO + r"pasado\s+manana" + _DESPUES)),
    # «por la mañana» / «en la mañana» es la hora del día, no el día de mañana.
    ("manana", re.compile(_ANTES + r"(?<!la )" + _PREFIJO + r"manana" + _DESPUES)),
    ("hoy", re.compile(_ANTES + _PREFIJO + r"hoy" + _DESPUES)),
    ("dia", re.compile(_ANTES + _PREFIJO + r"(?P<dia>" + "|".join(_DIAS_SEMANA) + r")"
                       + _DESPUES)),
    ("de_mes", re.compile(_ANTES + _PREFIJO + r"(?P<d>\d{1,2})\s+de\s+(?P<m>" + _NOMBRES_MES
                          + r")(?:\s+(?:de|del)\s+(?P<a>\d{4}))?" + _DESPUES)),
    ("barra", re.compile(_ANTES + _PREFIJO
                         + r"(?P<d>\d{1,2})/(?P<m>\d{1,2})(?:/(?P<a>\d{4}|\d{2}))?" + _DESPUES)),
    ("guion", re.compile(_ANTES + _PREFIJO + r"(?P<d>\d{1,2})-(?P<m>\d{1,2})-(?P<a>\d{4})"
                         + _DESPUES)),
)


def _plano_1a1(texto: str) -> str:
    """Minúsculas y sin acentos, **carácter por carácter** (misma longitud), para
    que un hallazgo en el texto plano se pueda recortar del original."""
    salida = []
    for c in texto:
        bajo = c.lower()
        salida.append(unicodedata.normalize("NFD", bajo)[0] if bajo else c)
    return "".join(salida)


def _fecha_con_o_sin_anio(dia: int, mes: int, hoy: date, anio: int | None) -> date | None:
    try:
        if anio is not None:
            return date(anio, mes, dia)
        candidata = date(hoy.year, mes, dia)
        # Sin año, una fecha que ya pasó es la del año que entra.
        return candidata if candidata >= hoy else date(hoy.year + 1, mes, dia)
    except ValueError:
        return None


def _resolver(tipo: str, m, hoy: date) -> date | None:
    if tipo == "hoy":
        return hoy
    if tipo == "manana":
        return hoy + timedelta(days=1)
    if tipo == "pasado":
        return hoy + timedelta(days=2)
    if tipo == "dia":
        delta = (_DIAS_SEMANA[m.group("dia")] - hoy.weekday()) % 7
        # «el viernes» dicho un viernes es el de la semana que entra: para el
        # mismo día está «hoy».
        return hoy + timedelta(days=delta or 7)
    anio = m.group("a")
    if anio is not None:
        anio = int(anio) + (2000 if len(anio) == 2 else 0)
    mes = _MESES[m.group("m")] if tipo == "de_mes" else int(m.group("m"))
    return _fecha_con_o_sin_anio(int(m.group("d")), mes, hoy, anio)


def fecha_en_texto(texto: str, hoy: date | None = None) -> tuple[date | None, str]:
    """Busca una fecha escrita en `texto` y la saca de él.

    Devuelve `(fecha, resto)`: la fecha reconocida (o `None`) y el texto sin
    ella, con los espacios apretados. Entiende «hoy», «mañana», «pasado mañana»,
    los días de la semana («el viernes», «el próximo lunes»), «15 de octubre»
    (con o sin año) y «15/10», «15/10/26», «15-10-2026». Si hay varias, gana la
    primera que aparece; una que no es fecha real («31/02») se ignora. Nunca
    lanza.
    """
    crudo = texto or ""
    hoy = hoy or ahora_mx().date()
    plano = _plano_1a1(crudo)
    candidatos = []
    for orden, (tipo, patron) in enumerate(_PATRONES):
        for m in patron.finditer(plano):
            if m.end() > m.start():
                candidatos.append((m.start(), orden, tipo, m))
    for _inicio, _orden, tipo, m in sorted(candidatos, key=lambda c: (c[0], c[1])):
        try:
            fecha = _resolver(tipo, m, hoy)
        except Exception:  # noqa: BLE001 — una forma rara no tumba la tarea
            fecha = None
        if fecha is None:
            continue
        resto = crudo[:m.start()] + " " + crudo[m.end():]
        return fecha, " ".join(resto.split())
    return None, " ".join(crudo.split())
