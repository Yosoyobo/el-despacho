"""Ejecuta un DSL validado contra el ORM de Django con cost guards.

Cost guards aplicados:
- Slice a `MAX_FILAS_PRE_AGREGACION` filas antes de Sum/Avg/Min/Max y de las
  duraciones (count es ya O(1) en SQL — no se limita).
- Construye el queryset por whitelist, nunca aceptando atributos crudos: toda
  ruta del ORM sale de `schema.py`, nunca de la definición.
- Logs/errores ASCII para no romper en cualquier locale.

Defensa en profundidad: con `usuario`, el ejecutor RE-CHEQUEA los permisos
del dato (`permisos_de`) aunque el caller ya lo haya hecho. Sin `usuario`
(tareas internas, pruebas) no hay a quién preguntarle y calcula.

Las duraciones se calculan en Python sobre pares acotados: la resta de fechas
en SQL no es portable entre SQLite (pruebas) y PostgreSQL 16 (producción).

NO usa `signal.SIGALRM` para timeout porque no es portable a Windows
ni seguro en threads. El slice cumple el rol práctico de cost guard
(en el datatablo del despacho los modelos no pasan de ~10k filas).
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.apps import apps
from django.db.models import Avg, Count, DateTimeField, F, Max, Min, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .schema import ENTIDADES, TOP_GRUPOS_DEFAULT, ruta_de
from .validador import ValidacionError, metadatos_de, permisos_de, validar

logger = logging.getLogger(__name__)

MAX_FILAS_PRE_AGREGACION = 10_000
SIN_NUMERO = "—"

_AGG = {"sum": Sum, "avg": Avg, "min": Min, "max": Max}
_LOOKUP = {"eq": "exact", "in": "in", "gte": "gte", "lte": "lte", "gt": "gt", "lt": "lt",
           "contiene": "icontains"}


def _modelo_django(entidad: str):
    app_label, model_name = ENTIDADES[entidad]["modelo"].split(".", 1)
    return apps.get_model(app_label, model_name)


def entidad_disponible(entidad: str) -> bool:
    """¿El modelo de la entidad está instalado en ESTA app? (La Gerencia, por
    ejemplo, no instala `recados`.)"""
    try:
        _modelo_django(entidad)
    except LookupError:
        return False
    return True


def _campo_modelo(Modelo, ruta: str):
    """El campo del modelo al final de `a__b__c`."""
    actual = Modelo
    campo = None
    for parte in ruta.split("__"):
        campo = actual._meta.get_field(parte)
        if campo.is_relation and campo.related_model is not None:
            actual = campo.related_model
    return campo


def _es_datetime(Modelo, ruta: str) -> bool:
    try:
        return isinstance(_campo_modelo(Modelo, ruta), DateTimeField)
    except Exception:  # noqa: BLE001
        return True


# ── Ventanas de tiempo ───────────────────────────────────────────────────────


def _restar_meses(d: date, meses: int) -> date:
    total = d.year * 12 + (d.month - 1) - meses
    ano, mes = divmod(total, 12)
    mes += 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def _inicio_trimestre(d: date) -> date:
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def _ventana_a_rango(ventana: str, hoy: date | None = None) -> tuple[date | None, date | None]:
    hoy = hoy or timezone.localdate()
    if ventana == "siempre":
        return None, None
    if ventana == "ultimos_7d":
        return hoy - timedelta(days=7), hoy
    if ventana == "ultimos_30d":
        return hoy - timedelta(days=30), hoy
    if ventana == "ultimos_90d":
        return hoy - timedelta(days=90), hoy
    if ventana == "ultimos_12m":
        return _restar_meses(hoy, 12), hoy
    if ventana == "esta_semana":
        return hoy - timedelta(days=hoy.weekday()), hoy
    if ventana == "este_mes":
        return hoy.replace(day=1), hoy
    if ventana == "mes_pasado":
        fin = hoy.replace(day=1) - timedelta(days=1)
        return fin.replace(day=1), fin
    if ventana == "este_trimestre":
        return _inicio_trimestre(hoy), hoy
    if ventana == "este_ano":
        return hoy.replace(month=1, day=1), hoy
    return None, None


def ventana_anterior(ventana: str, hoy: date | None = None) -> tuple[date, date] | None:
    """El periodo anterior COMPARABLE: «este mes» (1 al 29) se compara con el
    1 al 29 del mes pasado, no con el mes pasado completo; «últimos 30 días»
    con los 31 días anteriores (la ventana v1 incluye los dos extremos)."""
    hoy = hoy or timezone.localdate()
    desde, hasta = _ventana_a_rango(ventana, hoy)
    if desde is None or hasta is None:
        return None
    if ventana in ("ultimos_7d", "ultimos_30d", "ultimos_90d"):
        largo = (hasta - desde).days + 1
        return desde - timedelta(days=largo), desde - timedelta(days=1)
    if ventana == "ultimos_12m":
        return _restar_meses(desde, 12), desde - timedelta(days=1)
    if ventana == "esta_semana":
        return desde - timedelta(days=7), hasta - timedelta(days=7)
    if ventana == "este_mes":
        return _restar_meses(desde, 1), _restar_meses(hasta, 1)
    if ventana == "mes_pasado":
        fin = desde - timedelta(days=1)
        return fin.replace(day=1), fin
    if ventana == "este_trimestre":
        inicio = _restar_meses(desde, 3)
        fin_trimestre = desde - timedelta(days=1)
        return inicio, min(inicio + (hasta - desde), fin_trimestre)
    if ventana == "este_ano":
        return _restar_meses(desde, 12), _restar_meses(hasta, 12)
    return None


def _aplicar_rango(qs, Modelo, ruta_fecha: str, desde: date | None, hasta: date | None):
    # El lookup `__date` SOLO aplica a DateTimeField. Egreso/Ingreso usan
    # `fecha` como DateField puro — ahí va el lookup directo (sin `__date`),
    # o Django lanza "Unsupported lookup 'date' for DateField".
    sufijo = "__date" if _es_datetime(Modelo, ruta_fecha) else ""
    if desde:
        qs = qs.filter(**{f"{ruta_fecha}{sufijo}__gte": desde})
    if hasta:
        qs = qs.filter(**{f"{ruta_fecha}{sufijo}__lte": hasta})
    return qs


# ── Filtros ──────────────────────────────────────────────────────────────────


def resolver_fecha(valor: str, hoy: date | None = None) -> date:
    """"hoy" / "hace_N_dias" / "en_N_dias" / "AAAA-MM-DD" → date."""
    hoy = hoy or timezone.localdate()
    if valor == "hoy":
        return hoy
    if valor.startswith("hace_") and valor.endswith("_dias"):
        return hoy - timedelta(days=int(valor[5:-5]))
    if valor.startswith("en_") and valor.endswith("_dias"):
        return hoy + timedelta(days=int(valor[3:-5]))
    return date.fromisoformat(valor)


def _q_filtro(Modelo, entidad: str, f: dict, hoy: date) -> Q:
    spec = ENTIDADES[entidad]["campos"][f["campo"]]
    tipo = spec["tipo"]
    ruta = ruta_de(entidad, f["campo"])
    op = f["op"]

    if op == "vacio":
        vacio = Q(**{f"{ruta}__isnull": True})
        if tipo == "texto":
            vacio |= Q(**{ruta: ""})
        return vacio if f["valor"] else ~vacio

    lookup = _LOOKUP[op]

    if "campo_ref" in f:
        ruta_ref = ruta_de(entidad, f["campo_ref"])
        izq, der = ruta, F(ruta_ref)
        if tipo == "fecha":
            dt_izq, dt_der = _es_datetime(Modelo, ruta), _es_datetime(Modelo, ruta_ref)
            if dt_izq != dt_der:  # una fecha contra un momento: se comparan días
                if dt_izq:
                    izq = f"{ruta}__date"
                else:
                    der = TruncDate(ruta_ref)
        return Q(**{f"{izq}__{lookup}": der})

    valor = f["valor"]
    if tipo == "fecha":
        valor = [resolver_fecha(v, hoy) for v in valor] if op == "in" else resolver_fecha(valor, hoy)
        if _es_datetime(Modelo, ruta):
            ruta = f"{ruta}__date"
    clave = f"{ruta}__{lookup}" if lookup != "exact" else ruta
    return Q(**{clave: valor})


def _aplicar_filtros(qs, Modelo, entidad: str, filtros: list[dict], hoy: date):
    # Un .filter() por filtro, como v1 (mismo SQL para las definiciones viejas).
    for f in filtros:
        qs = qs.filter(_q_filtro(Modelo, entidad, f, hoy))
    return qs


def _aplicar_alcance(qs, entidad: str, alcance_usuario: str, usuario):
    if alcance_usuario != "mio" or usuario is None:
        return qs
    cfg = ENTIDADES[entidad]
    if cfg["campo_autor"]:
        return qs.filter(**{cfg["campo_autor"]: usuario})
    if cfg["campo_asignado"]:
        return qs.filter(**{cfg["campo_asignado"]: usuario}).distinct()
    return qs


# ── Cálculo ──────────────────────────────────────────────────────────────────


def _formatear_valor(valor: Any, agregacion: str) -> Any:
    """La forma v1: count → int; lo demás → float a 2 decimales; nada → 0."""
    if valor is None:
        return 0
    if agregacion == "count":
        return int(valor)
    # Sum/Avg pueden devolver Decimal — convertir a float redondeado.
    try:
        return round(float(valor), 2)
    except (TypeError, ValueError):
        return valor


def _a_numero(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int | float | Decimal):
        return float(valor)
    return None


def _acotar(qs, Modelo) -> tuple[Any, int]:
    """Los `MAX_FILAS_PRE_AGREGACION` más recientes, como queryset limpio (sin
    joins de los filtros), y cuántas filas había en total."""
    pks = list(qs.order_by("-pk").values_list("pk", flat=True)[:MAX_FILAS_PRE_AGREGACION + 1])
    total = len(pks)
    if total > MAX_FILAS_PRE_AGREGACION:
        total = qs.count()
        pks = pks[:MAX_FILAS_PRE_AGREGACION]
    return Modelo._default_manager.filter(pk__in=pks), total


def _dias_entre(desde: Any, hasta: Any, unidad: str) -> float | None:
    if desde is None or hasta is None:
        return None
    if isinstance(desde, datetime) != isinstance(hasta, datetime):
        # Una fecha contra un momento: se comparan días calendario (hora local).
        if isinstance(desde, datetime):
            desde = timezone.localtime(desde).date() if timezone.is_aware(desde) else desde.date()
        if isinstance(hasta, datetime):
            hasta = timezone.localtime(hasta).date() if timezone.is_aware(hasta) else hasta.date()
    segundos = (hasta - desde).total_seconds()
    return segundos / {"dias": 86400, "horas": 3600, "minutos": 60}[unidad]


def _agregar_py(valores: list[float], agregacion: str) -> float | None:
    if not valores:
        return None
    if agregacion == "sum":
        return sum(valores)
    if agregacion == "avg":
        return sum(valores) / len(valores)
    if agregacion == "min":
        return min(valores)
    return max(valores)


class _Calculo:
    """Una definición normalizada contra un rango de fechas."""

    def __init__(self, n: dict, usuario, hoy: date):
        self.n = n
        self.entidad = n["entidad"]
        self.cfg = ENTIDADES[self.entidad]
        self.Modelo = _modelo_django(self.entidad)
        self.usuario = usuario
        self.hoy = hoy
        self.truncado_de = 0  # total de filas si se acotó

    def queryset(self, rango: tuple[date | None, date | None], *, numerador: bool = False):
        n = self.n
        qs = self.Modelo._default_manager.all()
        qs = _aplicar_filtros(qs, self.Modelo, self.entidad, n["filtros"], self.hoy)
        if numerador:
            qs = _aplicar_filtros(qs, self.Modelo, self.entidad, n["filtros_numerador"], self.hoy)
        campo_fecha = n.get("campo_fecha") or self.cfg["campo_fecha"]
        if campo_fecha and n["ventana_tiempo"] != "siempre":
            qs = _aplicar_rango(qs, self.Modelo, ruta_de(self.entidad, campo_fecha), *rango)
        return _aplicar_alcance(qs, self.entidad, n["alcance_usuario"], self.usuario)

    # — un número —

    def agregado(self, qs) -> Any:
        """El número crudo (int/Decimal/float/None) de un queryset."""
        n = self.n
        if n.get("duracion"):
            return _agregar_py(list(self._duraciones(qs, agrupar=None).get(None, [])),
                               n["agregacion"])
        if n["agregacion"] == "count":
            return qs.count()
        # Cost guard: nunca agregamos sobre más de MAX_FILAS_PRE_AGREGACION.
        # PKs limitados → re-filtramos por __in para preservar SQL-level agg.
        acotado, total = _acotar(qs, self.Modelo)
        self._anotar_total(total)
        campo = ruta_de(self.entidad, n["campo"])
        return acotado.aggregate(v=_AGG[n["agregacion"]](campo))["v"]

    def _anotar_total(self, total: int) -> None:
        if total > MAX_FILAS_PRE_AGREGACION:
            self.truncado_de = max(self.truncado_de, total)

    def _duraciones(self, qs, agrupar: str | None) -> dict[Any, list[float]]:
        """{grupo: [duración, …]} sobre las filas más recientes (acotadas)."""
        d = self.cfg["duraciones"][self.n["duracion"]]
        r_desde, r_hasta = ruta_de(self.entidad, d["desde"]), ruta_de(self.entidad, d["hasta"])
        qs = qs.filter(**{f"{r_desde}__isnull": False, f"{r_hasta}__isnull": False})
        acotado, total = _acotar(qs, self.Modelo)
        self._anotar_total(total)
        columnas = [r_desde, r_hasta] + ([agrupar] if agrupar else [])
        salida: dict[Any, list[float]] = {}
        for fila in acotado.order_by().values_list(*columnas):
            valor = _dias_entre(fila[0], fila[1], d["unidad"])
            if valor is not None:
                salida.setdefault(fila[2] if agrupar else None, []).append(valor)
        return salida

    # — por grupo —

    def por_grupo(self, qs) -> dict[Any, Any]:
        """{valor_del_grupo: número crudo}."""
        n = self.n
        ruta_g = self.cfg["agrupaciones"][n["agrupar_por"]]["ruta"]
        if n.get("duracion"):
            return {
                g: _agregar_py(vs, n["agregacion"])
                for g, vs in self._duraciones(qs, agrupar=ruta_g).items()
            }
        if n["agregacion"] == "count":
            base = self.Modelo._default_manager.filter(pk__in=qs.values("pk"))
            expr = Count("pk", distinct=True)
        else:
            base, total = _acotar(qs, self.Modelo)
            self._anotar_total(total)
            expr = _AGG[n["agregacion"]](ruta_de(self.entidad, n["campo"]))
        filas = base.order_by().values(ruta_g).annotate(v=expr)
        return {fila[ruta_g]: fila["v"] for fila in filas}


def _etiquetas_grupo(Modelo, entidad: str, clave_grupo: str, valores: list) -> dict:
    """Nombre legible de cada valor de grupo (cliente → razón social, etc.)."""
    cfg = ENTIDADES[entidad]
    ruta = cfg["agrupaciones"][clave_grupo]["ruta"]
    campo = _campo_modelo(Modelo, ruta)
    presentes = [v for v in valores if v is not None]
    etiquetas: dict = {}
    if campo.is_relation and campo.related_model is not None:
        for pk, obj in campo.related_model._default_manager.in_bulk(presentes).items():
            etiquetas[pk] = getattr(obj, "nombre_completo", "") or getattr(obj, "email", "") or str(obj)
    elif getattr(campo, "choices", None):
        etiquetas = {k: str(v) for k, v in campo.flatchoices}
    else:
        catalogo = next(
            (s.get("catalogo") for c, s in cfg["campos"].items()
             if s.get("catalogo") and ruta_de(entidad, c) == ruta),
            None,
        )
        if catalogo:
            etiquetas = dict(
                apps.get_model(catalogo)._default_manager
                .filter(slug__in=presentes).values_list("slug", "label"),
            )
        elif campo.get_internal_type() == "BooleanField":
            etiquetas = {True: "Sí", False: "No"}
    sin = f"Sin {cfg['agrupaciones'][clave_grupo]['etiqueta']}"
    return {v: (sin if v is None else etiquetas.get(v, str(v))) for v in valores}


def _cambio_pct(actual: float | None, anterior: float | None) -> float | None:
    """Sin base no hay cambio: `None`, nunca un 0 % inventado."""
    if actual is None or anterior is None or anterior == 0:
        return None
    return round((actual - anterior) / abs(anterior) * 100, 1)


def _puede_ver(usuario, permisos: tuple[str, ...]) -> bool:
    from lib.permisos import es_super_admin, puede

    if not permisos or es_super_admin(usuario):
        return True
    return all(puede(usuario, *p.split(".", 1)) for p in permisos)


def ejecutar(definicion: dict, usuario=None, *, validado: bool = False) -> dict:
    """Ejecuta una definición DSL. Si `validado=False`, la valida primero.

    Retorna `{valor, numero, nota, link, formato, direccion}` —la forma de los
    KPIs del catálogo, más el número crudo y cómo pintarlo— y, si la definición
    lo pide, `grupos: [{pk, etiqueta, valor}]` y `comparacion: {anterior,
    cambio_pct, desde, hasta}`. `valor` es SIEMPRE un número (o «—» si no hay
    con qué medir): la tarjeta formatea.

    En caso de ValidacionError la deja propagar (el caller decide si la
    captura como 'error'). Sin permiso para el dato: `valor «—», nota «sin
    permiso»`. En caso de error transitorio del ORM, devuelve
    `{valor: '—', nota: 'error', link: ...}` y loggea.
    """
    n = definicion if validado else validar(definicion)
    cfg = ENTIDADES[n["entidad"]]
    meta = metadatos_de(n)

    if usuario is not None and not _puede_ver(usuario, permisos_de(n)):
        return {"valor": SIN_NUMERO, "numero": None, "nota": "sin permiso", "link": "",
                **meta, "sin_permiso": True}

    # Las definiciones v1 (sin duración ni porcentaje) conservan su forma:
    # sin filas, count/sum dan 0, no «—».
    forma_v1 = not n.get("duracion") and n.get("tipo") != "porcentaje"
    hoy = timezone.localdate()
    calc: _Calculo | None = None

    def numero_de(crudo_num, crudo_den=None) -> Any:
        if n.get("tipo") == "porcentaje":
            den = _a_numero(crudo_den)
            if not den:
                return SIN_NUMERO
            return round((_a_numero(crudo_num) or 0.0) / den * 100, 2)
        if forma_v1:
            return _formatear_valor(crudo_num, n["agregacion"])
        num = _a_numero(crudo_num)
        return SIN_NUMERO if num is None else round(num, 2)

    def medir(rango) -> Any:
        assert calc is not None
        qs = calc.queryset(rango)
        if n.get("tipo") == "porcentaje":
            return numero_de(calc.agregado(calc.queryset(rango, numerador=True)), calc.agregado(qs))
        return numero_de(calc.agregado(qs))

    try:
        # Dentro del try: en una app sin el modelo instalado (p. ej. La Gerencia
        # no trae `recados`) get_model truena y eso es un «error», no un 500.
        calc = _Calculo(n, usuario, hoy)
        rango = _ventana_a_rango(n["ventana_tiempo"], hoy)
        valor = medir(rango)
        salida: dict[str, Any] = {
            "valor": valor,
            "numero": _a_numero(valor),
            "nota": "",
            "link": cfg["link_default"],
            **meta,
        }
        if n.get("agrupar_por"):
            salida["grupos"] = _grupos(calc, rango, numero_de)
        if n.get("comparar"):
            anterior = ventana_anterior(n["ventana_tiempo"], hoy)
            valor_ant = medir(anterior) if anterior else SIN_NUMERO
            salida["comparacion"] = {
                "anterior": _a_numero(valor_ant),
                "cambio_pct": _cambio_pct(_a_numero(valor), _a_numero(valor_ant)),
                "desde": anterior[0].isoformat() if anterior else None,
                "hasta": anterior[1].isoformat() if anterior else None,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("kpi_dsl ejecutar fallo entidad=%s agg=%s: %s",
                       n["entidad"], n["agregacion"], exc)
        return {"valor": SIN_NUMERO, "numero": None, "nota": "error",
                "link": cfg["link_default"], **meta}

    if calc.truncado_de:
        salida["nota"] = f"sobre {MAX_FILAS_PRE_AGREGACION} más recientes (de {calc.truncado_de})"
    return salida


def _grupos(calc: _Calculo, rango, numero_de) -> list[dict]:
    n = calc.n
    qs = calc.queryset(rango)
    if n.get("tipo") == "porcentaje":
        den = calc.por_grupo(qs)
        num = calc.por_grupo(calc.queryset(rango, numerador=True))
        valores = {g: numero_de(num.get(g), d) for g, d in den.items()}
    else:
        valores = {g: numero_de(v) for g, v in calc.por_grupo(qs).items()}
    etiquetas = _etiquetas_grupo(calc.Modelo, calc.entidad, n["agrupar_por"], list(valores))

    def orden(item):
        g, v = item
        numero = _a_numero(v)
        return (numero is None, -(numero or 0.0), etiquetas[g])

    top = n.get("top", TOP_GRUPOS_DEFAULT)
    return [
        {"pk": g, "etiqueta": etiquetas[g], "valor": v}
        for g, v in sorted(valores.items(), key=orden)[:top]
    ]


def ejecutar_con_preview(definicion: dict, *, usuario=None) -> dict:
    """Variante para el flujo de creación — devuelve también detalles de debug:
    la definición normalizada, su frase en español y los permisos que pide."""
    from .ui import describir

    try:
        normalizada = validar(definicion)
    except ValidacionError as exc:
        return {"ok": False, "error": str(exc)}
    resultado = ejecutar(normalizada, usuario=usuario, validado=True)
    return {
        "ok": True,
        "resultado": resultado,
        "definicion_normalizada": normalizada,
        "descripcion": describir(normalizada),
        "permisos": permisos_de(normalizada),
    }
