"""El Chalán como analista: qué mirar hoy, qué meta ponerse y qué falta medir.

Tres trabajos, y el primero es el que más valor da:

1. **Curar.** De los ~70 indicadores del catálogo, decir cuáles importan HOY.
   El dato que originó esto: los dos usuarios activos tenían 72 preferencias
   guardadas y casi todas eran para APAGAR indicadores. El problema no era que
   faltaran números, era que sobraban. Un analista no entrega cincuenta cifras:
   entrega las cinco que hay que ver esta mañana, y dice por qué.

2. **Proponer metas.** La tabla de metas llevaba meses vacía, y sin meta el
   sistema describe pero no juzga. Con la memoria de los indicadores ya se puede
   proponer una meta realista: lo que se ha hecho, y un poco más.

3. **Proponer indicadores nuevos.** Sólo cuando el negocio muestra algo que
   ningún número existente cubre. Se apoya en el mecanismo de sugerencias que ya
   funcionaba (6 de 10 aceptadas), no en uno nuevo.

Lo importante: **nada de esto se activa solo**. Se propone y una persona decide,
igual que con las acciones. Y la elección de qué mirar hoy es determinista —sale
de reglas sobre la propia historia de cada indicador, no de una llamada a la IA—
así que puede correr a diario sin costar nada.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Cuántos indicadores se destacan por día. Más de esto y volvemos al problema
# original: un tablero que nadie lee.
CUANTOS_DESTACAR = 5


def _cfg():
    from ajustes.models import ConfiguracionAnalisis
    return ConfiguracionAnalisis.obtener()


def _razon_y_peso(kpi, valor, resumen, cfg) -> tuple[str, float]:
    """Por qué este indicador merece mirarse hoy, y qué tan urgente es.

    El peso ordena; la razón es lo que se le muestra a la persona. Un número sin
    el porqué obliga a adivinar, y adivinar es lo que hace que la gente apague
    el tablero.
    """
    nota = (resumen or {}).get("nota") or ""
    anomalia = (resumen or {}).get("anomalia") or {}
    comparacion = (resumen or {}).get("comparacion") or {}

    # 1. Lo que el propio KPI marca como alerta pesa más que cualquier otra cosa.
    if nota == "alerta":
        return "está en alerta", 100.0

    # 2. Lo que se salió de su comportamiento normal.
    if anomalia.get("raro"):
        direccion = "arriba" if anomalia["motivo"] == "arriba" else "abajo"
        return (
            f"se salió de lo normal: {abs(anomalia['desviacion_pct']):.0f}% {direccion} "
            f"de lo habitual",
            90.0 + min(abs(anomalia["desviacion_pct"]) / 10, 9),
        )

    # 3. Un cambio fuerte contra el periodo anterior.
    cambio = comparacion.get("cambio_pct")
    if cambio is not None and abs(cambio) >= 25:
        verbo = "subió" if cambio > 0 else "bajó"
        return f"{verbo} {abs(cambio):.0f}% contra el periodo anterior", 70.0 + min(abs(cambio) / 10, 15)

    # 4. Una meta en riesgo.
    meta = (resumen or {}).get("meta")
    if meta and meta.get("en_riesgo"):
        return f"vas al {meta['avance_pct']:.0f}% de tu meta", 80.0

    return "", 0.0


def destacados_de_hoy(usuario, *, cuantos: int = CUANTOS_DESTACAR) -> list[dict]:
    """Los pocos indicadores que hoy merecen la mirada de esta persona.

    Determinista y sin IA: se apoya en la alerta que el propio indicador
    levanta, en su historia y en la meta. Devuelve `[{kpi, valor, razon}]`.
    """
    from apps.taller_home import series
    from apps.taller_home.kpis import kpis_aplicables_a_rol
    from apps.taller_home.models import MetaKPI

    cfg = _cfg()
    metas = {m.kpi_slug: m for m in MetaKPI.objects.filter(activa=True)}
    candidatos: list[dict] = []

    for kpi in kpis_aplicables_a_rol(getattr(usuario, "rol", ""), user=usuario):
        try:
            r = kpi.calcular(usuario)
        except Exception:  # noqa: BLE001
            continue
        valor = r.get("valor")
        if isinstance(valor, str):
            continue

        resumen = {
            "nota": r.get("nota"),
            "anomalia": series.es_raro(kpi.slug, valor),
            "comparacion": series.comparar(kpi.slug),
        }
        meta = metas.get(kpi.slug)
        if meta and meta.valor:
            try:
                avance = float(valor) / float(meta.valor) * 100
                resumen["meta"] = {"avance_pct": avance, "en_riesgo": avance < 70}
            except Exception:  # noqa: BLE001
                pass

        razon, peso = _razon_y_peso(kpi, valor, resumen, cfg)
        if not razon:
            continue
        candidatos.append({
            "slug": kpi.slug, "titulo": kpi.titulo, "categoria": kpi.categoria,
            "valor": valor, "nota": r.get("nota") or "", "link": r.get("link") or "",
            "razon": razon, "peso": peso,
            "tendencia": series.tendencia(kpi.slug),
        })

    candidatos.sort(key=lambda c: -c["peso"])
    return candidatos[:cuantos]


def sobran(usuario, *, dias_quieto: int = 30) -> list[dict]:
    """Indicadores que llevan mucho sin moverse: candidatos a apagar.

    Un número que marca lo mismo todos los días no informa, sólo ocupa lugar.
    """
    from apps.taller_home import series
    from apps.taller_home.kpis import kpis_aplicables_a_rol
    from apps.taller_home.models import PreferenciaKPI

    ya_ocultos = set(
        PreferenciaKPI.objects.filter(usuario=usuario, visible=False)
        .values_list("kpi_slug", flat=True)
    )
    quietos = []
    for kpi in kpis_aplicables_a_rol(getattr(usuario, "rol", ""), user=usuario):
        if kpi.slug in ya_ocultos:
            continue
        historia = series.serie(kpi.slug, dias=dias_quieto)
        if len(historia) < 10:
            continue
        valores = {h["valor"] for h in historia}
        if len(valores) == 1:
            quietos.append({
                "slug": kpi.slug, "titulo": kpi.titulo,
                "razon": f"lleva {len(historia)} días marcando lo mismo",
            })
    return quietos


# ── Metas propuestas ─────────────────────────────────────────────────────

# Sólo tiene sentido ponerle meta a lo que se persigue. A un conteo de errores
# no se le pone meta: se le pone alerta, que ya existe.
SLUGS_CON_META = (
    "ingresos-mes", "utilidad-mes", "facturado-mes", "margen-real",
    "conversion-oportunidades", "cotizaciones-aprobadas-mes",
    "mandados-entregados-semana", "horas-equipo-semana",
)


def proponer_metas(*, solo_faltantes: bool = True) -> list[dict]:
    """Metas realistas a partir de lo que de verdad se ha hecho.

    No las guarda: las devuelve para que una persona las apruebe.
    """
    from apps.taller_home import series
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.models import MetaKPI

    ya_con_meta = set(MetaKPI.objects.values_list("kpi_slug", flat=True))
    propuestas = []
    for slug in SLUGS_CON_META:
        if solo_faltantes and slug in ya_con_meta:
            continue
        kpi = kpi_por_slug(slug)
        if kpi is None:
            continue
        m = series.meta_sugerida(slug)
        if not m.get("hay_datos"):
            continue
        propuestas.append({
            "slug": slug, "titulo": kpi.titulo,
            "sugerida": m["sugerida"], "tipico": m["tipico"],
            "mejor": m["mejor"], "muestras": m["muestras"],
            "razon": (
                f"en los últimos meses ronda {m['tipico']:,.0f} "
                f"(su mejor día: {m['mejor']:,.0f})"
            ),
        })
    return propuestas


# ── Indicadores que faltan ───────────────────────────────────────────────

def proponer_indicadores(usuario) -> list[dict]:
    """Qué convendría empezar a medir, mirando lo que el negocio muestra.

    Reglas sobre hechos, no invención: si hay gastos sin proveedor, conviene
    vigilarlos; si el margen real anda flojo, conviene tenerlo a la vista. Cada
    propuesta apunta a un indicador que YA existe en el catálogo pero que esta
    persona no está viendo — que es la forma barata y honesta de "proponer":
    no inventar métricas, sino destapar la que hacía falta.
    """
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.models import PreferenciaKPI
    from apps.taller_home.negocio import hechos_de

    ocultos = set(
        PreferenciaKPI.objects.filter(usuario=usuario, visible=False)
        .values_list("kpi_slug", flat=True)
    )
    propuestas: list[dict] = []

    def sugerir(slug: str, razon: str):
        if slug in ocultos:
            return
        kpi = kpi_por_slug(slug)
        if kpi is None:
            return
        propuestas.append({"slug": slug, "titulo": kpi.titulo, "razon": razon})

    try:
        perdidos = hechos_de("perdidos").get("metricas") or {}
        if (perdidos.get("cotizaciones_perdidas") or 0) > 0:
            sugerir("conversion-oportunidades",
                    "ya hay cotizaciones perdidas: conviene vigilar la conversión")
        if perdidos.get("enfriadas"):
            sugerir("cotizaciones-enfriadas",
                    f"{len(perdidos['enfriadas'])} propuestas llevan días sin respuesta")
    except Exception:  # noqa: BLE001
        pass

    try:
        prov = hechos_de("proveedores").get("metricas") or {}
        if (prov.get("egresos_sin_proveedor") or 0) > 0:
            sugerir("egresos-sin-proveedor",
                    f"{prov['egresos_sin_proveedor']} gastos no dicen a quién se le compró")
    except Exception:  # noqa: BLE001
        pass

    try:
        rent = hechos_de("rentabilidad").get("metricas") or {}
        res = rent.get("resumen") or {}
        if (res.get("n_en_perdida") or 0) > 0:
            sugerir("proyectos-en-perdida",
                    f"{res['n_en_perdida']} proyectos están dejando pérdida")
        elif (res.get("n_bajo_umbral") or 0) > 0:
            sugerir("margen-real", "hay proyectos debajo del margen que consideras sano")
    except Exception:  # noqa: BLE001
        pass

    return propuestas


def sembrar_sugerencias(usuario) -> int:
    """Deja las propuestas como sugerencias para que la persona las acepte.

    Reusa `SugerenciaKPI`, el mecanismo que ya venía funcionando (6 de cada 10
    aceptadas), en vez de inventar otro camino. Idempotente: la unicidad
    (usuario, kpi_slug) evita repetir lo mismo, y lo descartado no vuelve.
    """
    from apps.taller_home.models import SugerenciaKPI

    creadas = 0
    for prop in proponer_indicadores(usuario):
        try:
            _, nueva = SugerenciaKPI.objects.get_or_create(
                usuario=usuario, kpi_slug=prop["slug"],
                defaults={"motivo": prop["razon"][:200], "estado": "pendiente"},
            )
            creadas += 1 if nueva else 0
        except Exception:  # noqa: BLE001
            logger.warning("no se pudo sembrar la sugerencia %s", prop["slug"], exc_info=True)
    return creadas
