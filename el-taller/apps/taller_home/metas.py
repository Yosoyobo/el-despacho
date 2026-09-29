"""Metas de KPIs: cuánto se lleva, cuánto se esperaba a estas alturas y si va
en riesgo (S-KPIs-V2, 2026-09-29).

Oscar pidió cuatro cosas de las metas, y aquí viven todas:

1. **Proporcional al periodo.** El día 15 de un mes de 30, llevar la mitad de
   la meta de ingresos es ir bien. Sólo aplica a los KPIs que vuelven a cero
   cada periodo (`KPI.acumula`); un saldo («cuentas por cobrar») se juzga al
   corte, contra la meta entera.
2. **Saber si bajar es mejor.** Con `direccion="baja"` la meta es un TECHO:
   «cuentas por cobrar ≤ 100 mil», «gastos del mes ≤ 80 mil» (éste, además,
   proporcional: gastar el 80% del presupuesto el día 5 es ir mal).
3. **Por persona o por cliente.** Una meta de persona se mide con el número de
   esa persona (un KPI personal calculado como ella, o su parte del
   `desglose`); una de cliente, con la parte de ese cliente.
4. **Avisar si va en riesgo.** `avisar_en_riesgo()` (cron diario,
   `manage.py kpi_metas_avisar`) manda UN aviso por periodo por El Interfón a
   la persona de la meta o, si es del despacho o de un cliente, a quien tiene
   `kpis.configurar`.

Nada de esto usa IA: son reglas sobre el número, la meta y el calendario.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date

logger = logging.getLogger(__name__)

# Qué tanto se puede ir por detrás de lo esperado antes de llamarlo riesgo.
TOLERANCIA = 0.15
# Antes de este avance del periodo no se declara riesgo en una meta
# proporcional: el día 2 del mes cualquier cosa parece atrasada.
AVANCE_MINIMO_PARA_JUZGAR = 0.2

ESTADOS = {
    "cumplida": "Cumplida",
    "en_camino": "En camino",
    "en_riesgo": "En riesgo",
    "excedida": "Se pasó",
    "sin_datos": "Sin datos",
}


# ── El calendario ────────────────────────────────────────────────────────

def avance_periodo(acumula: str, hoy: date | None = None) -> float:
    """Qué fracción del periodo ya pasó (1.0 = completo). Un saldo: 1.0."""
    hoy = hoy or date.today()
    if acumula == "semana":
        return (hoy.weekday() + 1) / 7
    if acumula == "mes":
        return hoy.day / calendar.monthrange(hoy.year, hoy.month)[1]
    if acumula == "ano":
        dias = 366 if calendar.isleap(hoy.year) else 365
        return hoy.timetuple().tm_yday / dias
    return 1.0


def clave_periodo(acumula: str, hoy: date | None = None) -> str:
    """Identifica el periodo en curso (para avisar una sola vez por periodo).

    Un saldo no tiene periodo propio: se avisa a lo más una vez por semana."""
    hoy = hoy or date.today()
    if acumula == "dia":
        return hoy.isoformat()
    if acumula == "mes":
        return f"{hoy.year}-{hoy.month:02d}"
    if acumula == "ano":
        return str(hoy.year)
    anio, semana, _ = hoy.isocalendar()
    return f"{anio}-S{semana:02d}"


def periodo_de(kpi) -> str:
    """El `MetaKPI.periodo` que le toca a una meta sobre `kpi`."""
    return kpi.acumula or "corte"


# ── El juicio ────────────────────────────────────────────────────────────

def evaluar(meta: float, numero: float | None, *, direccion: str = "sube",
            acumula: str = "", hoy: date | None = None) -> dict:
    """Cómo va un número contra su meta. Función pura (sin base de datos).

    Devuelve `{estado, etiqueta, avance_pct, avance_clamp, esperado, fraccion}`:
    - `avance_pct`: con «sube», cuánto de la meta se lleva; con «baja», qué
      tanto del techo se ha usado (100% = en el techo).
    - `esperado`: lo que se esperaba llevar HOY (proporcional si acumula).
    """
    fraccion = avance_periodo(acumula, hoy) if acumula else 1.0
    esperado = meta * fraccion
    base = {"fraccion": round(fraccion, 3), "esperado": esperado, "meta": meta}
    if numero is None or meta <= 0:
        return {**base, "estado": "sin_datos", "etiqueta": ESTADOS["sin_datos"],
                "avance_pct": None, "avance_clamp": 0}

    avance = numero / meta * 100
    salida = {**base, "avance_pct": round(avance, 1),
              "avance_clamp": max(0, min(100, round(avance)))}
    juzgable = (not acumula) or fraccion >= AVANCE_MINIMO_PARA_JUZGAR

    if direccion == "baja":
        if numero > meta:
            estado = "excedida"
        elif acumula and juzgable and numero > esperado * (1 + TOLERANCIA):
            estado = "en_riesgo"
        elif not acumula and numero > meta * (1 - TOLERANCIA):
            # Un saldo pegado al techo: todavía no se pasa, pero casi.
            estado = "en_riesgo"
        else:
            estado = "cumplida" if not acumula else "en_camino"
    else:
        if numero >= meta:
            estado = "cumplida"
        elif juzgable and numero < esperado * (1 - TOLERANCIA):
            estado = "en_riesgo"
        else:
            estado = "en_camino"
    return {**salida, "estado": estado, "etiqueta": ESTADOS[estado]}


def en_riesgo(evaluacion: dict) -> bool:
    return evaluacion.get("estado") in ("en_riesgo", "excedida")


# ── El número de cada meta ───────────────────────────────────────────────

def actor_despacho():
    """Con qué mirada se calcula «el número del despacho»: la más amplia."""
    from cuentas.models.usuario import Usuario
    from lib.permisos import usuarios_con_rol

    return usuarios_con_rol("super_admin").order_by("pk").first() or Usuario.objects.filter(
        is_active=True,
    ).order_by("pk").first()


class _Calculadora:
    """Calcula cada KPI (y cada desglose) una sola vez por corrida."""

    def __init__(self):
        self._actor = None
        self._valores: dict = {}
        self._desgloses: dict = {}

    def actor(self):
        if self._actor is None:
            self._actor = actor_despacho()
        return self._actor

    def valor(self, kpi, usuario) -> float | None:
        from .kpi_valor import numero_del_resultado

        clave = (kpi.slug, getattr(usuario, "pk", None))
        if clave not in self._valores:
            try:
                self._valores[clave] = numero_del_resultado(kpi.calcular(usuario))
            except Exception:  # noqa: BLE001 — un KPI roto no tumba las metas
                logger.warning("meta: %s no se pudo calcular", kpi.slug, exc_info=True)
                self._valores[clave] = None
        return self._valores[clave]

    def desglose(self, kpi, ambito: str) -> dict:
        clave = (kpi.slug, ambito)
        if clave not in self._desgloses:
            try:
                self._desgloses[clave] = kpi.desglose(ambito) if kpi.desglose else {}
            except Exception:  # noqa: BLE001
                logger.warning("meta: desglose %s/%s falló", kpi.slug, ambito, exc_info=True)
                self._desgloses[clave] = {}
        return self._desgloses[clave]


def numero_de_meta(meta, kpi, calc: _Calculadora | None = None) -> float | None:
    """El número contra el que se mide `meta` (según su ámbito)."""
    calc = calc or _Calculadora()
    if meta.ambito == "persona":
        if meta.usuario is None:
            return None
        if kpi.personal:
            return calc.valor(kpi, meta.usuario)
        parte = calc.desglose(kpi, "persona")
        return float(parte.get(meta.usuario_id, 0)) if parte is not None else None
    if meta.ambito == "cliente":
        if meta.cliente_id is None:
            return None
        parte = calc.desglose(kpi, "cliente")
        return float(parte.get(meta.cliente_id, 0)) if parte is not None else None
    actor = calc.actor()
    return calc.valor(kpi, actor) if actor else None


def _direccion(kpi, configs: dict) -> str:
    cfg = configs.get(kpi.slug)
    return (cfg.direccion if cfg and cfg.direccion else "") or kpi.direccion


def estado_de_metas(*, activas_solo: bool = True, hoy: date | None = None,
                    filtro=None) -> list[dict]:
    """Todas las metas con su estado de hoy. Para La Gerencia, El Chalán y el
    aviso diario. `filtro(meta) -> bool` acota (p. ej. las de una persona)."""
    from .kpi_valor import formatear
    from .kpis import kpi_por_slug
    from .models import ConfigKPI, MetaKPI

    configs = {c.kpi_slug: c for c in ConfigKPI.objects.all()}
    qs = MetaKPI.objects.select_related("usuario", "cliente")
    if activas_solo:
        qs = qs.filter(activa=True)
    calc = _Calculadora()
    salida = []
    for meta in qs:
        if filtro is not None and not filtro(meta):
            continue
        kpi = kpi_por_slug(meta.kpi_slug)
        if kpi is None:
            continue
        numero = numero_de_meta(meta, kpi, calc)
        direccion = _direccion(kpi, configs)
        ev = evaluar(float(meta.valor), numero, direccion=direccion,
                     acumula=kpi.acumula, hoy=hoy)
        salida.append({
            "meta": meta, "kpi": kpi, "numero": numero, "direccion": direccion,
            "evaluacion": ev,
            "quien": _quien(meta),
            "valor_txt": formatear(numero, kpi.formato),
            "meta_txt": formatear(float(meta.valor), kpi.formato),
            "esperado_txt": formatear(ev["esperado"], kpi.formato),
        })
    return salida


def _quien(meta) -> str:
    if meta.ambito == "persona" and meta.usuario is not None:
        u = meta.usuario
        return (u.get_full_name() or "").strip() or u.email
    if meta.ambito == "cliente" and meta.cliente is not None:
        return str(meta.cliente)
    return "Todo el despacho"


# ── Las metas que se pintan en una tarjeta ───────────────────────────────

def meta_para_tarjeta(user, kpi, numero: float | None, *, metas: list | None = None,
                      direccion: str | None = None, hoy: date | None = None) -> dict | None:
    """La meta que le toca ver a `user` en la tarjeta de `kpi`, ya evaluada.

    - KPI personal → la meta de ESA persona.
    - KPI del despacho → la meta del despacho; salvo que `user` sólo vea sus
      proyectos y el KPI esté acotado (su número no es el del despacho).
    `metas` permite pasar las metas activas ya cargadas (una consulta por
    tablero, no una por tarjeta).
    """
    from lib.permisos import solo_proyectos_asignados

    from .kpi_valor import formatear

    if metas is None:
        from .models import MetaKPI
        metas = list(MetaKPI.objects.filter(activa=True, kpi_slug=kpi.slug))
    candidatas = [m for m in metas if m.kpi_slug == kpi.slug]
    if kpi.personal:
        meta = next((m for m in candidatas if m.ambito == "persona"
                     and m.usuario_id == getattr(user, "pk", None)), None)
    else:
        if kpi.acotado and solo_proyectos_asignados(user):
            return None
        meta = next((m for m in candidatas if m.ambito == "despacho"), None)
    if meta is None:
        return None
    ev = evaluar(float(meta.valor), numero, direccion=direccion or kpi.direccion,
                 acumula=kpi.acumula, hoy=hoy)
    return {
        **ev,
        "meta_txt": formatear(float(meta.valor), kpi.formato),
        "esperado_txt": formatear(ev["esperado"], kpi.formato),
        "proporcional": bool(kpi.acumula),
        "color": {"cumplida": "success", "en_camino": "brand", "en_riesgo": "warning",
                  "excedida": "error"}.get(ev["estado"], "gray"),
    }


# ── El aviso ─────────────────────────────────────────────────────────────

def destinatarios(meta):
    """A quién se le avisa: la persona de la meta; si no, quien configura KPIs."""
    from cuentas.models.usuario import Usuario
    from lib.permisos import puede_configurar_kpis

    if meta.ambito == "persona":
        return [meta.usuario] if meta.usuario and meta.usuario.is_active else []
    return [u for u in Usuario.objects.filter(is_active=True).order_by("pk")
            if puede_configurar_kpis(u)]


def _texto_aviso(fila: dict) -> tuple[str, str]:
    kpi, ev = fila["kpi"], fila["evaluacion"]
    titulo = f"Meta en riesgo: {kpi.titulo}"
    if fila["meta"].ambito != "despacho":
        titulo += f" · {fila['quien']}"
    if ev["estado"] == "excedida":
        cuerpo = f"Va en {fila['valor_txt']} y el tope era {fila['meta_txt']}."
    elif fila["direccion"] == "baja":
        cuerpo = (f"Va en {fila['valor_txt']}; a estas alturas lo sano era no pasar de "
                  f"{fila['esperado_txt']} (tope {fila['meta_txt']}).")
    elif kpi.acumula:
        cuerpo = (f"Va en {fila['valor_txt']}; a estas alturas se esperaba "
                  f"{fila['esperado_txt']} (meta {fila['meta_txt']}).")
    else:
        cuerpo = f"Va en {fila['valor_txt']} contra una meta de {fila['meta_txt']}."
    return titulo, cuerpo


def avisar_en_riesgo(*, hoy: date | None = None, dry_run: bool = False) -> list[dict]:
    """Avisa (una vez por periodo) cada meta que va en riesgo. Devuelve lo avisado."""
    from lib.interfono import enviar_a_usuario
    from lib.portavoz import emitir
    from lib.portavoz_eventos import EventoPortavoz

    hoy = hoy or date.today()
    avisadas = []
    for fila in estado_de_metas(hoy=hoy):
        if not en_riesgo(fila["evaluacion"]):
            continue
        meta, kpi = fila["meta"], fila["kpi"]
        periodo = clave_periodo(kpi.acumula, hoy)
        if meta.avisado_periodo == periodo:
            continue
        titulo, cuerpo = _texto_aviso(fila)
        para = destinatarios(meta)
        avisadas.append({"meta_id": meta.pk, "slug": kpi.slug, "titulo": titulo,
                         "cuerpo": cuerpo, "para": [u.pk for u in para]})
        if dry_run:
            continue
        for usuario in para:
            try:
                enviar_a_usuario(usuario, titulo, cuerpo, url="/analisis/",
                                 tag=f"meta-kpi-{meta.pk}", categoria="metas_kpi",
                                 origen_modulo="metas_kpi", origen_id=meta.pk)
            except Exception:  # noqa: BLE001 — un push fallido no detiene al resto
                logger.warning("aviso de meta %s a %s falló", meta.pk, usuario.pk, exc_info=True)
        meta.avisado_periodo = periodo
        meta.save(update_fields=["avisado_periodo"])
        try:
            emitir(EventoPortavoz(
                tipo="meta_kpi.en_riesgo", actor_id=None, actor_email=None,
                payload={"meta_id": meta.pk, "kpi_slug": kpi.slug, "ambito": meta.ambito,
                         "estado": fila["evaluacion"]["estado"], "valor": fila["numero"],
                         "meta": float(meta.valor), "periodo": periodo},
            ))
        except Exception:  # noqa: BLE001
            logger.warning("no se pudo emitir meta_kpi.en_riesgo", exc_info=True)
    return avisadas
