"""Series cortas de la tabla ``site_chequeo`` para alimentar sparklines y
mini-tendencias en El Site. Devuelve datos cocidos (ya escalados) listos
para SVG inline; no JS, no charting libs.

Cada serie es máximo `n` puntos en orden cronológico (viejo → nuevo).
Si una plataforma no tiene historia, retorna lista vacía y la UI dibuja
un guion."""

from __future__ import annotations

from typing import Any


def serie_latencia(plataforma: str, n: int = 20) -> list[dict[str, Any]]:
    from apps.el_site.models import SiteChequeo

    rows = list(
        SiteChequeo.objects.filter(plataforma=plataforma)
        .order_by("-probado_en")
        .values("estado", "latencia_ms", "probado_en")[:n]
    )
    rows.reverse()
    return [
        {
            "estado": r["estado"],
            "latencia_ms": r["latencia_ms"] or 0,
            "probado_en": r["probado_en"].isoformat() if r["probado_en"] else None,
        }
        for r in rows
    ]


def sparkline_puntos(serie: list[dict[str, Any]], ancho: int = 100, alto: int = 28) -> dict[str, Any]:
    """Convierte la serie en coordenadas SVG. Retorna ``{path, puntos,
    max_lat, min_lat, ultimo_estado}``. Si la serie está vacía, retorna
    estructura con ``vacio=True``."""
    if not serie:
        return {"vacio": True, "ancho": ancho, "alto": alto}
    vals = [p["latencia_ms"] for p in serie]
    mx = max(vals) or 1
    mn = min(vals)
    rango = max(mx - mn, 1)
    n = len(serie)
    xs = [ancho / 2] if n == 1 else [i * (ancho / (n - 1)) for i in range(n)]
    ys = [alto - 2 - ((v - mn) / rango) * (alto - 4) for v in vals]
    puntos = [
        {"x": round(x, 2), "y": round(y, 2), "v": vals[i], "estado": serie[i]["estado"]}
        for i, (x, y) in enumerate(zip(xs, ys, strict=False))
    ]
    path = "M " + " L ".join(f"{p['x']},{p['y']}" for p in puntos)
    area = (
        f"{path} L {puntos[-1]['x']},{alto} L {puntos[0]['x']},{alto} Z"
    )
    return {
        "vacio": False,
        "ancho": ancho,
        "alto": alto,
        "path": path,
        "area": area,
        "puntos": puntos,
        "max_lat": mx,
        "min_lat": mn,
        "ultimo_estado": serie[-1]["estado"],
        "ultima_latencia": vals[-1],
    }


def series_apex_por_plataforma(n: int = 60) -> list[dict[str, Any]]:
    """Series multi-línea para un area chart de ApexCharts: una línea por
    plataforma, con timestamp (ms) y latencia. Solo incluye plataformas
    con al menos 2 puntos."""
    from .registry import PLATAFORMAS

    paleta = [
        "#465fff", "#12b76a", "#f79009", "#ee46bc", "#0ba5ec",
        "#7a5af8", "#f04438", "#0e9384", "#a15c07", "#475467",
    ]
    salida = []
    for i, plat in enumerate(PLATAFORMAS):
        s = serie_latencia(plat, n=n)
        if len(s) < 2:
            continue
        data = [
            {"x": p["probado_en"], "y": p["latencia_ms"] or 0}
            for p in s
            if p["probado_en"]
        ]
        salida.append({
            "name": plat,
            "color": paleta[i % len(paleta)],
            "data": data,
        })
    return salida


def histograma_chequeos(dias: int = 14) -> list[dict[str, Any]]:
    """Conteo diario ok/error de los últimos N días, para barras apiladas."""
    from datetime import timedelta

    from apps.el_site.models import SiteChequeo
    from django.db.models import Count, Q
    from django.utils import timezone

    hoy = timezone.localdate()
    desde = hoy - timedelta(days=dias - 1)
    qs = (
        SiteChequeo.objects
        .filter(probado_en__date__gte=desde)
        .extra(select={"d": "date(probado_en)"})  # noqa: S610
        .values("d")
        .annotate(
            ok=Count("id", filter=Q(estado="ok")),
            error=Count("id", filter=Q(estado="error")),
        )
        .order_by("d")
    )
    idx = {row["d"]: row for row in qs}
    out = []
    for k in range(dias):
        f = desde + timedelta(days=k)
        r = idx.get(f) or idx.get(str(f))
        out.append({
            "fecha": f.strftime("%d %b"),
            "ok": (r or {}).get("ok", 0),
            "error": (r or {}).get("error", 0),
        })
    return out


def resumen_estados() -> dict[str, int]:
    """Cuenta por estado mirando la última lectura de cada plataforma del
    registry. Útil para la dona global de salud."""
    from .almacen import ultimo_por_plataforma

    out = {"ok": 0, "error": 0, "no_configurada": 0, "sin_datos": 0}
    for v in ultimo_por_plataforma().values():
        out[v.get("estado", "sin_datos")] = out.get(v.get("estado", "sin_datos"), 0) + 1
    return out
