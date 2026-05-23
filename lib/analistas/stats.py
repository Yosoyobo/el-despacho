"""Estadísticas agregadas por Chalán a partir de `AnalistaLog`.

Sirve para alimentar las tarjetas del panel de Los Chalanes y el bloque de
IA en El Site: llamadas, tokens, costo USD, última actividad por proveedor
en los últimos N días.

Las consultas son ligeras (SUM/COUNT con índices en `provider` y
`creado_en`) y se ejecutan en cada render del panel — sin caché. Si el
volumen crece, agregar memo de 30s con `lru_cache(maxsize=1)` + TTL.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Max, Sum
from django.utils import timezone


def _enmascarar(valor: str) -> str:
    """`sk-abcdefghij…wxyz` → `sk-a••••wxyz`. Devuelve cadena vacía si valor
    es vacío. Conserva 4 chars al inicio y 4 al final, en medio puntos."""
    if not valor:
        return ""
    valor = valor.strip()
    if len(valor) <= 10:
        return "•" * len(valor)
    return f"{valor[:4]}{'•' * 8}{valor[-4:]}"


def estadisticas_proveedores(dias: int = 30) -> dict[str, dict]:
    """Devuelve `{provider: {llamadas, llamadas_ok, llamadas_falla, prompt_tokens,
    completion_tokens, tokens, costo_usd, ultima_actividad, latencia_promedio}}`.

    Provider no usado en el rango no aparece — el caller debe combinar con
    `_FACTORIES` para mostrar tarjetas de proveedores sin uso.
    """
    from ajustes.models.analistas_log import AnalistaLog

    desde = timezone.now() - timedelta(days=dias)
    qs = AnalistaLog.objects.filter(creado_en__gte=desde)
    salida: dict[str, dict] = {}
    for row in qs.values("provider").annotate(
        llamadas=Count("id"),
        prompt_tokens=Sum("prompt_tokens"),
        completion_tokens=Sum("completion_tokens"),
        costo=Sum("costo_usd_estimado"),
        ultima=Max("creado_en"),
    ):
        provider = row["provider"]
        salida[provider] = {
            "llamadas": int(row["llamadas"] or 0),
            "prompt_tokens": int(row["prompt_tokens"] or 0),
            "completion_tokens": int(row["completion_tokens"] or 0),
            "tokens": int((row["prompt_tokens"] or 0) + (row["completion_tokens"] or 0)),
            "costo_usd": Decimal(row["costo"] or 0).quantize(Decimal("0.000001")),
            "ultima_actividad": row["ultima"],
        }

    # Conteo de fallas para mostrar en la tarjeta.
    for row in qs.values("provider", "exito").annotate(n=Count("id")):
        if row["provider"] not in salida:
            continue
        if row["exito"]:
            salida[row["provider"]]["llamadas_ok"] = int(row["n"])
        else:
            salida[row["provider"]]["llamadas_falla"] = int(row["n"])
    for v in salida.values():
        v.setdefault("llamadas_ok", v["llamadas"])
        v.setdefault("llamadas_falla", 0)
    return salida


def tarjetas_chalanes(dias: int = 30) -> list[dict]:
    """Lista de dicts listos para renderizar — un dict por adapter en `_FACTORIES`.

    Cada item: `{nombre, apodo, slot, configurado, llave_enmascarada,
    ultimo_test_*, modelo_default, estadisticas, capacidades_set}`.
    """
    from ajustes.models.credencial import Credencial

    from .capacidades import Capability
    from .registry import _FACTORIES

    stats = estadisticas_proveedores(dias=dias)
    salida: list[dict] = []
    for nombre, factory in _FACTORIES.items():
        adapter = factory()
        slot = f"chalan_{nombre}_api_key"
        cred = Credencial.objects.filter(clave=slot).first()
        llave = Credencial.obtener(slot) if cred else None
        configurado = bool(llave)
        # S-LC-Feedback-V3: detecta proveedores gratis (precio_in + precio_out == 0).
        # MiMo es el caso actual. Se importa por nombre desde el módulo del adapter.
        from importlib import import_module
        es_gratis = False
        try:
            mod = import_module(f"lib.analistas.adapters.{nombre}")
            precio_in = float(getattr(mod, "PRECIO_IN", 0))
            precio_out = float(getattr(mod, "PRECIO_OUT", 0))
            es_gratis = (precio_in + precio_out) == 0
        except Exception:  # noqa: BLE001
            pass
        salida.append({
            "nombre": nombre,
            "apodo": adapter.apodo,
            "slot": slot,
            "configurado": configurado,
            "llave_enmascarada": _enmascarar(llave) if llave else "",
            "ultimo_test_en": cred.ultimo_test_en if cred else None,
            "ultimo_test_ok": cred.ultimo_test_ok if cred else None,
            "ultimo_test_mensaje": cred.ultimo_test_mensaje if cred else "",
            "modelo_default": getattr(adapter, "modelo", ""),
            "soporta_vision": Capability.VISION in adapter.capacidades,
            "es_gratis": es_gratis,
            "estadisticas": stats.get(nombre, {
                "llamadas": 0, "tokens": 0, "costo_usd": Decimal("0"),
                "ultima_actividad": None,
                "llamadas_ok": 0, "llamadas_falla": 0,
            }),
        })
    salida.sort(key=lambda x: (-x["estadisticas"]["llamadas"], x["nombre"]))
    return salida


def resumen_global(dias: int = 30) -> dict:
    """`{costo_total, llamadas_total, tokens_total, max_costo_provider}` —
    para el banner superior del panel y de El Site.

    S-LC-Feedback-V3: proveedores con `costo_usd == 0` (MiMo gratis) se
    incluyen en llamadas/tokens pero `es_gratis=True` para que la UI
    no muestre barra de costo.
    """
    stats = estadisticas_proveedores(dias=dias)
    if not stats:
        return {
            "costo_total": Decimal("0"), "llamadas_total": 0, "tokens_total": 0,
            "max_costo": Decimal("0"), "por_proveedor": [],
        }
    por_proveedor = sorted(
        ((p, d["costo_usd"], d["tokens"], d["llamadas"]) for p, d in stats.items()),
        key=lambda x: -x[1],
    )
    max_costo = max((c for _, c, _, _ in por_proveedor), default=Decimal("0"))
    return {
        "costo_total": sum((d["costo_usd"] for d in stats.values()), Decimal("0")),
        "llamadas_total": sum(d["llamadas"] for d in stats.values()),
        "tokens_total": sum(d["tokens"] for d in stats.values()),
        "max_costo": max_costo,
        "por_proveedor": [
            {"provider": p, "costo_usd": c, "tokens": t, "llamadas": ll,
             "porcentaje_costo": float((c / max_costo * 100) if max_costo > 0 else 0),
             "es_gratis": c == 0}
            for p, c, t, ll in por_proveedor
        ],
    }
