"""Lógica del presupuesto de IA por usuario (S-Directorio-Panel-V1).

`evaluar(usuario)`  → estado para la UI (tope, gasto del mes, % y si rebasó).
`debe_topar(usuario_id)` → True si el gate de `lib.analistas.analizar` debe
                           rechazar la llamada (política `topar` + rebasado).

Todo es defensivo: si la tabla no existe aún o algo falla, se comporta como
"sin tope" (no rompe la operación de IA).
"""

from __future__ import annotations

from decimal import Decimal


def _gasto_mes(usuario_id: int) -> Decimal:
    from lib.analistas.stats import gasto_mes_usuario
    return gasto_mes_usuario(usuario_id)


def evaluar(usuario) -> dict:
    """Estado del presupuesto del usuario para mostrar en el modal/lista."""
    from .models.presupuesto_ia import PresupuestoIA

    p = PresupuestoIA.objects.filter(usuario=usuario).first()
    gastado = _gasto_mes(usuario.pk)
    if p is None or not p.activo or p.tope_usd <= 0:
        return {
            "tiene_tope": False,
            "tope_usd": Decimal("0"),
            "politica": p.politica if p else PresupuestoIA.POLITICA_ALERTAR,
            "activo": bool(p.activo) if p else False,
            "gastado_mes": gastado,
            "rebasado": False,
            "porcentaje": 0,
        }
    rebasado = gastado >= p.tope_usd
    pct = int(min(100, (gastado / p.tope_usd * 100))) if p.tope_usd > 0 else 0
    return {
        "tiene_tope": True,
        "tope_usd": p.tope_usd,
        "politica": p.politica,
        "activo": p.activo,
        "gastado_mes": gastado,
        "rebasado": rebasado,
        "porcentaje": pct,
    }


def debe_topar(usuario_id: int | None) -> bool:
    """¿La llamada IA de este usuario debe rechazarse por presupuesto?

    True solo si: hay fila activa, `politica='topar'`, `tope_usd>0` y el gasto
    del mes ya alcanzó el tope. Cualquier error → False (no topa)."""
    if not usuario_id:
        return False
    try:
        from .models.presupuesto_ia import PresupuestoIA

        p = (
            PresupuestoIA.objects.filter(
                usuario_id=usuario_id, activo=True, politica=PresupuestoIA.POLITICA_TOPAR
            )
            .filter(tope_usd__gt=0)
            .first()
        )
        if p is None:
            return False
        return _gasto_mes(usuario_id) >= p.tope_usd
    except Exception:
        return False
