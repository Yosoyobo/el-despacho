"""Helpers de fecha/hora con zona horaria de México."""

from datetime import datetime
from zoneinfo import ZoneInfo

TZ_MX = ZoneInfo("America/Mexico_City")


def ahora_mx() -> datetime:
    return datetime.now(TZ_MX)


def a_mx(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("Datetime sin tzinfo no se puede convertir a MX")
    return dt.astimezone(TZ_MX)
