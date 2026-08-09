"""Salud del sistema — señal ligera de «hay una falla» para el badge ⚠️.

La consume el sidebar de El Taller (context processor): si El Site detectó una
integración en error (token caído, Chalán en error…), TODOS los usuarios ven un
⚠️ junto a Ajustes. Cacheado 60s; nunca lanza (degrada a «sin falla»).

Nota: El Site (`apps.el_site`) vive en La Gerencia y NO está instalado en El
Taller, pero la tabla `site_chequeo` es de la MISMA base de datos compartida.
Por eso leemos el último estado por plataforma con SQL directo (sin depender del
modelo/app), y así funciona desde cualquiera de los dos proyectos.
"""

from __future__ import annotations

_CACHE_KEY = "salud_sistema_falla_v1"


def plataformas_en_error(limite: int = 5) -> list[str]:
    """Plataformas cuyo ÚLTIMO chequeo de `site_chequeo` quedó en 'error'.

    Lista vacía si no hay ninguna, si la tabla no existe todavía o si la base no
    responde — nunca lanza. La consume el badge ⚠️ del sidebar y el extremo
    `/salud` (que publica el CONTEO en abierto y los nombres solo con la
    credencial del Celador).
    """
    try:
        from django.db import connection
        with connection.cursor() as cur:
            # Portable (SQLite + Postgres): plataformas cuyo ÚLTIMO chequeo fue
            # 'error' (el más reciente por probado_en).
            cur.execute(
                """
                SELECT c.plataforma FROM site_chequeo c
                WHERE c.estado = 'error'
                  AND c.probado_en = (
                      SELECT MAX(c2.probado_en) FROM site_chequeo c2
                      WHERE c2.plataforma = c.plataforma
                  )
                ORDER BY c.plataforma
                LIMIT %s
                """,
                [limite],
            )
            return sorted({row[0] for row in cur.fetchall()})
    except Exception:  # noqa: BLE001 — la salud nunca debe tumbar la UI
        return []


def hay_falla(usar_cache: bool = True) -> dict:
    """Devuelve {falla: bool, motivo: str}. Marca falla si el último chequeo de
    alguna plataforma en `site_chequeo` quedó en estado 'error'."""
    from django.core.cache import cache

    if usar_cache:
        cached = cache.get(_CACHE_KEY)
        if cached is not None:
            return cached

    res = {"falla": False, "motivo": ""}
    malas = plataformas_en_error()
    if malas:
        res = {
            "falla": True,
            "motivo": "Problema de conexión: " + ", ".join(malas[:3]),
        }

    import contextlib
    with contextlib.suppress(Exception):
        cache.set(_CACHE_KEY, res, 60)
    return res
