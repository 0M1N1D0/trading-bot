"""Determina si un mercado está abierto en este momento.

Versión simple por zona horaria y horario regular de lun-vie. No considera
días feriados de cada bolsa; si eso importa, se puede añadir después con
`pandas_market_calendars` sin cambiar la firma de `is_open`.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

_MARKET_HOURS = {
    # (zona horaria, hora de apertura, hora de cierre)
    "US": (ZoneInfo("America/New_York"), time(9, 30), time(16, 0)),
    "MX": (ZoneInfo("America/Mexico_City"), time(8, 30), time(15, 0)),
}


def is_open(market: str, now: datetime | None = None) -> bool:
    """True si `market` ("US" o "MX") está en horario regular de operación.

    `now` es inyectable para pruebas; por defecto usa la hora actual.
    """
    if market not in _MARKET_HOURS:
        raise ValueError(f"Mercado desconocido: {market!r} (usa 'US' o 'MX')")

    tz, open_time, close_time = _MARKET_HOURS[market]
    local_now = (now or datetime.now(tz)).astimezone(tz)

    if local_now.weekday() >= 5:  # 5=sábado, 6=domingo
        return False

    return open_time <= local_now.time() <= close_time
