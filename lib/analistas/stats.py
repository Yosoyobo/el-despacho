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
        costo_final = Decimal(row["costo"] or 0)
        salida[provider] = {
            "llamadas": int(row["llamadas"] or 0),
            "prompt_tokens": int(row["prompt_tokens"] or 0),
            "completion_tokens": int(row["completion_tokens"] or 0),
            "tokens": int((row["prompt_tokens"] or 0) + (row["completion_tokens"] or 0)),
            "costo_usd": costo_final.quantize(Decimal("0.000001")),
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


def _inicio_mes_actual():
    ahora = timezone.now()
    return ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def uso_por_usuario(usuario_id: int, ventanas: tuple[int, ...] = (7, 30, 90)) -> dict[str, dict]:
    """`{"7d": {llamadas, tokens, costo_usd}, "30d": {...}, "90d": {...}}` para un
    usuario, desde `AnalistaLog.actor`. Alimenta el panel de uso del Directorio."""
    from ajustes.models.analistas_log import AnalistaLog

    salida: dict[str, dict] = {}
    ahora = timezone.now()
    for dias in ventanas:
        agg = (
            AnalistaLog.objects.filter(actor_id=usuario_id, creado_en__gte=ahora - timedelta(days=dias))
            .aggregate(
                llamadas=Count("id"),
                prompt_tokens=Sum("prompt_tokens"),
                completion_tokens=Sum("completion_tokens"),
                costo=Sum("costo_usd_estimado"),
            )
        )
        salida[f"{dias}d"] = {
            "llamadas": int(agg["llamadas"] or 0),
            "tokens": int((agg["prompt_tokens"] or 0) + (agg["completion_tokens"] or 0)),
            "costo_usd": Decimal(agg["costo"] or 0).quantize(Decimal("0.000001")),
        }
    return salida


def gasto_mes_usuario(usuario_id: int) -> Decimal:
    """Suma de `costo_usd_estimado` del usuario en el mes calendario en curso."""
    from ajustes.models.analistas_log import AnalistaLog

    agg = AnalistaLog.objects.filter(
        actor_id=usuario_id, creado_en__gte=_inicio_mes_actual()
    ).aggregate(costo=Sum("costo_usd_estimado"))
    return Decimal(agg["costo"] or 0).quantize(Decimal("0.01"))


def gasto_mes_por_usuario() -> dict[int, Decimal]:
    """`{usuario_id: costo_usd}` del mes en curso, una sola query agrupada."""
    from ajustes.models.analistas_log import AnalistaLog

    qs = (
        AnalistaLog.objects.filter(creado_en__gte=_inicio_mes_actual(), actor__isnull=False)
        .values("actor_id").annotate(costo=Sum("costo_usd_estimado"))
    )
    return {row["actor_id"]: Decimal(row["costo"] or 0).quantize(Decimal("0.01")) for row in qs}


def gasto_por_usuario_dias(dias: int = 30) -> dict[int, Decimal]:
    """`{usuario_id: costo_usd}` en los últimos `dias`, una sola query agrupada.
    Para el chip de gasto IA en la lista del Directorio."""
    from ajustes.models.analistas_log import AnalistaLog

    desde = timezone.now() - timedelta(days=dias)
    qs = (
        AnalistaLog.objects.filter(creado_en__gte=desde, actor__isnull=False)
        .values("actor_id").annotate(costo=Sum("costo_usd_estimado"))
    )
    return {row["actor_id"]: Decimal(row["costo"] or 0).quantize(Decimal("0.01")) for row in qs}


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
        # La mayoría de Chalanes usan `chalan_<nombre>_api_key`; los que tienen
        # otro tipo de credencial (ej. un base URL de servidor propio) declaran su slot.
        slot = getattr(adapter, "slot_credencial", "") or f"chalan_{nombre}_api_key"
        cred = Credencial.objects.filter(clave=slot).first()
        llave = Credencial.obtener(slot) if cred else None
        configurado = bool(llave)
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
            "estadisticas": stats.get(nombre, {
                "llamadas": 0, "tokens": 0, "costo_usd": Decimal("0"),
                "ultima_actividad": None,
                "llamadas_ok": 0, "llamadas_falla": 0,
            }),
        })
    salida.sort(key=lambda x: (-x["estadisticas"]["llamadas"], x["nombre"]))
    return salida


def _etiquetas_estaciones() -> dict[str, str]:
    """slug de estación → etiqueta legible (desde chalanes.estaciones)."""
    try:
        from chalanes.estaciones import ESTACIONES
        return {clave: etiqueta for clave, etiqueta, *_ in ESTACIONES}
    except Exception:  # noqa: BLE001
        return {}


def kpis_consumo(dias: int = 30) -> dict:
    """KPIs del header de la analítica: llamadas, tokens totales/entrada/salida,
    costo estimado (en la ventana de `dias`)."""
    from ajustes.models.analistas_log import AnalistaLog

    desde = timezone.now() - timedelta(days=dias)
    agg = AnalistaLog.objects.filter(creado_en__gte=desde).aggregate(
        llamadas=Count("id"),
        prompt_tokens=Sum("prompt_tokens"),
        completion_tokens=Sum("completion_tokens"),
        costo=Sum("costo_usd_estimado"),
    )
    pin = int(agg["prompt_tokens"] or 0)
    pout = int(agg["completion_tokens"] or 0)
    return {
        "llamadas": int(agg["llamadas"] or 0),
        "tokens_total": pin + pout,
        "tokens_entrada": pin,
        "tokens_salida": pout,
        "costo_total": Decimal(agg["costo"] or 0).quantize(Decimal("0.0001")),
    }


def estadisticas_por_estacion(dias: int = 30) -> list[dict]:
    """`[{estacion, etiqueta, llamadas, tokens, costo_usd, porcentaje_costo}]`
    ordenado por costo desc. Para la sección 'Por función'."""
    from ajustes.models.analistas_log import AnalistaLog

    desde = timezone.now() - timedelta(days=dias)
    etiquetas = _etiquetas_estaciones()
    filas = []
    for row in (
        AnalistaLog.objects.filter(creado_en__gte=desde)
        .values("estacion")
        .annotate(
            llamadas=Count("id"),
            prompt_tokens=Sum("prompt_tokens"),
            completion_tokens=Sum("completion_tokens"),
            costo=Sum("costo_usd_estimado"),
        )
    ):
        est = row["estacion"] or "—"
        costo = Decimal(row["costo"] or 0).quantize(Decimal("0.000001"))
        filas.append({
            "estacion": est,
            "etiqueta": etiquetas.get(est, est),
            "llamadas": int(row["llamadas"] or 0),
            "tokens": int((row["prompt_tokens"] or 0) + (row["completion_tokens"] or 0)),
            "costo_usd": costo,
        })
    filas.sort(key=lambda x: -x["costo_usd"])
    max_costo = max((f["costo_usd"] for f in filas), default=Decimal("0"))
    for f in filas:
        f["porcentaje_costo"] = float((f["costo_usd"] / max_costo * 100) if max_costo > 0 else 0)
    return filas


def usuarios_top(dias: int = 30, limit: int = 10) -> list[dict]:
    """`[{actor_id, nombre, email, llamadas, tokens, costo_usd}]` — usuarios con
    más llamadas en la ventana, top `limit`."""
    from ajustes.models.analistas_log import AnalistaLog
    from cuentas.models.usuario import Usuario

    desde = timezone.now() - timedelta(days=dias)
    filas = list(
        AnalistaLog.objects.filter(creado_en__gte=desde, actor__isnull=False)
        .values("actor_id")
        .annotate(
            llamadas=Count("id"),
            prompt_tokens=Sum("prompt_tokens"),
            completion_tokens=Sum("completion_tokens"),
            costo=Sum("costo_usd_estimado"),
        )
        .order_by("-llamadas")[:limit]
    )
    nombres = dict(
        Usuario.objects.filter(pk__in=[f["actor_id"] for f in filas])
        .values_list("pk", "nombre_completo")
    )
    correos = dict(
        Usuario.objects.filter(pk__in=[f["actor_id"] for f in filas]).values_list("pk", "email")
    )
    return [{
        "actor_id": f["actor_id"],
        "nombre": nombres.get(f["actor_id"], "—"),
        "email": correos.get(f["actor_id"], ""),
        "llamadas": int(f["llamadas"] or 0),
        "tokens": int((f["prompt_tokens"] or 0) + (f["completion_tokens"] or 0)),
        "costo_usd": Decimal(f["costo"] or 0).quantize(Decimal("0.0001")),
    } for f in filas]


def ultimas_llamadas(dias: int = 30, limit: int = 50) -> list[dict]:
    """`[{creado_en, estacion, etiqueta, provider, modelo, prompt_tokens,
    completion_tokens, costo_usd, actor_email, exito}]` — auditoría reciente."""
    from ajustes.models.analistas_log import AnalistaLog

    desde = timezone.now() - timedelta(days=dias)
    etiquetas = _etiquetas_estaciones()
    filas = (
        AnalistaLog.objects.filter(creado_en__gte=desde)
        .select_related("actor")
        .order_by("-creado_en")[:limit]
    )
    return [{
        "creado_en": r.creado_en,
        "estacion": r.estacion,
        "etiqueta": etiquetas.get(r.estacion, r.estacion),
        "provider": r.provider,
        "modelo": r.modelo,
        "prompt_tokens": r.prompt_tokens,
        "completion_tokens": r.completion_tokens,
        "costo_usd": r.costo_usd_estimado,
        "actor_email": r.actor.email if r.actor_id else "—",
        "exito": r.exito,
    } for r in filas]


def resumen_global(dias: int = 30) -> dict:
    """`{costo_total, llamadas_total, tokens_total, max_costo_provider}` —
    para el banner superior del panel y de El Site. Todos los proveedores
    cuentan su costo real desde `AnalistaLog`.
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
             "porcentaje_costo": float((c / max_costo * 100) if max_costo > 0 else 0)}
            for p, c, t, ll in por_proveedor
        ],
    }
