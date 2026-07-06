from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.market_hours import is_open


def test_us_open_during_regular_hours():
    # Martes 6 de enero 2026, 10:00 am hora de Nueva York
    dt = datetime(2026, 1, 6, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_open("US", now=dt) is True


def test_us_closed_before_open():
    dt = datetime(2026, 1, 6, 8, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_open("US", now=dt) is False


def test_us_closed_on_weekend():
    # Sábado
    dt = datetime(2026, 1, 10, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_open("US", now=dt) is False


def test_mx_open_during_regular_hours():
    dt = datetime(2026, 1, 6, 9, 0, tzinfo=ZoneInfo("America/Mexico_City"))
    assert is_open("MX", now=dt) is True


def test_mx_closed_after_close():
    dt = datetime(2026, 1, 6, 16, 0, tzinfo=ZoneInfo("America/Mexico_City"))
    assert is_open("MX", now=dt) is False


def test_unknown_market_raises():
    with pytest.raises(ValueError):
        is_open("XX")
