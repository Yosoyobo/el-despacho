"""POIs para fijar el destino de un Mandado — S-Mandados-V2.

Sin catálogo nuevo (decisión de proyecto: "visitas a POI sin catálogo"). Las
ubicaciones conocidas se reúnen de fuentes que ya existen y son gratis:
- `checador.SedeLC` activas con pin (las sedes/POI globales).
- Clientes y proveedores con una visita geolocalizada reciente (El Checador).

`pois_para_destino()` devuelve `[{label, lat, lng, fuente, clave}]` para poblar
un `<select>`. `resolver_poi(texto)` busca por nombre (para El Chalán).
"""

from __future__ import annotations

import contextlib


def _sedes() -> list[dict]:
    out: list[dict] = []
    with contextlib.suppress(Exception):
        from apps.checador.models.sede import SedeLC
        for s in SedeLC.objects.filter(activa=True, lat__isnull=False, lng__isnull=False).order_by("orden", "nombre"):
            out.append({
                "label": s.nombre,
                "lat": float(s.lat),
                "lng": float(s.lng),
                "fuente": "sede",
                "clave": f"sede:{s.pk}",
            })
    return out


def _por_visitas(campo: str, fuente: str, etiqueta_fn) -> list[dict]:
    """Última visita geolocalizada por cliente/proveedor → un POI por entidad."""
    out: list[dict] = []
    with contextlib.suppress(Exception):
        from apps.checador.models import Visita
        vistos: set[int] = set()
        qs = (
            Visita.objects
            .filter(**{f"{campo}__isnull": False}, lat__isnull=False, lng__isnull=False)
            .select_related(campo)
            .order_by("-registrado_en")
        )
        for v in qs[:500]:
            ent = getattr(v, campo, None)
            if ent is None or ent.pk in vistos:
                continue
            vistos.add(ent.pk)
            out.append({
                "label": etiqueta_fn(ent),
                "lat": float(v.lat),
                "lng": float(v.lng),
                "fuente": fuente,
                "clave": f"{fuente}:{ent.pk}",
            })
    return out


def pois_para_destino() -> list[dict]:
    """Lista combinada de POIs para el dropdown de destino del Mandado."""
    pois = _sedes()
    pois += _por_visitas("cliente", "cliente", lambda c: getattr(c, "razon_social", str(c)))
    pois += _por_visitas("proveedor", "proveedor", lambda p: getattr(p, "razon_social", str(p)))
    # Orden estable: sedes primero, luego alfabético.
    pois.sort(key=lambda p: (0 if p["fuente"] == "sede" else 1, p["label"].lower()))
    return pois


def resolver_poi(texto: str) -> dict | None:
    """Resuelve un POI por nombre (match exacto o por substring, sin acentos).
    Para El Chalán cuando el usuario dice 'recoge en la Sucursal Centro'."""
    texto = (texto or "").strip().lower()
    if not texto:
        return None
    pois = pois_para_destino()
    for p in pois:
        if p["label"].lower() == texto:
            return p
    for p in pois:
        if texto in p["label"].lower():
            return p
    return None


def _sin_acentos(s: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", (s or "").lower())
        if unicodedata.category(c) != "Mn"
    )


def buscar_pois(texto: str = "", limite: int = 8) -> list[dict]:
    """POIs internos (sedes + clientes/proveedores con ubicación conocida) que
    coinciden con `texto`, para el cuadro de resultados en vivo del geo-picker.

    Sin texto devuelve las primeras `limite` (sedes primero). Con texto filtra
    por substring sin acentos sobre la etiqueta. Defensivo: `[]` si algo falla.
    """
    try:
        pois = pois_para_destino()
    except Exception:  # noqa: BLE001 — nunca tumba el endpoint
        return []
    q = _sin_acentos(texto.strip())
    if q:
        pois = [p for p in pois if q in _sin_acentos(p.get("label", ""))]
    return pois[: max(1, limite)]
